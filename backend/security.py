"""Security configuration, versioned passwords and bounded sign-in budgets."""
import hashlib
import secrets
import threading
import time
from urllib.parse import urlparse
from fastapi import HTTPException

PASSWORD_ITERATIONS = 600_000
WINDOW_SECONDS = 300
ACCOUNT_LIMIT = 10
PEER_LIMIT = 300
MAX_BUCKETS = 10_000


def cors_origins(environment):
    production = environment.get('APP_ENV', 'development') == 'production' or environment.get('RENDER') == 'true'
    value = environment.get('CORS_ALLOWED_ORIGINS', '')
    if production and not environment.get('DATABASE_URL', '').strip():
        raise RuntimeError('Production requires DATABASE_URL')
    if production and not value.strip():
        raise RuntimeError('Production requires CORS_ALLOWED_ORIGINS')
    origins = [x.strip() for x in (value or 'http://localhost:8081,http://localhost:19006').split(',') if x.strip()]
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or '*' in origin:
            raise RuntimeError('CORS origins must be explicit origins without paths or wildcards')
        if production and parsed.scheme != 'https':
            raise RuntimeError('Production CORS origins must use HTTPS')
    return origins


def hash_password(password, salt):
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PASSWORD_ITERATIONS).hex()
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${digest}'


def verify_password(password, salt, stored):
    iterations = 120_000
    digest = stored or ''
    if digest.startswith('pbkdf2_sha256$'):
        try:
            _, count, digest = digest.split('$')
            iterations = int(count)
            if iterations < 120_000 or iterations > 2_000_000: return False
        except ValueError: return False
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), (salt or '').encode(), iterations).hex()
    if iterations < PASSWORD_ITERATIONS:
        hashlib.pbkdf2_hmac('sha256', password.encode(), b'legacy-timing-padding', PASSWORD_ITERATIONS-iterations)
    return secrets.compare_digest(actual, digest)


def rate_keys(email, peer):
    return [(hashlib.sha256(('account:'+email).encode()).hexdigest(), ACCOUNT_LIMIT),
            (hashlib.sha256(('peer:'+peer).encode()).hexdigest(), PEER_LIMIT)]


def rate_exceeded(retry=WINDOW_SECONDS):
    return HTTPException(429, 'Too many sign-in attempts. Try again later.', headers={'Retry-After': str(max(1, int(retry)))})


class MemoryLoginLimiter:
    """Local demo only; production uses the shared PostgreSQL budget."""
    def __init__(self):
        self.lock = threading.Lock()
        self.buckets = {}

    def reserve(self, keys):
        with self.lock:
            now = time.monotonic()
            self.buckets = {k: v for k, v in self.buckets.items() if v[1] > now}
            if len(self.buckets) + sum(k not in self.buckets for k, _ in keys) > MAX_BUCKETS: raise rate_exceeded()
            for key, limit in keys:
                count, expires = self.buckets.get(key, (0, now+WINDOW_SECONDS))
                if count >= limit: raise rate_exceeded(expires-now)
            for key, _ in keys:
                count, expires = self.buckets.get(key, (0, now+WINDOW_SECONDS))
                self.buckets[key] = count+1, expires


def install_security(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS auth_rate_limits (
        key TEXT PRIMARY KEY, attempts INTEGER NOT NULL CHECK(attempts>0), expires_at TIMESTAMPTZ NOT NULL
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS auth_rate_limits_expiry ON auth_rate_limits(expires_at)')


def reserve_login(conn, keys):
    # Tiny serialized reservation; password verification happens outside this lock.
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(471006)')
        conn.execute('DELETE FROM auth_rate_limits WHERE expires_at<=NOW()')
        count = conn.execute('SELECT COUNT(*) AS count FROM auth_rate_limits').fetchone()['count']
        existing = {}
        for key, limit in keys:
            row = conn.execute('SELECT attempts, EXTRACT(EPOCH FROM (expires_at-NOW())) AS retry FROM auth_rate_limits WHERE key=%s', (key,)).fetchone()
            if row and row['attempts'] >= limit: raise rate_exceeded(row['retry'])
            existing[key] = row
        if count + sum(row is None for row in existing.values()) > MAX_BUCKETS: raise rate_exceeded()
        for key, _ in keys:
            conn.execute("INSERT INTO auth_rate_limits(key,attempts,expires_at) VALUES (%s,1,NOW()+INTERVAL '300 seconds') ON CONFLICT(key) DO UPDATE SET attempts=auth_rate_limits.attempts+1", (key,))

"""Private fixtures for real-local-API platform browser checks; no production traffic."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_postgres_isolation import PostgresIsolationTests
import server
url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('127.0.0.1','localhost','::1') or not any(x in url.path.lower() for x in ('test','integration')):raise SystemExit('Use a disposable local test/integration database')
fixtures=PostgresIsolationTests;fixtures.setUpClass()
try:
    with server.db() as conn:
        conn.execute("UPDATE brands SET name='Platform Test Brand' WHERE id=%s",(fixtures.brand_a,))
        conn.execute("UPDATE stores SET name='Platform HQ' WHERE id=%s",(fixtures.stores[0],))
    output=Path(sys.argv[1]);output.write_text(json.dumps({'super_user':fixtures.prefix+'-super','super_token':fixtures.tokens['super']}));output.chmod(0o600)
    print('Private platform browser fixtures prepared')
finally:fixtures.doClassCleanups()

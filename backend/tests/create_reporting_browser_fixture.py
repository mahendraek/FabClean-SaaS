"""Local synthetic reports; no production requests or third-party calls."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_reporting import ReportingPostgresTests
import server

url = urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL', ''))
if url.hostname not in ('localhost', '127.0.0.1', '::1') or 'test' not in url.path:
    raise SystemExit('Disposable local database required')
ReportingPostgresTests.setUpClass()
f = ReportingPostgresTests.f
try:
    with server.db() as conn:
        for store, name in zip(f.stores, ['Market Reports Store', 'Central Reports Store', 'Foreign Reports Store']):
            conn.execute('UPDATE stores SET name=%s WHERE id=%s', (name, store))
    # Exercise actual pagination, not a mocked API response.
    for index in range(26):
        order = f.ok(0, 'post', '/api/orders', {'customer_name': 'Synthetic report customer', 'customer_phone': '5550100', 'items': [{'service_id': 'shared-service', 'service_name': 'Wash', 'quantity': 1, 'unit_price': 5}]})
        from tenant_scope import current_scope
        marker = current_scope.set((f.brand_a, f.stores[0]))
        try:
            with server.db() as conn:
                conn.execute("UPDATE orders SET created_at='2026-03-08T08:00:00Z' WHERE id=%s", (order['id'],))
        finally:
            current_scope.reset(marker)
    path = Path(sys.argv[1])
    path.write_text(json.dumps({'token': f.tokens[0], 'manager_token': f.tokens[1], 'foreign_token': f.tokens[2], 'user': f.users[0], 'manager': f.users[1], 'brand': f.brand_a, 'stores': f.stores}))
    path.chmod(0o600)
    print('Private reporting browser fixtures prepared')
finally:
    ReportingPostgresTests.doClassCleanups()

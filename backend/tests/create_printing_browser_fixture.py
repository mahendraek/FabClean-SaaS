"""Prepare synthetic fixtures only on a disposable local database."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_printing import PrintingAPITests
import server
from tenant_scope import current_scope

url = urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL', ''))
if url.hostname not in ('localhost', '127.0.0.1', '::1') or 'test' not in url.path:
    raise SystemExit('Disposable local database required')
PrintingAPITests.setUpClass()
f = PrintingAPITests.f
try:
    f.ok(0, 'put', '/api/settings', {'business_name': 'Print Fixture Laundry', 'hardware_profile': {'receipt_paper': '80mm'}})
    marker = current_scope.set((f.brand_a, f.stores[0]))
    try:
        with server.db() as conn:
            conn.execute("UPDATE orders SET payload=payload || '{\"currency\":\"INR\"}'::jsonb WHERE id=%s", (f.orders[0]['id'],))
    finally:
        current_scope.reset(marker)
    output = Path(sys.argv[1])
    output.write_text(json.dumps({'token': f.tokens[0], 'foreign_token': f.tokens[2], 'user': f.users[0], 'brand': f.brand_a, 'store': f.stores[0], 'order': f.orders[0]['id']}))
    output.chmod(0o600)
    print('Private printing browser fixtures prepared')
finally:
    PrintingAPITests.doClassCleanups()

"""Prepare browser fixtures only in FABCLEAN_TEST_DATABASE_URL (disposable DB).

Run from backend with the explicit disposable database variable and an output
path. Fixture tokens are local test sessions; never use a production database.
"""
import json
import os
import sys
from pathlib import Path

from tests.test_store_operations import StoreOperationsAPITests
import server

if not os.getenv("FABCLEAN_TEST_DATABASE_URL"):
    raise SystemExit("Set FABCLEAN_TEST_DATABASE_URL to a disposable database")
fixtures = StoreOperationsAPITests
fixtures.setUpClass()
try:
    with server.db() as conn:
        for store, name in zip(fixtures.stores, ["Market Street Store", "Central Plant", "North Dropoff", "Foreign Store"]):
            conn.execute("UPDATE stores SET name=%s WHERE id=%s", (name, store))
        conn.execute("UPDATE brands SET name='Browser Test Brand' WHERE id=%s", (fixtures.brand,))
    orders = [fixtures().order() for _ in range(4)]
    output = Path(sys.argv[1])
    output.write_text(json.dumps({"tokens": fixtures.tokens, "users": fixtures.users, "stores": fixtures.stores, "brand": fixtures.brand, "orders": [{"id": order["id"], "order_number": order["order_number"]} for order in orders]}))
    output.chmod(0o600)
    print("Browser fixtures written to", output)
finally:
    fixtures.doClassCleanups()

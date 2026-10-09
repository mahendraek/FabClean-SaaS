"""Exercise the upgrade from the legacy schema in an isolated test schema."""
import json
import os
import unittest
import uuid
from unittest.mock import patch

from psycopg import sql
from psycopg.conninfo import make_conninfo

import server
from tenant_scope import current_scope


@unittest.skipUnless(os.getenv("FABCLEAN_TEST_DATABASE_URL"), "Set FABCLEAN_TEST_DATABASE_URL for migration checks")
class LegacyMigrationTests(unittest.TestCase):
    def test_upgrade_quarantines_unknown_and_inconsistent_ownership(self):
        source = os.environ["FABCLEAN_TEST_DATABASE_URL"]
        schema = "pr4_migration_" + uuid.uuid4().hex
        with patch.object(server, "DATABASE_URL", source):
            with server.db() as conn:
                conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        isolated = make_conninfo(source, options="-c search_path=" + schema)
        token = current_scope.set(None)
        try:
            with patch.object(server, "DATABASE_URL", isolated):
                # Create the pre-isolation schema using the existing bootstrap,
                # then insert historical rows before enabling the migration.
                with patch.object(server, "install_isolation"):
                    server.init_db()
                with server.db(maintenance=True) as conn:
                    conn.execute("INSERT INTO customers (id,name,phone) VALUES ('legacy-customer','Legacy','555')")
                    for oid, scope in (("known", {"business_id": "fabclean", "location_id": "main"}), ("unknown", {}), ("inconsistent", {"business_id": "fabclean", "location_id": "another-store"})):
                        payload = {**scope, "id": oid, "customer": {"id": "legacy-customer"}, "order_number": oid, "barcode_value": oid}
                        conn.execute("INSERT INTO orders (id,order_number,barcode_value,payload) VALUES (%s,%s,%s,%s::jsonb)", (oid, oid, oid, json.dumps(payload)))
                        conn.execute("INSERT INTO order_events (id,order_id,event_type) VALUES (%s,%s,'legacy')", (oid + "-event", oid))
                server.init_db()
                server.init_db()
                current_scope.set(("fabclean", "main"))
                with server.db() as conn:
                    self.assertEqual([r["id"] for r in conn.execute("SELECT id FROM orders").fetchall()], ["known"])
                    self.assertEqual([r["order_id"] for r in conn.execute("SELECT order_id FROM order_events").fetchall()], ["known"])
                    self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM services").fetchone()["n"], 7)
                with server.db(maintenance=True) as conn:
                    rows = conn.execute("SELECT id,business_id,location_id FROM orders WHERE id IN ('unknown','inconsistent') ORDER BY id").fetchall()
                    self.assertEqual(len(rows), 2)
                    self.assertTrue(all(r["business_id"] is None and r["location_id"] is None for r in rows))
                    # No migration silently assigns a platform-wide role.
                    self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM user_role_assignments WHERE role='super_admin'").fetchone()["n"], 0)
        finally:
            current_scope.reset(token)
            with patch.object(server, "DATABASE_URL", source):
                with server.db() as conn:
                    conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


if __name__ == "__main__": unittest.main()

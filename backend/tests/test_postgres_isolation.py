"""Real PostgreSQL/API isolation tests.

Run with FABCLEAN_TEST_DATABASE_URL pointing to an isolated disposable database
owned by a NOSUPERUSER NOBYPASSRLS role. No tables/databases are dropped. Each
run uses unique fixture IDs. Without that variable this suite is skipped.
"""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.errors import ForeignKeyViolation, InsufficientPrivilege

import server
from tenant_scope import OWNED_TABLES, current_scope


@unittest.skipUnless(os.getenv("FABCLEAN_TEST_DATABASE_URL"), "Set FABCLEAN_TEST_DATABASE_URL for live PostgreSQL checks")
class PostgresIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_patch = patch.object(server, "DATABASE_URL", os.environ["FABCLEAN_TEST_DATABASE_URL"])
        cls.db_patch.start()
        cls.addClassCleanup(cls.db_patch.stop)
        server.init_db()
        server.init_db()  # migration repeatability
        cls.prefix = "pr4-" + uuid.uuid4().hex
        cls.brand_a, cls.brand_b = cls.prefix + "-a", cls.prefix + "-b"
        cls.stores = [cls.prefix + suffix for suffix in ("-a1", "-a2", "-b1")]
        cls.tokens = {}
        cls.users = {}
        with server.db(maintenance=True) as conn:
            for brand in (cls.brand_a, cls.brand_b):
                conn.execute("INSERT INTO brands (id,name,slug) VALUES (%s,%s,%s)", (brand, brand, brand))
            for index, store in enumerate(cls.stores):
                brand = cls.brand_a if index < 2 else cls.brand_b
                conn.execute("INSERT INTO stores (id,brand_id,store_code,name) VALUES (%s,%s,%s,%s)", (store, brand, store, store))
                uid = cls.prefix + "-user-" + str(index)
                cls.users[index] = uid
                cls.tokens[index] = "fixture-" + uid
                conn.execute("INSERT INTO staff_users (id,name,email,role,business_id,location_id) VALUES (%s,%s,%s,'manager',%s,%s)", (uid, uid, uid + "@example.com", brand, store))
                conn.execute("INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id) VALUES (%s,%s,'store_manager','store',%s,%s)", (uid + "-role", uid, brand, store))
                conn.execute("INSERT INTO staff_sessions (token,staff_id,active_brand_id,active_store_id) VALUES (%s,%s,%s,%s)", (cls.tokens[index], uid, brand, store))
            # A real SuperAdmin session still sees only its selected store.
            uid = cls.prefix + "-super"
            cls.tokens["super"] = "fixture-" + uid
            conn.execute("INSERT INTO staff_users (id,name,email,role,business_id,location_id) VALUES (%s,%s,%s,'owner',%s,%s)", (uid, uid, uid + "@example.com", cls.brand_a, cls.stores[0]))
            conn.execute("INSERT INTO user_role_assignments (id,user_id,role,scope_type) VALUES (%s,%s,'super_admin','platform')", (uid + "-role", uid))
            conn.execute("INSERT INTO staff_sessions (token,staff_id,active_brand_id,active_store_id) VALUES (%s,%s,%s,%s)", (cls.tokens["super"], uid, cls.brand_a, cls.stores[0]))
        cls.client = TestClient(server.app)
        cls.addClassCleanup(cls.client.close)
        cls.orders, cls.customers, cls.areas, cls.slots, cls.plans, cls.notifications, cls.garments = {}, {}, {}, {}, {}, {}, {}
        for index in range(3):
            cls.ok(index, "put", "/api/settings", {"business_name": "Store " + str(index)})
            cls.ok(index, "post", "/api/admin/categories", {"name": "Test"})
            cls.ok(index, "post", "/api/services", {"id": "shared-service", "category": "Test", "name": "Wash", "pricing_type": "per_item", "base_price": 5, "business_id": "forged", "location_id": "forged"})
            order = cls.ok(index, "post", "/api/orders", {"customer_name": "Customer " + str(index), "customer_phone": "5550100", "items": [{"service_id": "shared-service", "service_name": "Wash", "quantity": 2, "unit_price": 5}]})
            cls.orders[index] = order
            cls.customers[index] = order["customer"]["id"]
            cls.ok(index, "post", "/api/orders/" + order["id"] + "/payments", {"amount": 5})
            cls.garments[index] = cls.ok(index, "get", "/api/orders/" + order["id"] + "/garments")["garments"][0]["garment_code"]
            cls.areas[index] = cls.ok(index, "post", "/api/scheduling/areas", {"name": "Area " + str(index)})["id"]
            cls.slots[index] = cls.ok(index, "post", "/api/scheduling/slots", {"name": "Slot " + str(index)})["id"]
            cls.ok(index, "post", "/api/scheduling/blackouts", {"blackout_date": "2030-01-01", "reason": "Store " + str(index)})
            cls.ok(index, "post", "/api/offers", {"name": "Offer " + str(index), "code": "SHARED", "discount_type": "fixed", "discount_value": index + 1})
            cls.plans[index] = cls.ok(index, "post", "/api/subscriptions/plans", {"name": "Plan " + str(index), "eligible_service_ids": ["shared-service"]})["id"]
            cls.notifications[index] = cls.ok(index, "post", "/api/notifications/prepare", {"order_id": order["id"]})["id"]

    @classmethod
    def request(cls, index, method, path, body=None):
        kwargs = {"headers": {"X-Session-Token": cls.tokens[index]}}
        if body is not None: kwargs["json"] = body
        return getattr(cls.client, method)(path, **kwargs)

    @classmethod
    def ok(cls, index, method, path, body=None):
        r = cls.request(index, method, path, body)
        if r.status_code != 200:
            raise AssertionError(f"{method} {path}: {r.status_code} {r.text}")
        return r.json()

    def test_list_search_and_catalogs_are_store_scoped(self):
        for index in range(3):
            with self.subTest(store=index):
                self.assertEqual([o["id"] for o in self.ok(index, "get", "/api/orders")["orders"]], [self.orders[index]["id"]])
                self.assertEqual(self.ok(index, "get", "/api/settings")["business_name"], "Store " + str(index))
                customers = self.ok(index, "get", "/api/customers?q=555")["customers"]
                self.assertEqual([c["id"] for c in customers], [self.customers[index]])
                self.assertEqual(customers[0]["lifetime_value"], 10)
                service = self.ok(index, "get", "/api/services")["services"][0]
                self.assertEqual(service["location_id"], self.stores[index])
                self.assertEqual(self.ok(index, "get", "/api/scheduling/areas")["areas"][0]["id"], self.areas[index])
                self.assertEqual(self.ok(index, "get", "/api/scheduling/blackouts")["blackouts"][0]["reason"], "Store " + str(index))
                self.assertEqual(self.ok(index, "get", "/api/subscriptions/plans")["plans"][0]["id"], self.plans[index])
                self.assertEqual(self.ok(index, "get", "/api/offers")["offers"][0]["name"], "Offer " + str(index))

    def test_shared_barcodes_resolve_only_in_selected_store(self):
        self.assertEqual(len({o["barcode_value"] for o in self.orders.values()}), 1)
        for index in range(3):
            for code in (self.orders[index]["order_number"], self.orders[index]["barcode_value"], self.orders[index]["items"][0]["barcode_value"]):
                self.assertEqual(self.ok(index, "get", "/api/orders/" + code)["id"], self.orders[index]["id"])
            self.assertEqual(self.ok(index, "get", "/api/garments/" + self.garments[index])["order"]["id"], self.orders[index]["id"])

    def test_foreign_detail_and_mutations_fail_without_side_effects(self):
        for foreign in (1, 2):
            oid, cid = self.orders[foreign]["id"], self.customers[foreign]
            cases = [
                ("get", f"/api/orders/{oid}", None),
                ("put", f"/api/orders/{oid}", {"notes": "Intruder"}),
                ("put", f"/api/orders/{oid}/status", {"status": "completed"}),
                ("post", f"/api/orders/{oid}/payments", {"amount": 99}),
                ("get", f"/api/orders/{oid}/receipt", None),
                ("get", f"/api/orders/{oid}/events", None),
                ("get", f"/api/orders/{oid}/inspection", None),
                ("get", f"/api/orders/{oid}/garments", None),
                ("post", f"/api/orders/{oid}/garments/{self.garments[foreign]}/scan", {}),
                ("post", f"/api/orders/{oid}/photos", {"data_base64": "aGk="}),
                ("post", f"/api/ai/orders/{oid}/inspection-suggest", {}),
                ("get", f"/api/ai/orders/{oid}/risks", None),
                ("get", f"/api/customers/{cid}/profile", None),
                ("get", f"/api/customers/{cid}/payments", None),
                ("post", f"/api/customers/{cid}/rewards", {"points": 5}),
                ("get", f"/api/customers/{cid}/referrals", None),
                ("get", f"/api/customers/{cid}/subscriptions", None),
                ("get", f"/api/customers/{cid}/notifications", None),
                ("post", f"/api/notifications/{self.notifications[foreign]}/resend", {}),
                ("put", f"/api/scheduling/areas/{self.areas[foreign]}", {"name": "Intruder"}),
            ]
            for method, path, body in cases:
                with self.subTest(path=path):
                    self.assertEqual(self.request(0, method, path, body).status_code, 404)
            self.assertNotEqual(self.ok(foreign, "get", f"/api/orders/{oid}")["notes"], "Intruder")

    def test_related_ids_cannot_cross_store(self):
        cid = self.customers[0]
        cases = [
            ("/api/orders", {"customer_id": self.customers[1], "customer_name": "Forged", "customer_phone": "555", "quick_dropoff": True, "bag_count": 1}),
            (f"/api/customers/{cid}/subscriptions", {"plan_id": self.plans[1]}),
            ("/api/notifications/prepare", {"customer_id": self.customers[1]}),
            ("/api/orders", {"customer_name": "Forged", "customer_phone": "555", "quick_dropoff": True, "bag_count": 1, "service_area_id": self.areas[1]}),
        ]
        for path, body in cases:
            with self.subTest(path=path): self.assertIn(self.request(0, "post", path, body).status_code, (400, 404))
        self.assertEqual(self.request(0, "put", f"/api/orders/{self.orders[0]['id']}/inspection/not-an-item", {}).status_code, 404)

    def test_financial_customer_and_ai_aggregation_stays_in_store(self):
        for index in range(3):
            dashboard = self.ok(index, "get", "/api/dashboard")
            self.assertEqual(dashboard["total_orders"], 1)
            finance = self.ok(index, "get", "/api/financial/daily")
            self.assertEqual(finance["cash"], 5)
            profile = self.ok(index, "get", f"/api/customers/{self.customers[index]}/profile")
            self.assertEqual(profile["summary"]["order_count"], 1)
            summary = self.ok(index, "get", f"/api/ai/customers/{self.customers[index]}/summary")
            self.assertEqual(summary["order_count"], 1)

    def test_superadmin_has_no_implicit_operational_aggregation(self):
        self.assertEqual([o["id"] for o in self.ok("super", "get", "/api/orders")["orders"]], [self.orders[0]["id"]])
        self.assertEqual(self.request("super", "get", "/api/orders/" + self.orders[1]["id"]).status_code, 404)

    def test_context_and_role_changes_cannot_escalate_store_manager(self):
        self.assertEqual(self.request(0, "put", "/api/context", {"brand_id": self.brand_a, "store_id": self.stores[1]}).status_code, 403)
        self.assertEqual(self.request(0, "put", f"/api/admin/staff/{self.users[0]}/roles", {"assignments": [{"role": "brand_admin", "scope_type": "brand", "brand_id": self.brand_a}]}).status_code, 403)
        self.assertEqual(self.request(0, "post", "/api/admin/staff", {"name": "Intruder"}).status_code, 403)
        staff = self.ok(0, "get", "/api/admin/staff")["staff"]
        self.assertTrue(all(s["location_id"] == self.stores[0] for s in staff))
        self.assertTrue(all("password_hash" not in s and "password_salt" not in s for s in staff))

    def test_missing_session_and_unselected_store_fail_closed(self):
        for path in ("/api/settings", "/api/services", "/api/offers", "/api/scheduling/availability", "/api/subscriptions/plans"):
            self.assertEqual(self.client.get(path).status_code, 401)
        uid = self.prefix + "-unset"
        with server.db() as conn:
            conn.execute("INSERT INTO staff_sessions (token,staff_id,active_brand_id) VALUES (%s,%s,%s)", (uid, self.users[0], self.brand_a))
        self.assertEqual(self.client.get("/api/orders", headers={"X-Session-Token": uid}).status_code, 409)

    def test_rls_applies_to_table_owner_and_missing_scope(self):
        token = current_scope.set(None)
        try:
            with server.db() as conn:
                for table in OWNED_TABLES:
                    with self.subTest(table=table):
                        self.assertEqual(conn.execute(sql.SQL("SELECT COUNT(*) AS n FROM {}").format(sql.Identifier(table))).fetchone()["n"], 0)
            current_scope.set((self.brand_a, self.stores[0]))
            with server.db() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"], 1)
                self.assertEqual(conn.execute("UPDATE orders SET payload=payload WHERE id=%s", (self.orders[1]["id"],)).rowcount, 0)
                with self.assertRaises(InsufficientPrivilege):
                    conn.execute("UPDATE customers SET business_id=%s WHERE id=%s", (self.brand_b, self.customers[0]))
                with self.assertRaises(ForeignKeyViolation):
                    conn.execute("INSERT INTO reward_transactions (id,customer_id,transaction_type,points) VALUES (%s,%s,'adjustment',1)", (uuid.uuid4().hex, self.customers[1]))
        finally:
            current_scope.reset(token)

    def test_parallel_request_contexts_do_not_bleed(self):
        def check(index):
            return [o["id"] for o in self.ok(index, "get", "/api/orders")["orders"]]
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(check, [0, 1, 2] * 3))
        self.assertEqual(results, [[self.orders[i]["id"]] for i in [0, 1, 2] * 3])


if __name__ == "__main__": unittest.main()

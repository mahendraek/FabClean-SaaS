"""Hierarchy and explicit same-brand custody tests on a disposable PostgreSQL DB."""
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg.errors import CheckViolation, ForeignKeyViolation, InsufficientPrivilege

import server
from store_operations import validate_hierarchy, next_handoff_status, work_manifest
from tenant_scope import current_scope


class StoreOperationsUnitTests(unittest.TestCase):
    def test_hierarchy_rejects_cycles_missing_and_inactive_ancestors(self):
        rows = {"a": {"id": "a", "active": True, "parent_store_id": "b"}, "b": {"id": "b", "active": True, "parent_store_id": None}}
        validate_hierarchy(rows, "c", "a")
        for parent in ("a", "missing"):
            with self.assertRaises(ValueError): validate_hierarchy(rows, "a", parent)
        with self.assertRaises(ValueError): validate_hierarchy(rows, "b", "a")
        rows["b"]["active"] = False
        with self.assertRaises(ValueError): validate_hierarchy(rows, "c", "a")

    def test_work_manifest_excludes_customer_financial_and_freeform_data(self):
        order = {"customer": {"phone": "secret"}, "total": 100, "notes": "secret", "items": [{"service_id": "private", "service_name": "Wash", "quantity": 2, "unit_price": 50, "notes": "secret"}]}
        manifest = work_manifest(order)
        self.assertEqual(manifest, [{"service_name": "Wash", "quantity": 2, "unit_label": "item", "barcode_value": None}])
        self.assertNotIn("secret", json.dumps(manifest))

    def test_transitions_enforce_custody_and_current_state(self):
        row = {"source_store_id": "a", "destination_store_id": "b", "status": "dispatched"}
        self.assertEqual(next_handoff_status(row, "receive", "b"), "received")
        with self.assertRaises(PermissionError): next_handoff_status(row, "receive", "a")
        with self.assertRaises(RuntimeError): next_handoff_status(row, "complete", "a")
        with self.assertRaises(ValueError): next_handoff_status(row, "invented", "a")


@unittest.skipUnless(os.getenv("FABCLEAN_TEST_DATABASE_URL"), "Set a disposable PostgreSQL test database")
class StoreOperationsAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_patch = patch.object(server, "DATABASE_URL", os.environ["FABCLEAN_TEST_DATABASE_URL"])
        cls.db_patch.start(); cls.addClassCleanup(cls.db_patch.stop)
        server.init_db(); server.init_db()
        cls.prefix = "pr5-" + uuid.uuid4().hex
        cls.brand, cls.foreign_brand = cls.prefix + "-brand", cls.prefix + "-foreign"
        cls.stores = [cls.prefix + "-" + suffix for suffix in ("source", "plant", "other", "foreign")]
        cls.tokens = {name: cls.prefix + "-token-" + name for name in ("source", "plant", "other", "foreign", "admin")}
        cls.users = {}
        with server.db(maintenance=True) as conn:
            for brand in (cls.brand, cls.foreign_brand):
                conn.execute("INSERT INTO brands(id,name,slug) VALUES (%s,%s,%s)", (brand, brand, brand))
            for index, store in enumerate(cls.stores):
                brand = cls.foreign_brand if index == 3 else cls.brand
                conn.execute("INSERT INTO stores(id,brand_id,store_code,name,store_type) VALUES (%s,%s,%s,%s,%s)", (store, brand, store, store, "central_plant" if index == 1 else "regular"))
            for index, name in enumerate(("source", "plant", "other", "foreign", "admin")):
                store_index = index if index < 4 else 0
                brand = cls.foreign_brand if name == "foreign" else cls.brand
                uid = cls.prefix + "-user-" + name; cls.users[name] = uid
                role = "brand_admin" if name == "admin" else "processing" if name == "plant" else "counter"
                conn.execute("INSERT INTO staff_users(id,name,email,role,business_id,location_id) VALUES (%s,%s,%s,'manager',%s,%s)", (uid, name, uid + "@example.com", brand, cls.stores[store_index]))
                conn.execute("INSERT INTO user_role_assignments(id,user_id,role,scope_type,brand_id,store_id) VALUES (%s,%s,%s,%s,%s,%s)", (uid + "-role", uid, role, "brand" if name == "admin" else "store", brand, None if name == "admin" else cls.stores[store_index]))
                conn.execute("INSERT INTO staff_sessions(token,staff_id,active_brand_id,active_store_id) VALUES (%s,%s,%s,%s)", (cls.tokens[name], uid, brand, cls.stores[store_index]))
        cls.client = TestClient(server.app); cls.addClassCleanup(cls.client.close)
        cls.ok("admin", "post", "/api/services", {"id": "wash", "category": "Laundry", "name": "Wash", "pricing_type": "per_item", "base_price": 5})

    @classmethod
    def request(cls, actor, method, path, payload=None):
        kwargs = {"headers": {"X-Session-Token": cls.tokens[actor]}}
        if payload is not None: kwargs["json"] = payload
        return getattr(cls.client, method)(path, **kwargs)

    @classmethod
    def ok(cls, actor, method, path, payload=None):
        response = cls.request(actor, method, path, payload)
        if response.status_code != 200: raise AssertionError(f"{method} {path}: {response.status_code} {response.text}")
        return response.json()

    def order(self):
        return self.ok("source", "post", "/api/orders", {"customer_name": "Private Customer", "customer_phone": "555-" + uuid.uuid4().hex, "notes": "Private note", "items": [{"service_id": "wash", "service_name": "Wash", "quantity": 2, "unit_price": 5}]})

    def dispatch(self, order=None):
        return self.ok("source", "post", "/api/handoffs", {"order_id": (order or self.order())["id"], "destination_store_id": self.stores[1], "notes": "Sealed bag"})

    def action(self, actor, handoff, action):
        return self.ok(actor, "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": action})

    def test_handoff_lifecycle_manifest_isolation_and_replays(self):
        order = self.order(); handoff = self.dispatch(order)
        try:
            self.assertEqual(self.request("source", "post", "/api/handoffs", {"order_id": order["id"], "destination_store_id": self.stores[2]}).status_code, 409)
            self.assertEqual(self.request("plant", "get", "/api/orders/" + order["id"]).status_code, 404)
            visible = self.ok("plant", "get", "/api/handoffs")["handoffs"]
            selected = next(row for row in visible if row["id"] == handoff["id"])
            for secret in ("Private Customer", order["customer"]["phone"], "Private note", "unit_price", "payment_status"):
                self.assertNotIn(secret, json.dumps(selected))
            for actor in ("other", "foreign"):
                self.assertNotIn(handoff["id"], [row["id"] for row in self.ok(actor, "get", "/api/handoffs")["handoffs"]])
                self.assertEqual(self.request(actor, "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": "receive"}).status_code, 404)
            self.assertEqual(self.request("source", "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": "receive"}).status_code, 403)
            self.action("plant", handoff, "receive")
            self.assertEqual(self.request("plant", "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": "receive"}).status_code, 409)
            self.action("plant", handoff, "return")
            done = self.action("source", handoff, "complete")
            self.assertEqual(done["status"], "completed")
            self.assertEqual([event["action"] for event in done["events"]], ["dispatch", "receive", "return", "complete"])
            self.assertEqual(self.ok("source", "get", "/api/orders/" + order["id"])["location_id"], self.stores[0])
            self.assertEqual(self.request("plant", "get", "/api/orders/" + order["id"]).status_code, 404)
        finally:
            with server.db() as conn:
                self.assertEqual(conn.execute("SELECT open_handoff_count FROM stores WHERE id=%s", (self.stores[0],)).fetchone()["open_handoff_count"], 0)

    def test_open_custody_blocks_order_item_changes_and_closure(self):
        order = self.order(); handoff = self.dispatch(order)
        try:
            self.assertEqual(self.request("source", "put", "/api/orders/" + order["id"], {"status": "cancelled"}).status_code, 409)
            self.assertEqual(self.request("source", "put", "/api/orders/" + order["id"], {"items": []}).status_code, 409)
            self.assertEqual(self.ok("source", "get", "/api/orders/" + order["id"])["items"], order["items"])
        finally: self.action("source", handoff, "cancel")
        self.assertEqual(self.ok("source", "put", "/api/orders/" + order["id"], {"status": "cancelled"})["status"], "cancelled")

    def test_cancel_retry_cross_brand_and_inactive_destinations(self):
        order = self.order()
        for destination in (self.stores[3], self.stores[0]):
            self.assertIn(self.request("source", "post", "/api/handoffs", {"order_id": order["id"], "destination_store_id": destination}).status_code, (400, 404))
        self.assertEqual(self.request("other", "post", "/api/handoffs", {"order_id": order["id"], "destination_store_id": self.stores[1]}).status_code, 404)
        inactive = self.ok("admin", "post", "/api/brand/stores", {"brand_id": self.brand, "name": "Inactive", "store_code": uuid.uuid4().hex, "active": False})
        self.assertEqual(self.request("source", "post", "/api/handoffs", {"order_id": order["id"], "destination_store_id": inactive["id"]}).status_code, 404)
        destinations = self.ok("source", "get", "/api/handoff-destinations")["stores"]
        self.assertNotIn(inactive["id"], [row["id"] for row in destinations])
        self.assertNotIn(self.stores[3], [row["id"] for row in destinations])
        handoff = self.dispatch(order); self.action("source", handoff, "cancel")
        self.assertEqual(self.request("source", "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": "cancel"}).status_code, 409)
        another = self.dispatch(order); self.action("source", another, "cancel")
        self.assertNotEqual(handoff["id"], another["id"])
        self.assertEqual(self.client.get("/api/handoffs").status_code, 401)

    def test_hierarchy_cycles_types_brand_and_deactivation_guards(self):
        hub = self.ok("admin", "post", "/api/brand/stores", {"brand_id": self.brand, "name": "Hub", "store_code": uuid.uuid4().hex, "store_type": "mother_store"})
        child = self.ok("admin", "post", "/api/brand/stores", {"brand_id": self.brand, "name": "Dropoff", "store_code": uuid.uuid4().hex, "store_type": "dropoff", "parent_store_id": hub["id"]})
        for payload in ({"parent_store_id": child["id"]}, {"parent_store_id": hub["id"]}, {"parent_store_id": self.stores[3]}, {"store_type": "invented"}, {"brand_id": self.foreign_brand}):
            self.assertEqual(self.request("admin", "put", "/api/brand/stores/" + hub["id"], payload).status_code, 400)
        self.assertEqual(self.request("admin", "put", "/api/brand/stores/" + hub["id"], {"active": False}).status_code, 409)
        self.assertEqual(self.request("source", "put", "/api/brand/stores/" + hub["id"], {"name": "Forged"}).status_code, 403)
        handoff = self.dispatch()
        try:
            # Brand administrator is selected at source, so this checks the
            # destination counter without broadening handoff RLS visibility.
            self.assertEqual(self.request("admin", "put", "/api/brand/stores/" + self.stores[1], {"active": False}).status_code, 409)
        finally: self.action("source", handoff, "cancel")
        self.ok("admin", "put", "/api/brand/stores/" + child["id"], {"active": False})
        self.ok("admin", "put", "/api/brand/stores/" + hub["id"], {"active": False})
        self.assertEqual(self.request("admin", "put", "/api/admin/staff/" + self.users["source"] + "/roles", {"assignments": [{"role": "counter", "scope_type": "store", "brand_id": self.brand, "store_id": child["id"]}]}).status_code, 400)

    def test_staff_assignments_allow_only_active_same_brand_stores(self):
        with server.db() as conn:
            uid = self.prefix + "-assigned-" + uuid.uuid4().hex
            conn.execute("INSERT INTO staff_users(id,name,email,role,business_id,location_id) VALUES (%s,'Assigned',%s,'counter',%s,%s)", (uid, uid + "@example.com", self.brand, self.stores[0]))
        path = "/api/admin/staff/" + uid + "/roles"
        assignment = {"role": "processing", "scope_type": "store", "brand_id": self.brand, "store_id": self.stores[1]}
        saved = self.ok("admin", "put", path, {"assignments": [assignment]})
        self.assertEqual(saved["assignments"][0]["store_id"], self.stores[1])
        self.assertEqual(self.request("admin", "put", path, {"assignments": [{**assignment, "store_id": self.stores[3]}]}).status_code, 400)
        self.assertEqual(self.request("source", "put", path, {"assignments": [assignment]}).status_code, 403)
        self.assertEqual(self.ok("admin", "get", path)["assignments"][0]["store_id"], self.stores[1])

    def test_parallel_parent_edits_cannot_create_cycle(self):
        stores = [self.ok("admin", "post", "/api/brand/stores", {"brand_id": self.brand, "name": "Concurrent", "store_code": uuid.uuid4().hex}) for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, "admin", "put", "/api/brand/stores/" + stores[i]["id"], {"parent_store_id": stores[1-i]["id"]}) for i in range(2)]
            self.assertEqual(sorted(f.result().status_code for f in futures), [200, 400])

    def test_parallel_dispatch_and_receipt_have_one_winner(self):
        order = self.order()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, "source", "post", "/api/handoffs", {"order_id": order["id"], "destination_store_id": self.stores[1]}) for _ in range(2)]
            responses = [f.result() for f in futures]
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        handoff = next(r.json() for r in responses if r.status_code == 200)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, "plant", "post", "/api/handoffs/" + handoff["id"] + "/actions", {"action": "receive"}) for _ in range(2)]
            self.assertEqual(sorted(f.result().status_code for f in futures), [200, 409])
        self.action("plant", handoff, "return"); self.action("source", handoff, "complete")

    def test_rls_database_constraints_and_immutable_history(self):
        order = self.order(); handoff = self.dispatch(order)
        try:
            for scope in (None, (self.foreign_brand, self.stores[3]), (self.brand, self.stores[2])):
                reset = current_scope.set(scope)
                try:
                    with server.db() as conn:
                        self.assertIsNone(conn.execute("SELECT id FROM store_handoffs WHERE id=%s", (handoff["id"],)).fetchone())
                finally: current_scope.reset(reset)
            reset = current_scope.set((self.brand, self.stores[1]))
            try:
                with server.db() as conn:
                    row = conn.execute("SELECT id FROM store_handoffs WHERE id=%s", (handoff["id"],)).fetchone()
                    self.assertEqual(row["id"], handoff["id"])
                    with self.assertRaises(CheckViolation): conn.execute("UPDATE store_handoffs SET manifest='[]'::jsonb WHERE id=%s", (handoff["id"],))
                    with self.assertRaises(CheckViolation): conn.execute("UPDATE store_handoffs SET status='received',events='[]'::jsonb WHERE id=%s", (handoff["id"],))
                    self.assertEqual(conn.execute("DELETE FROM store_handoffs WHERE id=%s", (handoff["id"],)).rowcount, 0)
            finally: current_scope.reset(reset)
            reset = current_scope.set((self.brand, self.stores[0]))
            try:
                with server.db() as conn:
                    with self.assertRaises(ForeignKeyViolation):
                        conn.execute("INSERT INTO store_handoffs(id,business_id,source_store_id,destination_store_id,order_id,order_number,source_name,destination_name,manifest,status,events) VALUES (%s,%s,%s,%s,%s,'X','Source','Dest','[]','dispatched','[]')", (uuid.uuid4().hex, self.brand, self.stores[0], self.stores[3], self.order()["id"]))
            finally: current_scope.reset(reset)
        finally: self.action("source", handoff, "cancel")

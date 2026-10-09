"""HTTP regressions for the in-memory workflow and per-request context."""
import copy
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
import server
from tenant_scope import current_scope


class MemoryIsolationAPITests(unittest.TestCase):
    def setUp(self):
        self.scope_token = current_scope.set(None)
        self.addCleanup(current_scope.reset, self.scope_token)
        self.original = (server.memory_customers.copy(), server.memory_orders.copy(), server.memory_payments[:], server.memory_garments.copy())
        self.maps = [server.memory_settings, server.memory_services, *server.memory_catalogs.values()]
        self.buckets = [copy.deepcopy(m.buckets) for m in self.maps]
        self.addCleanup(self.restore)
        self.prefix = uuid.uuid4().hex
        self.staff = {}
        for index in range(3):
            brand = self.prefix + ("-a" if index < 2 else "-b")
            store = self.prefix + "-store-" + str(index)
            self.staff[str(index)] = {"id": "user-" + str(index), "role": "manager", "business_id": brand, "location_id": store, "active_brand_id": brand, "active_store_id": store,
                                     "assignments": [{"role": "store_manager", "scope_type": "store", "brand_id": brand, "store_id": store}]}
        self.database_patch = patch.object(server, "DATABASE_URL", "")
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.auth_patch = patch.object(server, "get_current_staff", side_effect=lambda token: self.staff.get(token))
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.client = TestClient(server.app)
        self.addCleanup(self.client.close)
        self.orders = {}
        for index in range(3):
            self.ok(index, "put", "/api/settings", {"business_name": "Store " + str(index)})
            self.ok(index, "post", "/api/admin/categories", {"name": "Test"})
            self.ok(index, "post", "/api/services", {"id": "shared", "category": "Test", "name": "Wash", "pricing_type": "per_item"})
            self.orders[index] = self.ok(index, "post", "/api/orders", {"customer_name": "Test", "customer_phone": "555", "items": [{"service_id": "shared", "service_name": "Wash", "unit_price": 5}]})
            self.ok(index, "post", "/api/offers", {"name": "Offer", "code": "SHARED", "discount_type": "fixed", "discount_value": index + 1})

    def restore(self):
        for target, saved in ((server.memory_customers, self.original[0]), (server.memory_orders, self.original[1]), (server.memory_garments, self.original[3])):
            target.clear(); target.update(saved)
        server.memory_payments[:] = self.original[2]
        for mapping, buckets in zip(self.maps, self.buckets): mapping.buckets = buckets

    def request(self, index, method, path, data=None):
        kwargs = {"headers": {"X-Session-Token": str(index)}}
        if data is not None: kwargs["json"] = data
        return getattr(self.client, method)(path, **kwargs)

    def ok(self, index, method, path, data=None):
        result = self.request(index, method, path, data)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_settings_catalogs_customers_and_orders_are_isolated(self):
        for index in range(3):
            self.assertEqual(self.ok(index, "get", "/api/settings")["business_name"], "Store " + str(index))
            self.assertEqual(self.ok(index, "get", "/api/services")["services"][0]["location_id"], self.staff[str(index)]["location_id"])
            self.assertEqual([o["id"] for o in self.ok(index, "get", "/api/orders")["orders"]], [self.orders[index]["id"]])
            self.assertEqual([c["id"] for c in self.ok(index, "get", "/api/customers?q=555")["customers"]], [self.orders[index]["customer"]["id"]])
            self.assertEqual(self.ok(index, "post", "/api/offers/validate", {"code": "SHARED", "subtotal": 10})["discount"], index + 1)
        self.assertIsNone(current_scope.get())

    def test_cross_store_reads_and_updates_are_denied(self):
        for foreign in (1, 2):
            oid, cid = self.orders[foreign]["id"], self.orders[foreign]["customer"]["id"]
            self.assertEqual(self.request(0, "get", "/api/orders/" + oid).status_code, 404)
            self.assertEqual(self.request(0, "put", "/api/orders/" + oid, {"notes": "Intruder"}).status_code, 404)
            self.assertEqual(self.request(0, "get", "/api/customers/" + cid).status_code, 404)
            self.assertEqual(self.request(0, "post", "/api/notifications/prepare", {"order_id": oid}).status_code, 404)
            self.assertEqual(self.request(0, "post", "/api/ai/orders/" + oid + "/inspection-suggest", {}).status_code, 404)
            self.assertEqual(self.ok(foreign, "get", "/api/orders/" + oid)["notes"], "")

    def test_service_reference_cannot_use_another_store_catalog(self):
        self.ok(0, "post", "/api/services", {"id": "private", "category": "Test", "name": "Private", "pricing_type": "per_item"})
        self.assertEqual(self.request(1, "post", "/api/orders", {"customer_name": "Test", "customer_phone": "555", "items": [{"service_id": "private", "service_name": "Private", "unit_price": 5}]}).status_code, 404)

    def test_no_session_and_invalid_context_fail_closed(self):
        self.assertEqual(self.client.get("/api/services").status_code, 401)
        self.assertEqual(self.request("unknown", "get", "/api/orders").status_code, 401)
        self.staff["0"]["active_store_id"] = self.staff["1"]["active_store_id"]
        self.assertEqual(self.request(0, "get", "/api/orders").status_code, 403)


if __name__ == "__main__": unittest.main()

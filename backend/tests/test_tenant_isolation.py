"""Tenant isolation regression tests. Run: cd backend && python -m unittest discover -s tests."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import server
from models import Customer, OrderCreate


class TenantScopeTests(unittest.TestCase):
    def test_permissions_follow_selected_scope_not_legacy_role(self):
        staff = self.staff(superadmin=False)
        staff["active_store_id"] = "store-b"
        staff["assignments"].append({"role": "counter", "scope_type": "store", "brand_id": "brand-a", "store_id": "store-b"})
        self.assertIn("orders", server.effective_permissions(staff))
        self.assertNotIn("admin", server.effective_permissions(staff))

    def test_revoked_and_malformed_roles_do_not_restore_legacy_privileges(self):
        staff = self.staff()
        staff["assignments_loaded"] = True
        staff["assignments"] = []
        self.assertEqual(server.effective_permissions(staff), set())
        self.assertEqual(server.accessible_brand_ids(staff), set())
        staff["assignments"] = [{"role": "super_admin", "scope_type": "store", "brand_id": "brand-a", "store_id": "store-a"}]
        self.assertFalse(server.has_role(staff, "super_admin"))
        self.assertEqual(server.effective_permissions(staff), set())
        staff["assignments"] = [{"role": "super_admin", "scope_type": "platform", "active": False}]
        self.assertFalse(server.has_role(staff, "super_admin"))
        self.assertEqual(server.effective_permissions(staff), set())

    def setUp(self):
        self.saved_customers = server.memory_customers.copy()
        self.saved_orders = server.memory_orders.copy()
        self.saved_garments = server.memory_garments.copy()
        server.memory_customers.clear()
        server.memory_orders.clear()
        server.memory_garments.clear()
        self.addCleanup(self.restore_memory)

    def restore_memory(self):
        for target, saved in ((server.memory_customers, self.saved_customers),
                              (server.memory_orders, self.saved_orders),
                              (server.memory_garments, self.saved_garments)):
            target.clear()
            target.update(saved)

    def test_order_customer_uses_authorized_context_and_reuses_phone(self):
        staff = self.staff()
        payload = OrderCreate(customer_name="Test", customer_phone="5550100",
                              quick_dropoff=True, bag_count=1)
        with patch.object(server, "DATABASE_URL", ""), patch.object(server, "get_current_staff", return_value=staff):
            first = server.create_order(payload, "test-session")
            second = server.create_order(payload, "test-session")
        self.assertEqual(first.customer.business_id, "brand-a")
        self.assertEqual(first.customer.location_id, "store-a")
        self.assertEqual(first.customer.id, second.customer.id)
        self.assertEqual(len(server.memory_customers), 1)

    def test_same_phone_in_other_brand_is_not_reused(self):
        foreign = Customer(id="foreign", name="Foreign", phone="5550100", business_id="brand-b")
        server.memory_customers[foreign.id] = foreign
        payload = OrderCreate(customer_name="Test", customer_phone=foreign.phone,
                              quick_dropoff=True, bag_count=1)
        with patch.object(server, "DATABASE_URL", ""), patch.object(server, "get_current_staff", return_value=self.staff()):
            order = server.create_order(payload, "test-session")
            with self.assertRaises(HTTPException) as ctx:
                server.create_order(payload.model_copy(update={"customer_id": foreign.id}), "test-session")
        self.assertNotEqual(order.customer.id, foreign.id)
        self.assertEqual(order.customer.business_id, "brand-a")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_customer_metrics_exclude_other_tenant_and_unowned_orders(self):
        orders = [
            {"business_id": "brand-a", "location_id": "store-a", "customer": {"id": "customer-a", "phone": "555"}, "total": 5},
            {"business_id": "brand-a", "location_id": "store-b", "customer": {"id": "customer-a", "phone": "555"}, "total": 50},
            {"business_id": "brand-b", "customer": {"id": "customer-b", "phone": "555"}, "total": 100},
            {"customer": {"id": "customer-a", "phone": "555"}, "total": 200},
        ]
        with patch.object(server, "get_order_values", return_value=orders), patch.object(server, "capability_enabled", return_value=False):
            metrics = server.customer_metrics("customer-a", "555", "brand-a", "store-a")
            unset = server.customer_metrics("customer-a", "555")
        self.assertEqual(metrics["order_count"], 1)
        self.assertEqual(metrics["lifetime_value"], 5)
        self.assertEqual(unset["order_count"], 0)

    def test_customer_profile_excludes_other_store_orders(self):
        orders = [
            {"id": "allowed", "business_id": "brand-a", "location_id": "store-a", "customer": {"id": "customer-a"}, "total": 5},
            {"id": "foreign-store", "business_id": "brand-a", "location_id": "store-b", "customer": {"id": "customer-a"}, "total": 100},
        ]
        with patch.object(server, "DATABASE_URL", ""), patch.object(server, "get_current_staff", return_value=self.staff()), patch.object(server, "get_customer", return_value={"id": "customer-a"}), patch.object(server, "get_order_values", return_value=orders), patch.object(server, "customer_rewards", return_value={}), patch.object(server, "customer_referrals", return_value={}):
            profile = server.get_customer_profile("customer-a", "test-session")
        self.assertEqual([o["id"] for o in profile["orders"]], ["allowed"])
        self.assertEqual(profile["summary"]["lifetime_value"], 5)

    def test_customer_payments_exclude_other_store_orders(self):
        orders = [
            {"id": "allowed", "business_id": "brand-a", "location_id": "store-a"},
            {"id": "foreign-store", "business_id": "brand-a", "location_id": "store-b"},
        ]
        payments = [{"customer_id": "customer-a", "order_id": o["id"]} for o in orders]
        with patch.object(server, "DATABASE_URL", ""), patch.object(server, "get_current_staff", return_value=self.staff()), patch.object(server, "get_customer", return_value={"id": "customer-a"}), patch.object(server, "get_order_values", return_value=orders), patch.object(server, "memory_payments", payments):
            history = server.customer_payment_history("customer-a", "test-session")
        self.assertEqual([p["order_id"] for p in history["payments"]], ["allowed"])

    def staff(self, brand="brand-a", store="store-a", superadmin=True):
        assignments = [{"role": "super_admin", "scope_type": "platform", "brand_id": None, "store_id": None}] if superadmin else [
            {"role": "store_manager", "scope_type": "store", "brand_id": brand, "store_id": store}
        ]
        return {"id": "user-a", "role": "manager", "business_id": brand, "location_id": store,
                "active_brand_id": brand, "active_store_id": store, "assignments": assignments}

    def test_order_scope_exact_match(self):
        row = {"business_id": "brand-a", "location_id": "store-a"}
        self.assertTrue(server.order_in_scope(row, "brand-a", "store-a"))
        self.assertFalse(server.order_in_scope(row, "brand-b", "store-a"))
        self.assertFalse(server.order_in_scope(row, "brand-a", "store-b"))
        self.assertFalse(server.order_in_scope({}, "brand-a", "store-a"))

    def test_unset_store_fails_closed(self):
        staff = self.staff()
        staff["active_store_id"] = None
        with patch.object(server, "DATABASE_URL", "postgres://unused"):
            with self.assertRaises(HTTPException) as ctx:
                server.operational_scope(staff)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_role_denied_other_brand(self):
        staff = self.staff(superadmin=False)
        staff["active_brand_id"] = "brand-b"
        with patch.object(server, "DATABASE_URL", ""):
            with self.assertRaises(HTTPException) as ctx:
                server.operational_scope(staff)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_role_denied_other_store(self):
        staff = self.staff(superadmin=False)
        staff["active_store_id"] = "store-b"
        with patch.object(server, "DATABASE_URL", ""):
            with self.assertRaises(HTTPException) as ctx:
                server.operational_scope(staff)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

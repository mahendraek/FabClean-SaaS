"""Tenant isolation regression tests. Run: cd backend && python -m unittest discover -s tests."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import server


class TenantScopeTests(unittest.TestCase):
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

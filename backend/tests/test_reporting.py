"""Reconciliation and authorization against real forced-RLS PostgreSQL."""
import csv
import io
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
import reporting
import server
from tests import test_postgres_isolation as fixtures
from tenant_scope import current_scope


class ReportingUnitTests(unittest.TestCase):
    def test_timezone_bounds_include_dst_short_day(self):
        _, _, lower, upper = reporting.date_range('2026-03-08', '2026-03-08', 'America/Chicago', datetime.now(timezone.utc))
        self.assertEqual((upper - lower).total_seconds(), 23 * 3600)
        self.assertEqual(lower.hour, 6)
        self.assertEqual(upper.hour, 5)
        for start, end in [('2026-02-30', '2026-03-01'), ('2026-02-02', '2026-02-01'), ('2020-01-01', '2026-01-01')]:
            with self.assertRaises(HTTPException):
                reporting.date_range(start, end, 'America/Chicago', datetime.now(timezone.utc))

    def test_untrusted_csv_cells_and_invalid_money(self):
        for value in ['=SUM(A1)', '  +formula', '-formula', '@formula', '\ttab']:
            self.assertTrue(reporting.cell(value).startswith("'"))
        self.assertEqual(reporting.cell('Normal Laundry'), 'Normal Laundry')
        for value in ['NaN', 'Infinity', None, 'invalid']:
            with self.assertRaises(HTTPException):
                reporting.money(value)
        self.assertEqual(str(reporting.money('1.005')), '1.01')


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'), 'Disposable PostgreSQL required')
class ReportingPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f = cls.f = fixtures.PostgresIsolationTests
        f.setUpClass()
        cls.addClassCleanup(f.doClassCleanups)
        with server.db(maintenance=True) as conn:
            conn.execute("INSERT INTO user_role_assignments(id,user_id,role,scope_type,brand_id) VALUES (%s,%s,'brand_admin','brand',%s)", (f.prefix + '-brand-admin', f.users[0], f.brand_a))
            conn.execute("UPDATE stores SET name=%s WHERE id=%s", ('=Unsafe store', f.stores[1]))
            for index in range(3):
                oid = f.orders[index]['id']
                # The cohort is March 8 in Chicago, the DST transition day.
                conn.execute("UPDATE orders SET created_at='2026-03-08T07:00:00Z',payload=payload || %s::jsonb WHERE id=%s", ('{"currency":"' + ('USD' if index != 1 else 'INR') + '","status":"completed","pricing_status":"final"}', oid))
                conn.execute("UPDATE payment_transactions SET created_at='2026-03-08T09:00:00Z' WHERE order_id=%s", (oid,))
                conn.execute("DELETE FROM order_events WHERE order_id=%s", (oid,))
                conn.execute("INSERT INTO order_events(id,order_id,event_type,to_value,created_at,business_id,location_id) VALUES (%s,%s,'status_changed','ready_for_pickup',%s,%s,%s)", (f.prefix + '-event-' + str(index), oid, '2026-03-08T' + ('09' if index != 1 else '11') + ':00:00Z', f.brand_a if index < 2 else f.brand_b, f.stores[index]))
        cls.query = '?from_date=2026-03-08&to_date=2026-03-08'

    def get(self, index, path, suffix=''):
        return self.f.request(index, 'get', '/api/reports/' + path + self.query + suffix)

    def test_brand_rollup_reconciles_to_stores_and_csv(self):
        r = self.get(0, 'summary', '&scope=brand')
        self.assertEqual(r.status_code, 200, r.text)
        report = r.json()
        self.assertEqual(report['metrics']['orders'], 2)
        self.assertEqual(report['metrics']['average_turnaround_hours'], 3)
        self.assertEqual({v['currency'] for v in report['currencies']}, {'USD', 'INR'})
        for currency in report['currencies']:
            self.assertEqual(currency['order_value'], '10.00')
            self.assertEqual(currency['paid_on_orders'], '5.00')
            self.assertEqual(currency['net_collected'], '5.00')
            self.assertEqual(currency['outstanding'], '5.00')
        self.assertEqual(sum(st['metrics']['orders'] for st in report['by_store']), report['metrics']['orders'])
        csv_response = self.get(0, 'export', '&scope=brand')
        self.assertEqual(csv_response.status_code, 200, csv_response.text)
        self.assertEqual(csv_response.headers['cache-control'], 'no-store')
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['Store ID'] for r in rows}, set(self.f.stores[:2]))
        self.assertTrue(next(r['Store'] for r in rows if r['Store ID'] == self.f.stores[1]).startswith("'="))
        self.assertEqual(sum(float(r['Order value']) for r in rows), 20)
        self.assertNotIn('Customer', csv_response.text)

    def test_manager_and_foreign_brand_denials_cover_all_endpoints(self):
        f = self.f
        for path in ('summary', 'orders', 'export'):
            self.assertEqual(self.get(1, path, '&scope=brand').status_code, 403)
            self.assertEqual(self.get(1, path, '&store_id=' + f.stores[0]).status_code, 404)
            self.assertEqual(self.get(0, path, '&scope=brand&store_id=' + f.stores[2]).status_code, 404)
            self.assertEqual(f.client.get('/api/reports/' + path).status_code, 401)
        self.assertEqual(len(f.ok(1, 'get', '/api/reports/options')['stores']), 1)
        self.assertEqual(self.get(1, 'summary').json()['metrics']['orders'], 1)
        self.assertEqual(self.get('super', 'summary', '&scope=brand').json()['metrics']['orders'], 2)

    def test_status_pagination_empty_and_limits(self):
        self.assertEqual(self.get(0, 'summary', '&scope=brand&status=cancelled').json()['metrics']['orders'], 0)
        detail = self.get(0, 'orders', '&scope=brand&limit=1&offset=1').json()
        self.assertEqual(detail['total'], 2)
        self.assertEqual(len(detail['orders']), 1)
        self.assertEqual(self.get(0, 'summary', '&status=forged').status_code, 400)
        self.assertEqual(self.get(0, 'orders', '&limit=10000').status_code, 422)
        with patch.object(reporting, 'MAX_ORDERS', 1):
            self.assertEqual(self.get(0, 'summary', '&scope=brand').status_code, 413)
        # No RLS connection settings leak on either success or failure.
        for index in range(3):
            self.assertEqual([o['id'] for o in self.f.ok(index, 'get', '/api/orders')['orders']], [self.f.orders[index]['id']])
        self.assertIsNone(current_scope.get())

    def test_cashflow_is_not_limited_to_order_creation_window(self):
        f = self.f
        oid = f.orders[1]['id']
        with server.db(maintenance=True) as conn:
            conn.execute("UPDATE orders SET created_at='2026-03-07T07:00:00Z' WHERE id=%s", (oid,))
        try:
            report = self.get(0, 'summary', '&scope=brand').json()
            self.assertEqual(report['metrics']['orders'], 1)
            cash_only = next(c for c in report['currencies'] if c['currency'] == 'INR')
            self.assertEqual(cash_only['orders'], 0)
            self.assertEqual(cash_only['net_collected'], '5.00')
            self.assertEqual(cash_only['order_value'], '0.00')
        finally:
            with server.db(maintenance=True) as conn:
                conn.execute("UPDATE orders SET created_at='2026-03-08T07:00:00Z' WHERE id=%s", (oid,))

    def test_refunds_adjustments_unknown_currency_and_lifetime_balances(self):
        f = self.f
        oid = f.orders[0]['id']
        marker = current_scope.set((f.brand_a, f.stores[0]))
        try:
            with server.db() as conn:
                conn.execute("UPDATE orders SET payload=payload - 'currency' - 'tax_snapshot' WHERE id=%s", (oid,))
                for kind, amount, expected_refund, expected_adjustment in [('refund', -5, '5.00', '0.00'), ('adjustment', 5, '0.00', '5.00')]:
                    conn.execute("UPDATE payment_transactions SET transaction_type=%s,amount=%s WHERE order_id=%s", (kind, amount, oid))
                    c = self.get(0, 'summary').json()['currencies'][0]
                    self.assertEqual(c['currency'], 'UNSPECIFIED')
                    self.assertEqual(c['refunds'], expected_refund)
                    self.assertEqual(c['adjustments'], expected_adjustment)
                    self.assertEqual(c['net_collected'], str(reporting.money(amount)))
                    self.assertEqual(c['net_collected'], c['payment_methods']['cash'])
                conn.execute("UPDATE payment_transactions SET created_at='2026-03-10T09:00:00Z',transaction_type='payment' WHERE order_id=%s", (oid,))
                c = self.get(0, 'summary').json()['currencies'][0]
                self.assertEqual(c['paid_on_orders'], '5.00')
                self.assertEqual(c['net_collected'], '0.00')
        finally:
            with server.db() as conn:
                conn.execute("UPDATE orders SET payload=payload || '{\"currency\":\"USD\"}'::jsonb WHERE id=%s", (oid,))
                conn.execute("UPDATE payment_transactions SET transaction_type='payment',amount=5,created_at='2026-03-08T09:00:00Z' WHERE order_id=%s", (oid,))
            current_scope.reset(marker)

    def test_revocation_and_non_admin_roles_fail_closed(self):
        f = self.f
        with server.db() as conn:
            conn.execute('UPDATE user_role_assignments SET active=FALSE WHERE user_id=%s', (f.users[0],))
        try:
            for endpoint in ('options', 'summary', 'orders', 'export'):
                self.assertEqual(self.get(0, endpoint, '&scope=brand').status_code, 403)
        finally:
            with server.db() as conn:
                conn.execute('UPDATE user_role_assignments SET active=TRUE WHERE user_id=%s', (f.users[0],))
        with server.db() as conn:
            conn.execute("UPDATE user_role_assignments SET role='counter' WHERE user_id=%s", (f.users[1],))
        try:
            for endpoint in ('options', 'summary', 'orders', 'export'):
                self.assertEqual(self.get(1, endpoint).status_code, 403)
        finally:
            with server.db() as conn:
                conn.execute("UPDATE user_role_assignments SET role='store_manager' WHERE user_id=%s", (f.users[1],))

    def test_exact_timezone_boundary_and_export_operational_metrics(self):
        f = self.f
        oid = f.orders[1]['id']
        with server.db(maintenance=True) as conn:
            conn.execute("UPDATE orders SET created_at='2026-03-09T05:00:00Z' WHERE id=%s", (oid,))
        try:
            self.assertEqual(self.get(0, 'summary', '&scope=brand').json()['metrics']['orders'], 1)
        finally:
            with server.db(maintenance=True) as conn:
                conn.execute("UPDATE orders SET created_at='2026-03-08T07:00:00Z' WHERE id=%s", (oid,))
        result = self.get(0, 'export', '&scope=brand&dataset=summary')
        self.assertEqual(result.status_code, 200, result.text)
        rows = list(csv.DictReader(io.StringIO(result.text)))
        selected = [r for r in rows if r['Scope'] == 'Selected stores']
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(r['Average Turnaround Hours (all currencies)'] == '3.0' for r in selected))
        self.assertEqual(self.get(0, 'export', '&dataset=forged').status_code, 400)

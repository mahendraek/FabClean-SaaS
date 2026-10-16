"""Opt-in tax calculation, immutable invoice evidence and forced-RLS API checks."""
import copy
import csv
import io
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from psycopg.errors import RaiseException
import taxation as tax
import server
from tenant_scope import current_scope
from tests import test_postgres_isolation as fixtures


def policy(day='2026-10-16', mode='exclusive'):
    return {'enabled': True, 'pricing_mode': mode, 'components': [{'name': 'Synthetic state component', 'rate': '5'}, {'name': 'Synthetic local component', 'rate': '2.5'}], 'services': {'shared-service': 'taxable', 'exempt-service': 'exempt'}, 'delivery_fee_taxable': False, 'effective_on': day, 'source_note': 'Synthetic test rates; not jurisdiction guidance'}


class TaxCalculationTests(unittest.TestCase):
    def quote(self, items=None, discount=0, fee=0, mode='exclusive'):
        return tax.calculate(items or [{'service_id': 'shared-service', 'unit_price': 10, 'quantity': 1}], discount, fee, policy(mode=mode), {}, 'USD', 'test-policy')

    def test_exclusive_and_inclusive_totals_reconcile(self):
        result = self.quote()
        self.assertEqual(result['tax'], .75)
        self.assertEqual(result['total'], 10.75)
        included = self.quote(mode='inclusive')
        self.assertEqual(included['total'], 10)
        self.assertEqual(included['tax'], .70)
        self.assertEqual(included['tax_snapshot']['lines'][0]['taxable_base'], 9.30)
        for result in [result, included]:
            self.assertEqual(sum(Decimal(str(b['amount'])) for b in result['tax_snapshot']['breakdown']), Decimal(str(result['tax'])))
            self.assertEqual(sum(Decimal(str(l['total'])) for l in result['tax_snapshot']['lines']), Decimal(str(result['total'])))

    def test_discount_cents_allocate_once_and_exempt_fees_stay_untaxed(self):
        items = [{'service_id': 'shared-service', 'quantity': 1, 'unit_price': 100}, {'service_id': 'exempt-service', 'quantity': 1, 'unit_price': 100}]
        result = self.quote(items, discount=33.33, fee=5)
        self.assertEqual(result['tax'], 6.25)
        self.assertEqual(result['total'], 177.92)
        lines = result['tax_snapshot']['lines']
        self.assertEqual([l['discount'] for l in lines], [16.67, 16.66, 0])
        self.assertEqual([l['tax'] for l in lines], [6.25, 0, 0])
        self.assertEqual(tax.allocate(Decimal('.01'), [Decimal(1), Decimal(1)]), [Decimal('.01'), Decimal(0)])

    def test_unknown_services_and_invalid_rates_are_rejected(self):
        with self.assertRaises(HTTPException):
            self.quote([{'service_id': 'unknown', 'unit_price': 10}])
        loc = {'country': 'US', 'state': 'IL', 'postal_code': '60601', 'timezone': 'UTC'}
        for rate in ['NaN', '-1', '101', '1.12345', True]:
            p = policy(day=tax.today(loc).isoformat());p['components'][0]['rate'] = rate
            with self.subTest(rate=rate), self.assertRaises(HTTPException):
                tax.validate_policy(p, {'shared-service', 'exempt-service'}, loc)

    def test_partial_refund_credits_are_nonnegative_capped_and_exhaust_original_tax(self):
        quote = self.quote();order = {**quote};rows=[]
        for amount in ['0.01'] * 25 + ['10.50']:
            credit, breakdown = tax.refund_credit(order, rows, Decimal(amount))
            self.assertTrue(all(Decimal(str(b['amount'])) >= 0 for b in breakdown))
            self.assertEqual(sum(Decimal(str(b['amount'])) for b in breakdown), Decimal(str(credit)))
            rows.append({'transaction_type': 'refund', 'amount': -Decimal(amount), 'tax_amount': credit, 'tax_breakdown': breakdown})
        self.assertEqual(sum(Decimal(str(r['tax_amount'])) for r in rows), Decimal('.75'))
        for b in order['tax_snapshot']['breakdown']:
            self.assertEqual(sum(Decimal(str(v['amount'])) for r in rows for v in r['tax_breakdown'] if v['jurisdiction'] == b['jurisdiction']), Decimal(str(b['amount'])))


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'), 'Disposable PostgreSQL required')
class StoreTaxAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
        with server.db() as conn:
            for store in cls.f.stores:
                conn.execute("UPDATE stores SET country='US',state='IL',postal_code='60601',timezone='America/Chicago' WHERE id=%s", (store,))
        cls.f.ok(0, 'post', '/api/services', {'id': 'exempt-service', 'category': 'Test', 'name': 'Synthetic exempt service', 'pricing_type': 'per_item', 'base_price': 10})

    def setUp(self):
        self.publish(enabled=False)

    def publish(self, **changes):
        cfg = self.f.ok(0, 'get', '/api/taxes/policy')
        p = {**policy(cfg['today']), **changes}
        return self.f.ok(0, 'post', '/api/taxes/policy', {'expected_revision': cfg['revision'], 'policy': p})

    def order(self, **changes):
        return self.f.ok(0, 'post', '/api/orders', {'customer_name': 'Tax fixture', 'customer_phone': uuid4().hex, 'items': [{'service_id': 'shared-service', 'service_name': 'Synthetic taxable wash', 'quantity': 1, 'unit_price': 10}], **changes})

    def test_disabled_default_and_no_legacy_reactivation(self):
        order = self.order(tax=999, tax_snapshot={'tax': 999})
        self.assertEqual(order['tax'], 0)
        self.assertIsNone(order['tax_snapshot'])
        self.assertEqual(order['total'], 10)
        self.assertIsNone(self.f.ok(1, 'get', '/api/taxes/policy')['active'])
        self.assertEqual(self.f.ok(1, 'get', '/api/taxes/policy')['revision'], 0)

    def test_estimate_invoice_receipt_and_print_snapshot_reconcile(self):
        self.publish()
        body = {'items': [{'service_id': 'shared-service', 'quantity': 1, 'unit_price': 10}], 'discount': 2}
        estimate = self.f.ok(0, 'post', '/api/taxes/estimate', body)
        order = self.order(discount=2)
        self.assertEqual((estimate['tax'], estimate['total']), (.6, 8.6))
        self.assertEqual(order['tax'], estimate['tax'])
        self.assertEqual(order['total'], estimate['total'])
        receipt = self.f.ok(0, 'get', '/api/orders/' + order['id'] + '/print-preview')['receipt']
        self.assertEqual(receipt['order']['tax_snapshot'], order['tax_snapshot'])
        self.assertEqual(receipt['balance_due'], 8.6)
        self.assertEqual(self.f.request(2, 'get', '/api/orders/' + order['id']).status_code, 404)

    def test_frozen_policy_repricing_and_paid_invoice_guard(self):
        original = self.publish()
        order = self.order()
        self.publish(components=[{'name': 'New synthetic rate', 'rate': '20'}])
        changed = self.f.ok(0, 'put', '/api/orders/' + order['id'], {'discount': 2})
        self.assertEqual(changed['tax'], .6)
        self.assertEqual(changed['tax_snapshot']['policy_id'], original['id'])
        self.f.ok(0, 'post', '/api/orders/' + order['id'] + '/payments', {'amount': 1})
        self.assertEqual(self.f.request(0, 'put', '/api/orders/' + order['id'], {'discount': 1}).status_code, 409)
        self.assertEqual(self.order()['tax'], 2)

    def test_refund_tax_credits_reconcile_and_report_exports_match(self):
        self.publish();order = self.order();path = '/api/orders/' + order['id'] + '/payments'
        self.f.ok(0, 'post', path, {'amount': order['total']})
        credits=[]
        for amount in [3, 3, 4.75]:
            credits.append(self.f.ok(0, 'post', path, {'amount': amount, 'transaction_type': 'refund'})['payment']['tax_amount'])
        self.assertEqual(sum(Decimal(str(v)) for v in credits), Decimal('.75'))
        self.assertEqual(self.f.request(0, 'post', path, {'amount': .01, 'transaction_type': 'refund'}).status_code, 409)
        report = self.f.ok(0, 'get', '/api/taxes/report')
        csv_response = self.f.request(0, 'get', '/api/taxes/report?format=csv')
        self.assertEqual(csv_response.status_code, 200)
        exported = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual(exported, [{**{k: str(v) for k, v in g.items()}, 'from_date': report['from_date'], 'to_date': report['to_date'], 'timezone': report['timezone'], 'generated_at': exported[i]['generated_at']} for i, g in enumerate(report['currencies'])])

    def test_scope_permissions_expected_revision_history_and_scheduling(self):
        cfg = self.f.ok(0, 'get', '/api/taxes/policy')
        p = policy(cfg['today'])
        self.assertEqual(self.f.request(0, 'post', '/api/taxes/policy', {'expected_revision': cfg['revision'] - 1, 'policy': p}).status_code, 409)
        future = (date.fromisoformat(cfg['today']) + timedelta(days=1)).isoformat()
        self.publish(effective_on=future)
        self.assertEqual(self.order()['tax'], 0)
        self.publish()
        self.assertEqual(self.f.ok(1, 'get', '/api/taxes/policy')['versions'], [])
        for path in ['/api/taxes/policy', '/api/taxes/report']:
            self.assertEqual(self.f.client.get(path).status_code, 401)
        with server.db() as conn:
            conn.execute("UPDATE user_role_assignments SET role='counter' WHERE user_id=%s", (self.f.users[1],))
        try:
            self.assertEqual(self.f.request(1, 'get', '/api/taxes/policy').status_code, 403)
            self.assertEqual(self.f.request(1, 'get', '/api/taxes/report').status_code, 403)
            self.assertEqual(self.f.request(1, 'post', '/api/taxes/estimate', {'items': []}).status_code, 200)
        finally:
            with server.db() as conn:
                conn.execute("UPDATE user_role_assignments SET role='store_manager' WHERE user_id=%s", (self.f.users[1],))
        marker = current_scope.set((self.f.brand_a, self.f.stores[0]))
        try:
            with self.assertRaises(RaiseException):
                with server.db() as conn:
                    conn.execute("UPDATE store_tax_policy_versions_v2 SET effective_on=CURRENT_DATE")
        finally:
            current_scope.reset(marker)

    def test_location_change_and_unclassified_service_fail_closed(self):
        self.publish(services={})
        self.assertEqual(self.f.request(0, 'post', '/api/taxes/estimate', {'items': [{'service_id': 'shared-service', 'quantity': 1, 'unit_price': 10}]}).status_code, 409)
        self.publish()
        with server.db() as conn:
            conn.execute("UPDATE stores SET postal_code='60000' WHERE id=%s", (self.f.stores[0],))
        try:
            self.assertEqual(self.f.request(0, 'post', '/api/taxes/estimate', {'items': []}).status_code, 409)
        finally:
            with server.db() as conn:
                conn.execute("UPDATE stores SET postal_code='60601' WHERE id=%s", (self.f.stores[0],))
        for items in [None, {}, [1]]:
            self.assertEqual(self.f.request(0, 'post', '/api/taxes/estimate', {'items': items}).status_code, 400)

    def test_old_untaxed_orders_are_not_retroactively_taxed(self):
        order = self.order()
        self.publish()
        edited = self.f.ok(0, 'put', '/api/orders/' + order['id'], {'discount': 1})
        self.assertEqual((edited['tax'], edited['total'], edited['tax_snapshot']), (0, 9, None))
        preview = self.f.ok(0, 'post', '/api/orders/' + order['id'] + '/tax-estimate', {'items': order['items']})
        self.assertEqual(preview['tax'], 0)

    def test_frozen_estimate_and_concurrent_refund_tax_limits(self):
        self.publish();order = self.order();path = '/api/orders/' + order['id']
        self.publish(components=[{'name': 'Another synthetic rate', 'rate': '15'}])
        estimate = self.f.ok(0, 'post', path + '/tax-estimate', {'discount': 2})
        self.assertEqual(estimate['tax'], .6)
        self.assertEqual(self.f.request(2, 'post', path + '/tax-estimate', {}).status_code, 404)
        self.f.ok(0, 'post', path + '/payments', {'amount': order['total']})
        self.assertEqual(self.f.request(0, 'post', path + '/tax-estimate', {'discount': 1}).status_code, 409)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.f.request(0, 'post', path + '/payments', {'amount': 8, 'transaction_type': 'refund', 'tax_amount': 999}), range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        refund = next(r.json()['payment'] for r in responses if r.status_code == 200)
        self.assertEqual(refund['tax_amount'], .56)
        final = self.f.ok(0, 'post', path + '/payments', {'amount': 2.75, 'transaction_type': 'refund'})
        self.assertEqual(final['payment']['tax_amount'], .19)

    def test_referral_collision_in_another_store_does_not_abort_order_support(self):
        from psycopg.errors import UniqueViolation
        prefix = uuid4().hex[:6]
        codes=[]
        for index in [0, 2]:
            marker = current_scope.set((self.f.brand_a if index == 0 else self.f.brand_b, self.f.stores[index]))
            try:
                cid = prefix + '-' + uuid4().hex
                with server.db() as conn:
                    conn.execute('INSERT INTO customers(id,name,phone) VALUES (%s,%s,%s)', (cid, 'Synthetic collision fixture', cid))
                try:
                    codes.append(server.get_or_create_referral_code(cid))
                except UniqueViolation as exc:
                    self.fail('A hidden-store referral collision aborted creation: ' + exc.diag.constraint_name)
            finally:
                current_scope.reset(marker)
        self.assertNotEqual(codes[0], codes[1])

    def test_policy_table_forces_scope_and_rejects_foreign_store_relationships(self):
        from psycopg.errors import ForeignKeyViolation, InsufficientPrivilege
        self.publish()
        marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
        try:
            with server.db() as conn:
                settings=conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='store_tax_policy_versions_v2'::regclass").fetchone()
                self.assertTrue(settings['relrowsecurity']);self.assertTrue(settings['relforcerowsecurity'])
                self.assertEqual(conn.execute('SELECT id FROM store_tax_policy_versions_v2 WHERE business_id=%s',(self.f.brand_b,)).fetchall(),[])
            params=(str(uuid4()),self.f.brand_a,self.f.stores[2],999999,tax.today({'timezone':'UTC'}),self.f.users[0])
            sql="INSERT INTO store_tax_policy_versions_v2(id,business_id,location_id,revision,effective_on,policy,created_by) VALUES (%s,%s,%s,%s,%s,'{}'::jsonb,%s)"
            with self.assertRaises(InsufficientPrivilege):
                with server.db() as conn:conn.execute(sql,params)
            with self.assertRaises(ForeignKeyViolation):
                with server.db(maintenance=True) as conn:conn.execute(sql,params)
            with self.assertRaises(RaiseException):
                with server.db() as conn:conn.execute('DELETE FROM store_tax_policy_versions_v2')
        finally:current_scope.reset(marker)

    def test_legacy_zero_default_refund_is_explicitly_unclassified(self):
        before=self.f.ok(0,'get','/api/taxes/report')['currencies']
        old=next((g['unclassified_refunds'] for g in before if g['currency']=='USD'),0)
        order=self.order()
        marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
        try:
            with server.db() as conn:
                conn.execute("UPDATE orders SET payload=payload||'{\"tax\":1,\"total\":11,\"tax_snapshot\":{\"currency\":\"USD\"}}'::jsonb WHERE id=%s",(order['id'],))
            self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':11})
            payment=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':5,'transaction_type':'refund'})['payment']
            with server.db() as conn:
                conn.execute("UPDATE payment_transactions SET tax_amount=0,tax_breakdown='[]'::jsonb WHERE id=%s",(payment['id'],))
        finally:current_scope.reset(marker)
        result=self.f.ok(0,'get','/api/taxes/report')['currencies']
        usd=next(g for g in result if g['currency']=='USD')
        self.assertEqual(usd['unclassified_refunds'],old+1)
        self.assertGreaterEqual(usd['unclassified_tax_bases'],1)

    def test_parallel_referral_lookup_keeps_one_code_for_one_customer(self):
        marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
        cid=uuid4().hex
        try:
            with server.db() as conn:
                conn.execute('INSERT INTO customers(id,name,phone) VALUES (%s,%s,%s)',(cid,'Synthetic concurrent fixture',cid))
        finally:current_scope.reset(marker)
        def lookup(_):
            marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
            try:return server.get_or_create_referral_code(cid)
            finally:current_scope.reset(marker)
        with ThreadPoolExecutor(max_workers=3) as pool:
            codes=list(pool.map(lookup,range(3)))
        self.assertEqual(len(set(codes)),1)

import json
import os
import unittest
import uuid
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

import pricing
import server
from tests import test_postgres_isolation as fixtures


class PricingTests(unittest.TestCase):
    def test_decimal_line_rounding_discount_and_delivery_totals(self):
        self.assertEqual(pricing.money('1.005'), Decimal('1.01'))
        result=pricing.quote([{'quantity':3,'unit_price':'1.005'},{'quantity':1,'unit_price':10}],2,3)
        self.assertEqual(result,{'subtotal':13.02,'discount':2,'delivery_fee':3,'total':14.02})

    def test_invalid_money_quantity_discount_and_refund_are_rejected(self):
        for value in (True,-1,'nan','Infinity'):
            with self.assertRaises(server.HTTPException):pricing.money(value)
        for items,discount in (([{'quantity':0,'unit_price':1}],0),([{'quantity':1,'unit_price':-1}],0),([{'quantity':1,'unit_price':1}],2)):
            with self.assertRaises(server.HTTPException):pricing.quote(items,discount)
        with self.assertRaises(server.HTTPException):pricing.validate_refund({'total':10},[{'amount':5,'transaction_type':'payment'}],6)


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable PostgreSQL required')
class PricingAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)

    def create(self,**changes):
        return self.f.ok(0,'post','/api/orders',{'customer_name':'Pricing fixture','customer_phone':uuid.uuid4().hex,
            'items':[{'service_id':'shared-service','service_name':'Wash','quantity':1,'unit_price':10}],**changes})

    def test_legacy_provider_routes_and_generic_tax_configuration_stay_unavailable(self):
        paths=server.app.openapi()['paths']
        self.assertIn('/api/taxes/policy',paths)
        self.assertNotIn('/api/taxes/provider',paths)
        for path in ('/api/taxes/rules','/api/taxes/provider','/api/financial/taxes'):
            self.assertEqual(self.f.request(0,'get',path).status_code,404)
        self.assertEqual(self.f.request(0,'post','/api/taxes/estimate',{'items':[]}).status_code,200)
        self.assertEqual(self.f.request(0,'put','/api/settings',{'delivery_fee_taxable':True}).status_code,400)
        service=self.f.ok(0,'get','/api/admin/services')['services'][0]
        self.assertNotIn('taxable',service);self.assertNotIn('tax_rate',service)

    def test_new_orders_ignore_client_tax_and_reconcile_without_rules(self):
        order=self.create(tax=999,discount=2)
        self.assertEqual(order['tax'],0);self.assertIsNone(order['tax_snapshot']);self.assertEqual(order['total'],8)
        self.assertEqual(order['currency'],'USD')
        updated=self.f.ok(0,'put','/api/orders/'+order['id'],{'items':[{**order['items'][0],'quantity':2}]})
        self.assertEqual(updated['subtotal'],20);self.assertEqual(updated['total'],18);self.assertEqual(updated['tax'],0)
        receipt=self.f.ok(0,'get','/api/orders/'+order['id']+'/receipt')
        self.assertEqual(receipt['order']['total'],18);self.assertEqual(receipt['balance_due'],18)
        self.assertEqual(self.f.request(2,'get','/api/orders/'+order['id']+'/receipt').status_code,404)

    def test_archived_invoice_tax_and_snapshot_are_not_rewritten(self):
        order=self.create();snapshot={'currency':'USD','location':{'state':'IL'},'breakdown':[{'jurisdiction':'Archived state tax','rate':'5','amount':.5}],'lines':[]}
        with server.db(maintenance=True) as conn:
            conn.execute("UPDATE orders SET payload=payload||%s::jsonb WHERE id=%s",(json.dumps({'tax':.5,'total':10.5,'tax_snapshot':snapshot}),order['id']))
        saved=self.f.ok(0,'put','/api/orders/'+order['id'],{'notes':'Preserve the original invoice'})
        self.assertEqual(saved['tax_snapshot'],snapshot);self.assertEqual(saved['total'],10.5)
        self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'discount':1}).status_code,409)
        reread=self.f.ok(0,'get','/api/orders/'+order['id']+'/receipt')
        self.assertEqual(reread['order']['tax_snapshot'],snapshot);self.assertEqual(reread['order']['tax'],.5)

    def test_refunds_keep_gross_balance_caps_and_concurrency_guards(self):
        order=self.create();path='/api/orders/'+order['id']+'/payments'
        self.f.ok(0,'post',path,{'amount':10})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.f.request(0,'post',path,{'amount':8,'transaction_type':'refund'}),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.f.ok(0,'post',path,{'amount':2,'transaction_type':'refund'})
        self.assertEqual(self.f.request(0,'post',path,{'amount':1,'transaction_type':'refund'}).status_code,409)
        self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'discount':1}).status_code,409)

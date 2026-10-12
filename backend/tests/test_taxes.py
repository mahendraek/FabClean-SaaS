import json,os,unittest,uuid
from datetime import datetime,timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from psycopg.errors import InsufficientPrivilege
import server,taxes
from tests import test_postgres_isolation as fixtures
from tenant_scope import current_scope

class TaxMathTests(unittest.TestCase):
    def test_discount_allocation_and_half_up(self):
        self.assertEqual(taxes.allocate(Decimal('.01'),[Decimal(1)]*3),[Decimal('.01'),Decimal(0),Decimal(0)]);self.assertEqual(taxes.money('.005'),Decimal('.01'))
    def test_invalid_rule_money_and_dates(self):
        for value in (True,-1,'nan','Infinity'):
            with self.assertRaises(server.HTTPException):taxes.number(value)
        base={'component':'state','jurisdiction':'State tax','country':'US','state':'IL','rate':'6.25','effective_from':'2026-01-01'}
        for change in ({'rate':'101'},{'rate':'0.00001'},{'effective_to':'2025-01-01'},{'state':''},{'business_id':'forged'}):
            with self.assertRaises(server.HTTPException):taxes.validate_rule({**base,**change})
        with self.assertRaises(server.HTTPException):taxes.refund({'tax':2,'total':1},[{'amount':1,'transaction_type':'payment'}],1)
    def test_specificity_boundaries_and_timezone(self):
        base={'id':'a','component':'state','jurisdiction':'State','country':'US','state':'IL','rate':'5','effective_from':'2026-01-01','effective_to':'2026-02-01'}
        local={**base,'id':'b','city':'Chicago','rate':'6'};loc={'country':'US','state':'il','city':'CHICAGO','timezone':'America/Chicago'}
        self.assertEqual(taxes.selected([base,local],loc,'2026-01-31')[0]['rule_id'],'b');self.assertEqual(taxes.selected([base],loc,'2026-02-01'),[])
        self.assertEqual(taxes.store_date(loc,datetime(2026,1,1,1,tzinfo=timezone.utc)),'2025-12-31')

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable PostgreSQL required')
class TaxAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups);cls.client=cls.f.client
    def setUp(self):
        self.phone=uuid.uuid4().hex[:10]
        with server.db(maintenance=True) as conn:
            conn.execute('DELETE FROM tax_rules WHERE business_id=ANY(%s)',([self.f.brand_a,self.f.brand_b],));conn.execute("UPDATE stores SET country='US',state='IL',city='Chicago',postal_code='60601',timezone='America/Chicago' WHERE brand_id=ANY(%s)",([self.f.brand_a,self.f.brand_b],))
            conn.execute("UPDATE app_settings SET payload=payload-'delivery_fee_taxable' WHERE business_id=ANY(%s)",([self.f.brand_a,self.f.brand_b],))
        service=self.f.ok(0,'get','/api/admin/services')['services'][0];service['taxable']=True;service['tax_rate']=0;self.f.ok(0,'put','/api/services/shared-service',service)
        self.items=[{'service_id':'shared-service','service_name':'Wash','quantity':1,'unit_price':10}]
    def rule(self,actor=0,**change):
        body={'component':'state','jurisdiction':'Illinois state tax','country':'US','state':'IL','rate':'6.25','effective_from':'2020-01-01',**change};return self.f.request(actor,'post','/api/taxes/rules',body)
    def seed(self):
        r=self.rule();self.assertEqual(r.status_code,200,r.text);return r.json()
    def estimate(self,actor=0,**change):return self.f.request(actor,'post','/api/taxes/estimate',{'items':self.items,**change})
    def create(self,actor=0,**change):return self.f.ok(actor,'post','/api/orders',{'customer_name':'Tax fixture','customer_phone':self.phone,'items':self.items,**change})
    def test_estimate_order_receipt_match_and_client_tax_is_ignored(self):
        self.seed();self.rule(component='city',jurisdiction='Chicago city tax',city='Chicago',rate='1.25');quote=self.estimate(discount=2).json();order=self.create(discount=2,tax=999)
        self.assertEqual(quote['tax'],.6);self.assertEqual(order['tax'],.6);self.assertEqual(quote['total'],order['total']);self.assertEqual(len(order['tax_snapshot']['breakdown']),2);self.assertEqual(self.f.ok(0,'get','/api/orders/'+order['id']+'/receipt')['order']['tax'],.6)
    def test_exempt_items_and_proportional_discount(self):
        self.seed();self.f.ok(0,'post','/api/services',{'id':'exempt','name':'Exempt service','category':'Test','pricing_type':'per_item','base_price':10,'taxable':False});q=self.estimate(items=self.items+[{'service_id':'exempt','quantity':1,'unit_price':10}],discount=10).json();self.assertEqual(q['tax'],.31);self.assertEqual(q['tax_snapshot']['lines'][0]['discount'],5);self.assertFalse(q['tax_snapshot']['lines'][1]['taxable'])
    def test_dates_replacement_and_void_preserve_snapshot(self):
        original=self.seed();order=self.create();self.assertEqual(self.f.request(0,'post','/api/taxes/rules/'+original['id']+'/void',{'reason':'Correct future calculations'}).status_code,200);self.rule(rate='10');self.assertEqual(self.estimate().json()['tax'],1);saved=self.f.ok(0,'get','/api/orders/'+order['id']);self.assertEqual(saved['tax'],.63);self.assertEqual(saved['tax_snapshot']['components'][0]['rule_id'],original['id'])
    def test_overlap_and_concurrent_creation_are_rejected(self):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.rule(),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409]);self.assertEqual(self.rule(effective_from='2019-01-01',effective_to='2020-01-01').status_code,200)
    def test_missing_location_or_rate_coverage_fails_closed(self):
        self.seed()
        with server.db() as conn:conn.execute("UPDATE stores SET state='' WHERE id=%s",(self.f.stores[0],))
        self.assertEqual(self.estimate().status_code,409)
        with server.db() as conn:conn.execute("UPDATE stores SET state='CA' WHERE id=%s",(self.f.stores[0],))
        self.assertEqual(self.estimate().status_code,409)
    def test_foreign_scope_rules_services_and_estimate_order_are_denied(self):
        rule=self.seed();self.assertEqual(self.f.ok(1,'get','/api/taxes/rules')['rules'],[]);self.assertEqual(self.f.ok(2,'get','/api/taxes/rules')['rules'],[]);self.assertEqual(self.f.request(1,'post','/api/taxes/rules/'+rule['id']+'/void',{'reason':'Foreign'}).status_code,404)
        order=self.create();self.assertEqual(self.estimate(1,order_id=order['id']).status_code,404);self.assertEqual(self.estimate(location={'state':'CA'}).status_code,400);self.assertEqual(self.client.get('/api/taxes/rules').status_code,401)
    def test_forced_rls_and_repeatable_migration(self):
        self.seed();server.init_db();server.init_db();self.assertEqual(len(self.f.ok(0,'get','/api/taxes/rules')['rules']),1)
        marker=current_scope.set((self.f.brand_b,self.f.stores[2]))
        try:
            with server.db() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM tax_rules').fetchone()['n'],0);r=conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='tax_rules'::regclass").fetchone();self.assertTrue(r['relrowsecurity'] and r['relforcerowsecurity'])
            with self.assertRaises(InsufficientPrivilege),server.db() as conn:conn.execute('INSERT INTO tax_rules(id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb)',(uuid.uuid4().hex,self.f.brand_a,self.f.stores[0],'{}'))
        finally:current_scope.reset(marker)
    def test_repricing_uses_frozen_rates_and_taxability(self):
        self.seed();order=self.create();service=self.f.ok(0,'get','/api/admin/services')['services'][0];service['taxable']=False;self.f.ok(0,'put','/api/services/shared-service',service)
        marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
        try:
            with server.db() as conn:conn.execute("UPDATE stores SET state='CA' WHERE id=%s",(self.f.stores[0],))
        finally:current_scope.reset(marker)
        items=[{**order['items'][0],'quantity':2}];quote=self.estimate(order_id=order['id'],items=items).json();edited=self.f.ok(0,'put','/api/orders/'+order['id'],{'items':items,'tax':0});self.assertEqual(edited['tax'],1.25);self.assertEqual(quote['total'],edited['total']);self.assertEqual(edited['tax_snapshot']['location']['state'],'IL')
    def test_refund_tax_cumulative_rounding_report_and_overrefund(self):
        self.seed();order=self.create();self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':order['total']})
        first=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':5,'transaction_type':'refund'});second=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':5.63,'transaction_type':'refund'});self.assertEqual(float(first['payment']['tax_amount'])+float(second['payment']['tax_amount']),.63)
        self.assertEqual(self.f.request(0,'post','/api/orders/'+order['id']+'/payments',{'amount':1,'transaction_type':'refund'}).status_code,409);self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'discount':1}).status_code,409)
        day=order['tax_snapshot']['service_date'];report=self.f.ok(0,'get','/api/financial/taxes?from_date='+day+'&to_date='+day);self.assertGreaterEqual(report['refunded_tax'],.63)
    def test_concurrent_refunds_cannot_exceed_paid_balance(self):
        self.seed();order=self.create();self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':order['total']})
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.f.request(0,'post','/api/orders/'+order['id']+'/payments',{'amount':8,'transaction_type':'refund'}),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
    def test_delivery_fee_policy_and_legacy_service_fallback(self):
        q=self.estimate().json();self.assertEqual(q['tax_snapshot']['source'],'legacy_service_rates');self.seed();self.f.ok(0,'put','/api/settings',{'delivery_fee_taxable':True});self.assertEqual(self.estimate(delivery_fee=2).json()['tax'],.76)
    def test_legacy_order_preserved_until_pricing_changes(self):
        order=self.create()
        with server.db(maintenance=True) as conn:conn.execute("UPDATE orders SET payload=(payload-'tax_snapshot')||%s::jsonb WHERE id=%s",(json.dumps({'tax':3,'total':13}),order['id']))
        self.seed();legacy=self.f.ok(0,'get','/api/orders/'+order['id']);q=self.estimate(order_id=order['id'],items=legacy['items']).json();self.assertEqual(q['total'],13);updated=self.f.ok(0,'put','/api/orders/'+order['id'],{'notes':'Keep history','items':legacy['items']});self.assertEqual(updated['tax'],3)
        updated=self.f.ok(0,'put','/api/orders/'+order['id'],{'items':[{**legacy['items'][0],'quantity':2}]});self.assertEqual(updated['tax'],1.25)
    def test_quick_dropoff_rates_are_captured_when_first_priced(self):
        order=self.create(items=[],quick_dropoff=True,bag_count=1);self.seed();edited=self.f.ok(0,'put','/api/orders/'+order['id'],{'items':self.items,'quick_dropoff':False});self.assertEqual(edited['tax'],.63)
    def test_invalid_quote_cannot_write_operational_records(self):
        self.seed()
        for body in ({'discount':11},{'items':[{'service_id':'shared-service','quantity':-1,'unit_price':10}]},{'tax':0},{'items':['bad']}):self.assertIn(self.estimate(**body).status_code,(400,404))
    def test_legacy_refund_does_not_transfer_unrecorded_tax_to_new_refund(self):
        self.seed();order=self.create();self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':order['total']});first=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':5,'transaction_type':'refund'})
        with server.db(maintenance=True) as conn:conn.execute("UPDATE payment_transactions SET tax_amount=0,tax_breakdown='[]'::jsonb WHERE id=%s",(first['payment']['id'],))
        second=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':5.63,'transaction_type':'refund'});self.assertEqual(float(second['payment']['tax_amount']),.33)
        day=order['tax_snapshot']['service_date'];report=self.f.ok(0,'get','/api/financial/taxes?from_date='+day+'&to_date='+day);self.assertGreaterEqual(report['unclassified_refunds'],1)
    def test_cent_refunds_do_not_credit_more_tax_than_cash_and_components_balance(self):
        self.seed();self.rule(component='city',jurisdiction='City tax',city='Chicago',rate='5');order=self.create(items=[{**self.items[0],'unit_price':.1}]);self.assertEqual(order['tax'],.02);self.assertEqual(order['total'],.12);self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':.12})
        credits=[]
        for _ in range(12):
            row=self.f.ok(0,'post','/api/orders/'+order['id']+'/payments',{'amount':.01,'transaction_type':'refund'})['payment'];self.assertLessEqual(float(row['tax_amount']),.01);credits.append(row)
        self.assertEqual(round(sum(float(row['tax_amount']) for row in credits),2),.02)
        for component in order['tax_snapshot']['breakdown']:self.assertEqual(round(sum(entry['amount'] for row in credits for entry in row['tax_breakdown'] if entry['component']==component['component']),2),component['amount'])

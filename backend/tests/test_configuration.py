import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from psycopg.errors import InsufficientPrivilege
import server
import configuration
from tenant_scope import current_scope
from tests import test_postgres_isolation as fixtures

class ConfigurationValidationTests(unittest.TestCase):
    def test_invalid_definitions(self):
        for value in ({'pickup_enabled':1},{'service_radius_miles':-1},{'currency':'usd'},{'business_id':'foreign'},{'pickup_delivery_slot_minutes':0}):
            with self.assertRaises(server.HTTPException):configuration.validate_settings(value)
        for value in ({'name':'Wash','category':'Wash','pricing_type':'per_item','base_price':-1},{'name':'Wash','category':'Wash','pricing_type':'per_item','business_id':'foreign'}):
            with self.assertRaises(server.HTTPException):configuration.validate_service(value,'wash')
        for value in ({'name':'Bad','discount_value':float('nan')},{'name':'Bad','discount_type':'percent','discount_value':101},{'name':'Bad','usage_limit':True},{'name':'Bad','active':1}):
            with self.assertRaises(server.HTTPException):configuration.validate_offer(value,'promo')

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable PostgreSQL required')
class ConfigurationAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups);cls.client=cls.f.client
    def setUp(self):
        with server.db(maintenance=True) as conn:
            for table in ('brand_configuration','store_configuration','configuration_offer_usage'):conn.execute('DELETE FROM '+table+' WHERE business_id=ANY(%s)',([self.f.brand_a,self.f.brand_b],))
            conn.execute("UPDATE app_settings SET payload=%s::jsonb WHERE business_id=%s AND location_id=%s",(json.dumps({'business_name':'Store 0'}),self.f.brand_a,self.f.stores[0]))
    def get(self,actor=0):return self.f.ok(actor,'get','/api/configuration')
    def put(self,level,body,actor='super'):return self.f.request(actor,'put','/api/configuration/'+level,{'revision':self.get(actor)[level]['revision'],**body})
    def seed(self,price=10):
        r=self.put('brand',{'settings':{'pickup_enabled':True,'service_radius_miles':12},'services':{'brand-wash':{'name':'Brand wash','category':'Brand laundry','pricing_type':'per_item','base_price':price}},'offers':{'welcome':{'name':'Welcome','code':'BRAND','discount_value':2,'usage_limit':1}}});self.assertEqual(r.status_code,200,r.text)
    def service(self,actor=0):return next(r for r in self.get(actor)['services'] if r['id']=='brand-wash')
    def test_legacy_values_and_new_fields(self):
        self.seed();d=self.get();self.assertEqual(d['settings']['business_name'],'Store 0');self.assertTrue(d['settings']['pickup_enabled']);self.assertEqual(d['settings_sources']['business_name'],'store');self.assertEqual(d['settings_sources']['pickup_enabled'],'brand');self.assertEqual(self.f.ok(0,'get','/api/admin/overview')['settings'],self.f.ok(0,'get','/api/settings'))
    def test_store_override_reset_and_brand_propagation(self):
        self.seed();self.put('store',{'settings':{'service_radius_miles':8}},0);self.put('brand',{'settings':{'service_radius_miles':20}});self.assertEqual(self.get()['settings']['service_radius_miles'],8);self.assertEqual(self.get(1)['settings']['service_radius_miles'],20);self.put('store',{'settings':{'service_radius_miles':None}},0);self.assertEqual(self.get()['settings']['service_radius_miles'],20)
    def test_service_price_inheritance_and_reset(self):
        self.seed();self.assertEqual(self.service()['base_price'],10);self.assertEqual(self.service()['location_id'],self.f.stores[0]);self.assertIn('brand-wash',[r['id'] for r in self.f.ok(0,'get','/api/services')['services']]);self.put('store',{'services':{'brand-wash':{'base_price':7}}},0);self.seed(15);self.assertEqual(self.service()['base_price'],7);self.assertEqual(self.service(1)['base_price'],15);self.put('store',{'services':{'brand-wash':None}},0);self.assertEqual(self.service()['base_price'],15)
    def test_disable_without_brand_fallback(self):
        self.seed();self.put('store',{'services':{'brand-wash':{'active':False}}},0);self.assertNotIn('brand-wash',[r['id'] for r in self.f.ok(0,'get','/api/services')['services']]);self.assertIn('brand-wash',[r['id'] for r in self.f.ok(1,'get','/api/services')['services']])
    def test_existing_editors_and_reset(self):
        self.seed();service=self.service();service['base_price']=4;self.assertEqual(self.f.request(0,'put','/api/services/brand-wash',service).status_code,200);self.assertEqual(self.service()['base_price'],4);offer=next(r for r in self.get()['offers'] if r.get('template_id'));self.assertEqual(self.f.request(0,'put','/api/offers/'+offer['id'],{'discount_value':5}).status_code,200);self.assertEqual(next(r for r in self.get()['offers'] if r.get('template_id'))['discount_value'],5);self.put('store',{'services':{'brand-wash':None},'offers':{'welcome':None}},0);self.assertEqual(self.service()['base_price'],10)
    def test_permissions_and_forged_scope(self):
        self.assertEqual(self.put('brand',{'settings':{}},0).status_code,403);self.assertEqual(self.client.get('/api/configuration').status_code,401);self.assertEqual(self.f.request(0,'put','/api/configuration/store',{'revision':0,'business_id':self.f.brand_b}).status_code,400);self.assertEqual(self.client.get('/api/configuration',headers={'X-Session-Token':self.f.tokens[0],'X-Active-Brand-ID':self.f.brand_b,'X-Active-Store-ID':self.f.stores[2]}).status_code,409)
    def test_other_brand_has_no_templates(self):
        self.seed();self.assertNotIn('brand-wash',[r['id'] for r in self.get(2)['services']]);self.assertFalse(self.get(2)['settings']['pickup_enabled']);self.assertEqual(self.put('store',{'services':{'brand-wash':None}},2).status_code,404);self.assertNotIn('BRAND',[r['code'] for r in self.get(2)['offers']])
    def test_forced_rls(self):
        self.seed();marker=current_scope.set((self.f.brand_b,self.f.stores[2]))
        try:
            with server.db() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM brand_configuration').fetchone()['n'],0)
                for table in ('brand_configuration','store_configuration','configuration_offer_usage'):
                    row=conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone();self.assertTrue(row['relrowsecurity'] and row['relforcerowsecurity'])
            with self.assertRaises(InsufficientPrivilege),server.db() as conn:conn.execute('INSERT INTO brand_configuration(business_id,payload) VALUES (%s,%s::jsonb)',(self.f.brand_a,json.dumps(configuration.EMPTY)))
        finally:current_scope.reset(marker)
    def test_concurrent_revision_conflict(self):
        body={'revision':0,'settings':{'service_radius_miles':5}}
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.f.request('super','put','/api/configuration/brand',body),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
    def test_invalid_write_is_atomic(self):
        self.seed();before=self.get();r=self.put('store',{'settings':{'service_radius_miles':77},'services':{'missing':{'base_price':2}}},0);self.assertEqual(r.status_code,404);after=self.get();self.assertEqual(before['settings'],after['settings']);self.assertEqual(before['store'],after['store'])
    def test_offer_application_and_store_usage(self):
        self.seed();order=self.f.ok(0,'post','/api/orders',{'customer_name':'Inherited promo','customer_phone':'55588881','promo_code':'BRAND','items':[{'service_id':'brand-wash','service_name':'Brand wash','quantity':1,'unit_price':10}]});self.assertEqual(order['discount'],2);self.assertEqual(self.f.request(0,'post','/api/offers/validate',{'code':'BRAND','subtotal':10}).status_code,400);self.assertEqual(self.f.request(1,'post','/api/offers/validate',{'code':'BRAND','subtotal':10}).status_code,200);self.put('store',{'offers':{'welcome':None}},0);self.assertEqual(next(r for r in self.get()['offers'] if r.get('template_id'))['usage_count'],1)
    def test_repeatable_migration_and_audit(self):
        self.seed();before=self.get()['brand'];server.init_db();server.init_db();self.assertEqual(self.get()['brand'],before);events=self.f.ok('super','get','/api/platform/audit?brand_id='+self.f.brand_a)['events'];self.assertTrue(any(r['action']=='configuration_brand_updated' for r in events))
    def test_brand_update_rejects_invalid_override_in_another_store(self):
        self.seed();self.assertEqual(self.put('store',{'offers':{'welcome':{'discount_value':120}}},1).status_code,200)
        before=self.get()['brand'];r=self.put('brand',{'offers':{'welcome':{'name':'Welcome','code':'BRAND','discount_type':'percent','discount_value':10}}});self.assertEqual(r.status_code,409);self.assertEqual(self.get()['brand'],before)
    def test_incremental_overrides_preserve_other_fields_and_reject_nonobjects(self):
        self.seed();self.put('store',{'services':{'brand-wash':{'active':False}}},0);self.put('store',{'services':{'brand-wash':{'base_price':8}}},0);self.assertFalse(self.service()['active']);self.assertEqual(self.service()['base_price'],8)
        self.assertEqual(self.put('store',{'services':{'brand-wash':'forged'}},0).status_code,400)
    def test_local_inactive_service_shadows_brand_and_reset_is_explicit(self):
        self.seed();self.assertEqual(self.f.request(0,'post','/api/services',{'id':'brand-wash','name':'Local wash','category':'Brand laundry','pricing_type':'per_item','base_price':99,'active':False}).status_code,200)
        self.assertNotIn('brand-wash',[r['id'] for r in self.f.ok(0,'get','/api/services')['services']]);self.put('store',{'services':{'brand-wash':None}},0);self.assertEqual(self.service()['base_price'],10)
    def test_revision_rejects_stale_editor_after_legacy_settings_write(self):
        before=self.get()['store']['revision'];self.f.ok(0,'put','/api/settings',{'service_radius_miles':2});r=self.f.request(0,'put','/api/configuration/store',{'revision':before,'settings':{'service_radius_miles':9}});self.assertEqual(r.status_code,409);self.assertEqual(self.get()['settings']['service_radius_miles'],2)
    def test_new_store_inherits_without_copying_local_rows(self):
        self.seed();store=self.f.ok('super','post','/api/brand/stores',{'brand_id':self.f.brand_a,'name':'New inheriting store','store_code':'INHERIT'})
        marker=current_scope.set((self.f.brand_a,store['id']))
        try:
            self.assertTrue(server.get_settings_value()['pickup_enabled']);self.assertEqual(server.get_settings_value()['service_radius_miles'],12);self.assertEqual(server.get_service_values()[0]['id'],'brand-wash')
            with server.db() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM services').fetchone()['n'],0)
        finally:current_scope.reset(marker)
    def test_defaults_cannot_enable_unlicensed_pickup(self):
        self.seed()
        with server.db() as conn:conn.execute('UPDATE brands SET entitlement_overrides=%s::jsonb WHERE id=%s',(json.dumps({'features':{'pickup':False}}),self.f.brand_a))
        try:
            self.assertTrue(self.get()['settings']['pickup_enabled'])
            r=self.f.request(0,'post','/api/orders',{'customer_name':'Licence check','customer_phone':'5551111','service_address':'Local test address','fulfillment_type':'pickup_only','items':[{'service_id':'brand-wash','service_name':'Brand wash','quantity':1,'unit_price':10}]});self.assertEqual(r.status_code,400);self.assertIn('disabled',r.json()['detail'].lower())
        finally:
            with server.db() as conn:conn.execute("UPDATE brands SET entitlement_overrides='{}'::jsonb WHERE id=%s",(self.f.brand_a,))
    def test_price_override_preserves_existing_local_definition_until_reset(self):
        self.seed();self.f.ok(0,'post','/api/services',{'id':'brand-wash','name':'Local specialty wash','category':'Local category','pricing_type':'per_item','base_price':25,'pickup_eligible':False,'turnaround_hours':72})
        self.assertEqual(self.put('store',{'services':{'brand-wash':{'base_price':8}}},0).status_code,200)
        value=self.service();self.assertEqual(value['base_price'],8);self.assertEqual(value['name'],'Local specialty wash');self.assertEqual(value['category'],'Local category');self.assertFalse(value['pickup_eligible']);self.assertEqual(value['turnaround_hours'],72)
        self.put('store',{'services':{'brand-wash':None}},0);self.assertEqual(self.service()['name'],'Brand wash')

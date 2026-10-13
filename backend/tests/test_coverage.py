import copy
import json
import math
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from psycopg.errors import InsufficientPrivilege
import server
import coverage
from tenant_scope import current_scope
from tests import test_postgres_isolation as fixtures

def p(lat,lon):return {'latitude':lat,'longitude':lon}
def policy(**changes):return {'enabled':True,'mode':'radius','unit':'km','radius':10,'zones':[],**changes}
def zone(**changes):return {'id':'zone-a','name':'Central','pickup':True,'delivery':True,'active':True,'vertices':[p(41,-88),p(42,-88),p(42,-87),p(41,-87)],**changes}

class CoverageMathTests(unittest.TestCase):
    def test_distance_zero_symmetry_date_line_and_known_distance(self):
        self.assertEqual(coverage.distance_km(p(0,0),p(0,0)),0)
        self.assertAlmostEqual(coverage.distance_km(p(0,0),p(0,1)),111.19508,places=4)
        self.assertAlmostEqual(coverage.distance_km(p(10,179.9),p(10,-179.9)),coverage.distance_km(p(10,-179.9),p(10,179.9)))
        self.assertLess(coverage.distance_km(p(10,179.9),p(10,-179.9)),23)
    def test_radius_boundary_and_miles_conversion(self):
        loc={'id':'store',**p(0,0)};target=p(0,1);distance=coverage.distance_km(loc,target)
        result=coverage.evaluate({'revision':1,'payload':policy(radius=distance)},loc,target,'pickup_only',{'pickup':True,'delivery':True})
        self.assertTrue(result['eligible'])
        document={'revision':1,'payload':policy(radius=distance/1.609344,unit='mi')}
        self.assertTrue(coverage.evaluate(document,loc,target,'pickup_only',{'pickup':True,'delivery':True})['eligible'])
        document['payload']['radius']-=.001
        self.assertFalse(coverage.evaluate(document,loc,target,'pickup_only',{'pickup':True,'delivery':True})['eligible'])
    def test_polygon_boundary_concavity_and_negative_coordinates(self):
        vertices=zone()['vertices'];self.assertTrue(coverage.contains(vertices,p(41.5,-87.5)));self.assertTrue(coverage.contains(vertices,p(41,-88)));self.assertTrue(coverage.contains(vertices,p(41.5,-88)));self.assertFalse(coverage.contains(vertices,p(40,-88)))
        concave=[p(0,0),p(0,2),p(1,1),p(2,2),p(2,0)]
        self.assertTrue(coverage.contains(concave,p(1,.5)));self.assertFalse(coverage.contains(concave,p(1,1.5)))
    def test_invalid_polygons_and_coordinates(self):
        for vertices in ([p(0,0),p(0,1)],[p(0,0),p(0,1),p(0,2)],[p(0,0),p(1,1),p(0,1),p(1,0)],[p(0,179),p(1,-179),p(0,-179)],zone()['vertices']+[zone()['vertices'][0]]):
            with self.assertRaises(server.HTTPException):coverage.validate_polygon(vertices)
        for value in (True,float('nan'),float('inf'),'41',86,None):
            with self.assertRaises(server.HTTPException):coverage.coordinate(value)
    def test_zone_modes_inactive_and_disabled_capabilities(self):
        document={'revision':1,'payload':policy(mode='zones',zones=[zone(pickup=False)])};loc={'id':'s',**p(41.5,-87.5)};caps={'pickup':True,'delivery':True}
        self.assertTrue(coverage.evaluate(document,loc,p(41.5,-87.5),'delivery_only',caps)['eligible'])
        self.assertFalse(coverage.evaluate(document,loc,p(41.5,-87.5),'pickup_and_delivery',caps)['eligible'])
        document['payload']['zones'][0]['active']=False
        self.assertFalse(coverage.evaluate(document,loc,p(41.5,-87.5),'delivery_only',caps)['eligible'])
        document['payload']=policy()
        self.assertFalse(coverage.evaluate(document,loc,p(41.5,-87.5),'pickup_only',{'pickup':False,'delivery':True})['eligible'])
    def test_policy_validation_and_unconfigured_rollout(self):
        for change in ({'radius':0},{'radius':501},{'radius':True},{'unit':'yards'},{'mode':'zones'},{'enabled':1},{'zones':[zone(),zone()]}):
            with self.assertRaises(server.HTTPException):coverage.validate(policy(**change))
        result=coverage.evaluate({'revision':0,'payload':None},{'id':'s'},p(0,0),'pickup_only',{'pickup':True,'delivery':True});self.assertIsNone(result['eligible'])

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable PostgreSQL required')
class CoverageAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
    def setUp(self):
        with server.db(maintenance=True) as conn:
            conn.execute('DELETE FROM store_delivery_coverage WHERE business_id=ANY(%s)',([self.f.brand_a,self.f.brand_b],))
            conn.execute('UPDATE stores SET latitude=41.5,longitude=-87.5 WHERE brand_id=ANY(%s)',([self.f.brand_a,self.f.brand_b],))
        for i in range(3):self.f.ok(i,'put','/api/settings',{'pickup_enabled':True,'delivery_enabled':True})
    def save(self,document=None,actor=0,revision=0):return self.f.request(actor,'put','/api/coverage',{'revision':revision,'payload':document or policy()})
    def check(self,actor=0,**changes):return self.f.request(actor,'post','/api/coverage/check',{'latitude':41.5,'longitude':-87.5,'address':'Test street','fulfillment_type':'pickup_and_delivery',**changes})
    def body(self,**changes):return {'customer_name':'Coverage fixture','customer_phone':'555map','items':[{'service_id':'shared-service','service_name':'Wash','quantity':1,'unit_price':10}],'fulfillment_type':'pickup_only','pickup_date':'2030-01-02','pickup_slot_id':self.f.slots[0],'service_address':'Test street','service_latitude':41.5,'service_longitude':-87.5,**changes}
    def test_check_create_snapshot_spoof_and_coverage_change(self):
        self.assertEqual(self.save().status_code,200);result=self.check().json();self.assertTrue(result['eligible']);order=self.f.ok(0,'post','/api/orders',self.body(coverage_snapshot={'eligible':False}))
        self.assertTrue(order['coverage_snapshot']['eligible']);self.assertEqual(order['coverage_snapshot']['store_id'],self.f.stores[0]);self.assertEqual(order['coverage_snapshot']['policy']['radius'],10)
        self.assertEqual(self.check(latitude=40).json()['eligible'],False)
        self.assertEqual(self.f.request(0,'post','/api/orders',self.body(service_latitude=40)).status_code,409)
        self.assertEqual(self.f.request(0,'post','/api/orders',self.body(service_latitude=None)).status_code,400)
        self.assertEqual(self.save(policy(radius=1),revision=1).status_code,200)
        updated=self.f.ok(0,'put','/api/orders/'+order['id'],{'notes':'Preserve assessment'});self.assertEqual(updated['coverage_snapshot'],order['coverage_snapshot'])
        self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'service_latitude':40}).status_code,409)
        self.assertEqual(self.f.ok(0,'get','/api/orders/'+order['id'])['service_latitude'],41.5)
    def test_policy_store_scope_permission_and_forged_store(self):
        self.assertEqual(self.save().status_code,200);self.assertIsNone(self.f.ok(1,'get','/api/coverage')['payload']);self.assertIsNone(self.f.ok(2,'get','/api/coverage')['payload'])
        self.assertEqual(self.check(store_id=self.f.stores[1]).status_code,400)
        self.assertEqual(self.f.client.get('/api/coverage').status_code,401)
        with server.db(maintenance=True) as conn:conn.execute('UPDATE user_role_assignments SET role=%s WHERE user_id=%s',('driver',self.f.users[0]))
        try:self.assertEqual(self.save(revision=1).status_code,403)
        finally:
            with server.db(maintenance=True) as conn:conn.execute('UPDATE user_role_assignments SET role=%s WHERE user_id=%s',('store_manager',self.f.users[0]))
    def test_forced_rls_migration_and_audit(self):
        self.save();server.init_db();server.init_db();self.assertEqual(self.f.ok(0,'get','/api/coverage')['revision'],1)
        marker=current_scope.set((self.f.brand_b,self.f.stores[2]))
        try:
            with server.db() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM store_delivery_coverage').fetchone()['n'],0)
                row=conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='store_delivery_coverage'::regclass").fetchone();self.assertTrue(row['relrowsecurity'] and row['relforcerowsecurity'])
            with self.assertRaises(InsufficientPrivilege),server.db() as conn:conn.execute('INSERT INTO store_delivery_coverage VALUES (%s,%s,%s::jsonb,1)',(self.f.brand_a,self.f.stores[0],'{}'))
        finally:current_scope.reset(marker)
        events=self.f.ok('super','get','/api/platform/audit?brand_id='+self.f.brand_a)['events'];self.assertTrue(any(e['action']=='delivery_coverage_updated' for e in events))
    def test_missing_origin_and_invalid_policy_are_atomic(self):
        with server.db(maintenance=True) as conn:conn.execute('UPDATE stores SET latitude=NULL WHERE id=%s',(self.f.stores[0],))
        self.assertEqual(self.save().status_code,409);self.assertEqual(self.f.ok(0,'get','/api/coverage')['revision'],0)
        self.assertEqual(self.save(policy(enabled=False)).status_code,200)
        self.assertEqual(self.save(policy(radius=-1),revision=1).status_code,400);self.assertEqual(self.f.ok(0,'get','/api/coverage')['revision'],1)
    def test_concurrent_revision_conflict(self):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.save(),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
    def test_polygon_pickup_delivery_and_unit_roundtrip(self):
        self.assertEqual(self.save(policy(mode='zones',zones=[zone(pickup=False)])).status_code,200)
        self.assertFalse(self.check().json()['eligible']);self.assertTrue(self.check(fulfillment_type='delivery_only').json()['eligible'])
        document=policy(unit='mi',radius=10/1.609344);self.assertEqual(self.save(document,revision=1).status_code,200);r=self.check().json();self.assertEqual(r['unit'],'mi');self.assertTrue(r['eligible'])
    def test_enabling_coverage_enforces_existing_walkin_address_changes(self):
        order=self.f.ok(0,'post','/api/orders',self.body(fulfillment_type='walk_in'))
        self.save()
        self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'fulfillment_type':'delivery_only','service_latitude':0}).status_code,409)
        self.assertEqual(self.f.request(0,'put','/api/orders/'+order['id'],{'service_latitude':'bad'}).status_code,400)
    def test_customer_creation_rolls_back_on_outside_address(self):
        self.save()
        before=len(self.f.ok(0,'get','/api/customers')['customers'])
        self.assertEqual(self.f.request(0,'post','/api/orders',self.body(customer_phone='outside-new',service_latitude=0)).status_code,409)
        self.assertEqual(len(self.f.ok(0,'get','/api/customers')['customers']),before)

    def test_recurring_orders_carry_pins_and_recheck_current_coverage(self):
        self.save();self.f.ok(0,'put','/api/settings',{'subscriptions_enabled':True})
        customer=self.f.customers[0]
        sub=self.f.ok(0,'post','/api/customers/'+customer+'/subscriptions',{'plan_id':self.f.plans[0],'next_pickup_date':'2030-01-02','service_area_id':self.f.areas[0],'scheduled_slot_id':self.f.slots[0],'service_address':'Recurring street','service_postal_code':'60601','service_latitude':41.5,'service_longitude':-87.5})
        result=self.f.ok(0,'post','/api/subscriptions/'+sub['id']+'/generate-order')
        order=result.get('order',result);self.assertTrue(order['coverage_snapshot']['eligible']);self.assertEqual(order['service_latitude'],41.5)
        self.f.ok(0,'put','/api/subscriptions/'+sub['id'],{'service_latitude':0,'service_longitude':0})
        self.assertEqual(self.f.request(0,'post','/api/subscriptions/'+sub['id']+'/generate-order').status_code,409)
        with server.db(maintenance=True) as conn:
            row=conn.execute('SELECT next_pickup_date FROM customer_subscriptions WHERE id=%s',(sub['id'],)).fetchone();self.assertEqual(str(row['next_pickup_date']),'2030-01-09')

    def test_subscription_pin_validation_and_foreign_ids(self):
        customer=self.f.customers[0]
        body={'plan_id':self.f.plans[0],'service_latitude':41.5}
        self.assertEqual(self.f.request(0,'post','/api/customers/'+customer+'/subscriptions',body).status_code,400)
        sub=self.f.ok(0,'post','/api/customers/'+customer+'/subscriptions',{'plan_id':self.f.plans[0]})
        self.assertEqual(self.f.request(1,'put','/api/subscriptions/'+sub['id'],{'service_latitude':41.5,'service_longitude':-87.5}).status_code,404)

class MemoryCoverageTests(unittest.TestCase):
    def test_memory_scopes_and_same_geometry(self):
        from tests.test_memory_isolation_api import MemoryIsolationAPITests
        f=MemoryIsolationAPITests();f.setUp();self.addCleanup(f.doCleanups)
        saved=copy.deepcopy(coverage.memory.buckets);self.addCleanup(setattr,coverage.memory,'buckets',saved)
        with patch.object(coverage,'location',return_value={'id':f.staff['0']['location_id'],**p(41.5,-87.5)}):
            f.ok(0,'put','/api/settings',{'pickup_enabled':True,'delivery_enabled':True});f.ok(0,'put','/api/coverage',{'revision':0,'payload':policy()})
            self.assertTrue(f.ok(0,'post','/api/coverage/check',{'latitude':41.5,'longitude':-87.5,'address':'Test','fulfillment_type':'pickup_only'})['eligible'])
            self.assertIsNone(f.ok(1,'get','/api/coverage')['payload'])

"""PR6 regressions, using disposable PostgreSQL and non-bypass owner RLS."""
import hashlib
import os
import unittest
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient
import server
import security
from tests import test_store_operations as fixtures
from tenant_scope import current_scope
from database_pool import get_pool

class ConfigurationTests(unittest.TestCase):
    def test_production_requires_database_and_explicit_https_origins(self):
        for env in ({'RENDER':'true'}, {'APP_ENV':'production'}, {'APP_ENV':'production','DATABASE_URL':'configured'}, {'APP_ENV':'production','DATABASE_URL':'configured','CORS_ALLOWED_ORIGINS':'*'}, {'APP_ENV':'production','DATABASE_URL':'configured','CORS_ALLOWED_ORIGINS':'http://example.com'}, {'CORS_ALLOWED_ORIGINS':'https://example.com/private'}, {'CORS_ALLOWED_ORIGINS':'https://*.example.com'}, {'CORS_ALLOWED_ORIGINS':'https://user:pass@example.com'}):
            with self.subTest(env=env), self.assertRaises(RuntimeError): security.cors_origins(env)
        self.assertEqual(security.cors_origins({'APP_ENV':'production','DATABASE_URL':'configured','CORS_ALLOWED_ORIGINS':'https://example.com'}),['https://example.com'])

    def test_password_versioning_preserves_legacy(self):
        old=hashlib.pbkdf2_hmac('sha256',b'password',b'salt',120000).hex()
        new=security.hash_password('password','salt')
        self.assertTrue(new.startswith('pbkdf2_sha256$600000$'))
        for value in (old,new):
            self.assertTrue(security.verify_password('password','salt',value))
            self.assertFalse(security.verify_password('wrong','salt',value))
        self.assertFalse(security.verify_password('password','salt','pbkdf2_sha256$999999999$bad'))

    def test_cors_and_redacted_request_logging(self):
        client=TestClient(server.app);self.addCleanup(client.close)
        headers={'Origin':'http://localhost:8081','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'x-session-token,x-active-store-id'}
        self.assertEqual(client.options('/api/orders',headers=headers).status_code,200)
        headers['Origin']='https://untrusted.example'
        self.assertEqual(client.options('/api/orders',headers=headers).status_code,400)
        with patch.object(server,'DATABASE_URL',''), self.assertLogs('fabclean.access',level='INFO') as logs:
            response=client.post('/api/auth/sign-out?private_query=do-not-log-query',headers={'X-Session-Token':'do-not-log-token'},json={'password':'do-not-log-password'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.headers.get('x-request-id'))
        self.assertEqual(response.headers.get('cache-control'),'no-store')
        output=' '.join(logs.output)
        for secret in ('do-not-log-token','do-not-log-password','do-not-log-query'):self.assertNotIn(secret,output)
        self.assertIn('/api/auth/sign-out',output)

    def test_cross_origin_authentication_errors_remain_visible_to_browser(self):
        client=TestClient(server.app);self.addCleanup(client.close)
        with patch.object(server,'DATABASE_URL',''):
            response=client.get('/api/orders',headers={'Origin':'http://localhost:8081'})
        self.assertEqual(response.status_code,401)
        self.assertEqual(response.headers.get('access-control-allow-origin'),'http://localhost:8081')
        self.assertTrue(response.headers.get('x-request-id'))

    def test_demo_limiter_expiry_and_bound(self):
        limiter=security.MemoryLoginLimiter()
        with patch.object(security.time,'monotonic',return_value=0):
            for _ in range(2):limiter.reserve([('key',2)])
            with self.assertRaises(server.HTTPException) as error:limiter.reserve([('key',2)])
            self.assertEqual(error.exception.status_code,429)
        with patch.object(security.time,'monotonic',return_value=301):limiter.reserve([('key',2)])
        with patch.object(security.time,'monotonic',return_value=302),patch.object(security,'MAX_BUCKETS',1),self.assertRaises(server.HTTPException):limiter.reserve([('other',2)])

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Set a disposable PostgreSQL database')
class SecurityPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixtures.StoreOperationsAPITests;cls.fixture.setUpClass()
        cls.addClassCleanup(cls.fixture.doClassCleanups);cls.client=cls.fixture.client

    def user(self,legacy=False):
        uid=uuid.uuid4().hex;salt='fixture-salt';password='Fixture-password-123';token='fixture-'+uid;email=uid+'@example.invalid'
        value=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),120000).hex() if legacy else security.hash_password(password,salt)
        with server.db() as conn:
            conn.execute("INSERT INTO staff_users(id,name,email,role,business_id,location_id,password_salt,password_hash) VALUES (%s,'Security fixture',%s,'counter',%s,%s,%s,%s)",(uid,email,self.fixture.brand,self.fixture.stores[0],salt,value))
            conn.execute("INSERT INTO user_role_assignments(id,user_id,role,scope_type,brand_id,store_id) VALUES (%s,%s,'counter','store',%s,%s)",(uid+'-role',uid,self.fixture.brand,self.fixture.stores[0]))
            conn.execute('INSERT INTO staff_sessions(token,staff_id,active_brand_id,active_store_id) VALUES (%s,%s,%s,%s)',(token,uid,self.fixture.brand,self.fixture.stores[0]))
        return uid,email,password,token

    def test_parallel_login_budget_and_expiry(self):
        email='unknown-'+uuid.uuid4().hex+'@example.invalid'
        with patch.object(server,'hash_password',return_value='dummy'),ThreadPoolExecutor(max_workers=12) as pool:
            responses=list(pool.map(lambda _:self.client.post('/api/auth/sign-in',json={'email':email,'password':'wrong-password'}),range(12)))
        self.assertEqual(sum(r.status_code==401 for r in responses),10)
        self.assertEqual(sum(r.status_code==429 for r in responses),2)
        self.assertTrue(all('retry-after' in r.headers for r in responses if r.status_code==429))
        with server.db() as conn:conn.execute("UPDATE auth_rate_limits SET expires_at=NOW()-INTERVAL '1 second' WHERE key=%s",(security.rate_keys(email,'testclient')[0][0],))
        with patch.object(server,'hash_password',return_value='dummy'):self.assertEqual(self.client.post('/api/auth/sign-in',json={'email':email,'password':'wrong'}).status_code,401)

    def test_legacy_login_upgrade_and_no_hash_exposure(self):
        uid,email,password,_=self.user(True)
        response=self.client.post('/api/auth/sign-in',json={'email':email,'password':password})
        self.assertEqual(response.status_code,200,response.text)
        for path in ('/api/auth/me','/api/context'):
            payload=self.client.get(path,headers={'X-Session-Token':response.json()['token']}).json()
            self.assertNotIn('password_hash',payload['staff']);self.assertNotIn('password_salt',payload['staff'])
        with server.db() as conn:self.assertTrue(conn.execute('SELECT password_hash FROM staff_users WHERE id=%s',(uid,)).fetchone()['password_hash'].startswith('pbkdf2_sha256$600000$'))

    def test_password_change_revocation_expired_and_disabled_sessions(self):
        uid,_,_,token=self.user();headers={'X-Session-Token':token}
        self.assertEqual(self.client.get('/api/orders',headers=headers).status_code,200)
        response=self.fixture.request('admin','put','/api/admin/staff/'+uid,{'password':'Changed-password-123'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/orders',headers=headers).status_code,401)
        uid,_,_,token=self.user()
        with server.db() as conn:conn.execute("UPDATE staff_sessions SET expires_at=NOW()-INTERVAL '1 second' WHERE token=%s",(token,))
        self.assertEqual(self.client.get('/api/context',headers={'X-Session-Token':token}).status_code,401)
        uid,_,_,token=self.user()
        with server.db() as conn:conn.execute('UPDATE staff_users SET active=FALSE WHERE id=%s',(uid,))
        self.assertEqual(self.client.get('/api/orders',headers={'X-Session-Token':token}).status_code,401)

    def test_removed_role_denies_existing_session(self):
        uid,_,_,token=self.user()
        with server.db() as conn:conn.execute('UPDATE user_role_assignments SET active=FALSE WHERE user_id=%s',(uid,))
        self.assertEqual(self.client.get('/api/orders',headers={'X-Session-Token':token}).status_code,403)

    def test_pool_reuse_isolates_tenants_and_maintenance(self):
        for scope in ((self.fixture.brand,self.fixture.stores[0]),(self.fixture.foreign_brand,self.fixture.stores[3]),None):
            marker=current_scope.set(scope)
            try:
                with server.db() as conn:self.assertTrue(all(scope and row['location_id']==scope[1] for row in conn.execute('SELECT DISTINCT location_id FROM orders').fetchall()))
            finally:current_scope.reset(marker)
        with server.db(maintenance=True) as conn:self.assertGreater(conn.execute('SELECT COUNT(*) AS n FROM orders').fetchone()['n'],0)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM orders').fetchone()['n'],0)
        self.assertLessEqual(get_pool(server.DATABASE_URL).get_stats()['pool_size'],8)

    def test_concurrent_fields_payments_status_preserve_all_changes(self):
        order=self.fixture().order();oid=order['id']
        operations=[('put','/api/orders/'+oid,{'notes':'Concurrent note'}),('put','/api/orders/'+oid,{'due_at':'2030-01-02T12:00:00Z'}),('put','/api/orders/'+oid+'/status',{'status':'cleaning'})]+[('post','/api/orders/'+oid+'/payments',{'amount':1}) for _ in range(10)]
        with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(lambda operation:self.fixture.request('source',*operation),operations))
        self.assertTrue(all(r.status_code==200 for r in responses),[r.text for r in responses if r.status_code!=200])
        data=self.fixture.ok('source','get','/api/orders/'+oid)
        self.assertEqual(data['notes'],'Concurrent note');self.assertEqual(data['due_at'],'2030-01-02T12:00:00Z');self.assertEqual(data['status'],'cleaning');self.assertEqual(data['payment_status'],'paid')
        payments=self.fixture.ok('source','get','/api/orders/'+oid+'/payments')
        self.assertEqual(payments['paid_total'],10);self.assertEqual(len(payments['payments']),10)

    def test_failed_mutation_rolls_back(self):
        order=self.fixture().order()
        response=self.fixture.request('source','put','/api/orders/'+order['id'],{'items':[{'service_id':'foreign','unit_price':99,'quantity':1}]})
        self.assertEqual(response.status_code,404);self.assertIsNone(server.transaction_connection.get())
        self.assertEqual(self.fixture.ok('source','get','/api/orders/'+order['id'])['total'],10)

    def test_nonfinite_and_invalid_payments_leave_no_transaction(self):
        oid=self.fixture().order()['id']
        for amount in ('NaN','Infinity','not-a-number'):
            self.assertEqual(self.fixture.request('source','post','/api/orders/'+oid+'/payments',{'amount':amount}).status_code,400)
        self.assertEqual(self.fixture.ok('source','get','/api/orders/'+oid+'/payments')['payments'],[])

    def test_staff_partial_edit_keeps_role_and_explicit_assignments(self):
        uid,_,_,_=self.user()
        with server.db() as conn:
            conn.execute("UPDATE staff_users SET role='manager' WHERE id=%s",(uid,))
            before=conn.execute('SELECT id,role,active FROM user_role_assignments WHERE user_id=%s ORDER BY id',(uid,)).fetchall()
        response=self.fixture.request('admin','put','/api/admin/staff/'+uid,{'name':'Renamed fixture'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['role'],'manager')
        with server.db() as conn:self.assertEqual(conn.execute('SELECT id,role,active FROM user_role_assignments WHERE user_id=%s ORDER BY id',(uid,)).fetchall(),before)

    def test_explicit_matching_assignment_does_not_block_role_edit(self):
        uid,_,_,_=self.user()
        with server.db() as conn:
            conn.execute("INSERT INTO user_role_assignments(id,user_id,role,scope_type,brand_id,store_id) VALUES (%s,%s,'processing','store',%s,%s)",(uid+'-processing',uid,self.fixture.brand,self.fixture.stores[0]))
        response=self.fixture.request('admin','put','/api/admin/staff/'+uid,{'role':'processing'})
        self.assertEqual(response.status_code,200,response.text)
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM user_role_assignments WHERE user_id=%s AND role='processing' AND active=TRUE",(uid,)).fetchone()['n'],1)

    def test_assembly_override_uses_assignments_not_legacy_role(self):
        uid,_,_,token=self.user()
        with server.db() as conn:conn.execute("UPDATE staff_users SET role='manager' WHERE id=%s",(uid,))
        order=self.fixture().order();path='/api/orders/'+order['id']+'/assembly/complete'
        self.assertEqual(self.client.post(path,headers={'X-Session-Token':token},json={'override':True}).status_code,403)
        self.assertEqual(self.fixture.request('admin','post',path,{'override':True}).status_code,200)

    def test_parallel_order_creation_uses_distinct_numbers(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            orders=list(pool.map(lambda _:self.fixture().order(),range(6)))
        self.assertEqual(len({order['order_number'] for order in orders}),6)
        self.assertEqual(len({order['id'] for order in orders}),6)

    def test_failed_order_creation_does_not_leave_customer(self):
        phone=uuid.uuid4().hex
        response=self.fixture.request('source','post','/api/orders',{'customer_name':'Invalid promo','customer_phone':phone,'promo_code':'not-a-real-offer','items':[{'service_id':'wash','service_name':'Wash','quantity':1,'unit_price':5}]})
        self.assertEqual(response.status_code,400)
        marker=current_scope.set((self.fixture.brand,self.fixture.stores[0]))
        try:
            with server.db() as conn:self.assertIsNone(conn.execute('SELECT id FROM customers WHERE phone=%s',(phone,)).fetchone())
        finally:current_scope.reset(marker)

    def test_overlapping_recurring_generation_conflicts_instead_of_duplicate(self):
        order=self.fixture().order()
        plan=self.fixture.ok('admin','post','/api/subscriptions/plans',{'name':'Concurrency plan','eligible_service_ids':['wash']})
        subscription=self.fixture.ok('source','post','/api/customers/'+order['customer']['id']+'/subscriptions',{'plan_id':plan['id']})
        started=threading.Event(); release=threading.Event(); original=server.create_order
        def pause(*args,**kwargs):
            started.set()
            if not release.wait(10):raise AssertionError('Recurring generation failed to release')
            return original(*args,**kwargs)
        path='/api/subscriptions/'+subscription['id']+'/generate-order'
        with patch.object(server,'create_order',side_effect=pause),ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.fixture.request,'source','post',path,{})
            try:
                self.assertTrue(started.wait(10))
                second=self.fixture.request('source','post',path,{})
                self.assertEqual(second.status_code,409,second.text)
            finally:release.set()
            self.assertEqual(first.result(timeout=10).status_code,200)

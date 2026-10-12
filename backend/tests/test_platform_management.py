"""Platform control-plane and tenant lifecycle regressions on disposable PostgreSQL."""
import hashlib
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from psycopg.errors import InsufficientPrivilege
import server
import platform_management as platform
from tests import test_postgres_isolation as fixtures
from tenant_scope import current_scope

class PlatformValidationTests(unittest.TestCase):
    def test_policy_validation_rejects_unknown_keys_nonbooleans_and_invalid_limits(self):
        for value in ({'secret':True},{'ai':1},[]):
            with self.assertRaises(server.HTTPException):platform.validate_features(value)
        for value in ({'staff':0},{'stores':True},{'staff':10001},{'unknown':2}):
            with self.assertRaises(server.HTTPException):platform.validate_limits(value)
        self.assertEqual(platform.validate_overrides({'features':{'ai':True},'limits':{'stores':None}})['features'],{'ai':True})
        with self.assertRaises(server.HTTPException):platform.valid_email('not-an-email')

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Set an explicitly disposable PostgreSQL database')
class PlatformAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixtures.PostgresIsolationTests;cls.fixture.setUpClass()
        cls.addClassCleanup(cls.fixture.doClassCleanups);cls.client=cls.fixture.client
        server.init_db();server.init_db()

    def request(self,actor,method,path,body=None):return self.fixture.request(actor,method,path,body)
    def ok(self,actor,method,path,body=None):return self.fixture.ok(actor,method,path,body)
    def brand(self,plan='enterprise',email=None):
        suffix=uuid.uuid4().hex
        return self.ok('super','post','/api/platform/brands',{'name':'Platform fixture '+suffix,'slug':'platform-'+suffix,'plan_code':plan,'initial_store':{'name':'Initial store','store_code':'MAIN'},'owner_email':email or suffix+'@example.invalid'})
    def accept(self,brand,password='Owner-password-123'):
        response=self.client.post('/api/auth/owner-invitations/accept',json={'token':brand['invitation']['token'],'name':'Invited owner','password':password})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()
    def owner_session(self,brand,password='Owner-password-123'):
        self.accept(brand,password)
        response=self.client.post('/api/auth/sign-in',json={'email':brand['invitation']['email'],'password':password})
        self.assertEqual(response.status_code,200,response.text)
        return {'X-Session-Token':response.json()['token']}

    def test_existing_brands_keep_compatibility_features_and_limits(self):
        with server.db() as conn:
            row=conn.execute('SELECT plan_code FROM brands WHERE id=%s',(self.fixture.brand_a,)).fetchone()
            self.assertEqual(row['plan_code'],'legacy')
            _,policy=platform.brand_policy(conn,self.fixture.brand_a)
            self.assertTrue(all(policy['features'].values()))
            self.assertIsNone(policy['limits']['stores'])
        self.assertEqual(self.request(0,'get','/api/handoffs').status_code,200)

    def test_non_super_users_cannot_manage_platform_or_read_global_health_audit(self):
        brand=self.brand()
        for actor in (0,1,2):
            for method,path,body in [('get','/api/platform/plans',None),('get','/api/platform/health',None),('get','/api/platform/audit',None),('get','/api/platform/brands/'+brand['id'],None),('put','/api/platform/brands/'+brand['id'],{'plan_code':'legacy'}),('post','/api/platform/brands/'+brand['id']+'/owner-invitations',{'email':'intruder@example.invalid','store_id':brand['initial_store']['id']})]:
                self.assertEqual(self.request(actor,method,path,body).status_code,403)
        self.assertEqual(self.client.get('/api/platform/health').status_code,401)

    def test_onboarding_is_atomic_and_tokens_are_hashed_and_not_listed_or_audited(self):
        suffix=uuid.uuid4().hex
        response=self.request('super','post','/api/platform/brands',{'name':'Invalid invitation','slug':suffix,'initial_store':{'name':'Store','store_code':'MAIN'},'owner_email':'invalid'})
        self.assertEqual(response.status_code,400)
        with server.db() as conn:self.assertIsNone(conn.execute('SELECT id FROM brands WHERE slug=%s',(suffix,)).fetchone())
        brand=self.brand();token=brand['invitation']['token']
        with server.db() as conn:
            row=conn.execute('SELECT token_hash FROM owner_invitations WHERE id=%s',(brand['invitation']['id'],)).fetchone()
            self.assertEqual(row['token_hash'],hashlib.sha256(token.encode()).hexdigest())
        detail=self.ok('super','get','/api/platform/brands/'+brand['id'])
        history=self.ok('super','get','/api/platform/audit?brand_id='+brand['id'])
        self.assertNotIn(token,json.dumps(detail,default=str));self.assertNotIn('token_hash',json.dumps(detail,default=str));self.assertNotIn(token,json.dumps(history,default=str))
        self.assertEqual(detail['usage']['pending_owner_seats'],1)

    def test_invitation_acceptance_is_single_use_and_grants_brand_only(self):
        brand=self.brand();payload={'token':brand['invitation']['token'],'name':'Owner','password':'Owner-password-123'}
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:self.client.post('/api/auth/owner-invitations/accept',json=payload),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,410])
        uid=next(r.json()['staff_id'] for r in responses if r.status_code==200)
        with server.db() as conn:
            roles=conn.execute('SELECT role,brand_id,scope_type FROM user_role_assignments WHERE user_id=%s',(uid,)).fetchall()
        self.assertEqual([(r['role'],r['brand_id'],r['scope_type']) for r in roles],[('brand_admin',brand['id'],'brand')])
        preview=self.client.post('/api/auth/owner-invitations/preview',json={'token':payload['token']})
        self.assertEqual(preview.status_code,410)

    def test_invitation_replacement_revocation_expiry_and_foreign_store_are_safe(self):
        brand=self.brand();old=brand['invitation'];base='/api/platform/brands/'+brand['id']+'/owner-invitations'
        replacement=self.ok('super','post',base,{'email':old['email'],'store_id':brand['initial_store']['id']})
        self.assertEqual(self.client.post('/api/auth/owner-invitations/preview',json={'token':old['token']}).status_code,410)
        self.assertEqual(self.request('super','post',base,{'email':'other@example.invalid','store_id':self.fixture.stores[2]}).status_code,404)
        self.ok('super','post','/api/platform/owner-invitations/'+replacement['id']+'/revoke')
        self.assertEqual(self.client.post('/api/auth/owner-invitations/accept',json={'token':replacement['token'],'name':'Owner','password':'Owner-password-123'}).status_code,410)
        newer=self.ok('super','post',base,{'email':old['email'],'store_id':brand['initial_store']['id']})
        with server.db() as conn:conn.execute("UPDATE owner_invitations SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(newer['id'],))
        self.assertEqual(self.client.post('/api/auth/owner-invitations/preview',json={'token':newer['token']}).status_code,410)
        with server.db() as conn:self.assertEqual(platform.usage(conn,brand['id'])['pending_owner_seats'],0)

    def test_existing_account_requires_identity_proof_and_is_not_reset(self):
        first=self.brand();accepted=self.accept(first)
        second=self.brand(email=first['invitation']['email'])
        with server.db() as conn:before=conn.execute('SELECT password_hash FROM staff_users WHERE id=%s',(accepted['staff_id'],)).fetchone()['password_hash']
        token=second['invitation']['token']
        self.assertEqual(self.client.post('/api/auth/owner-invitations/accept',json={'token':token,'name':'Hijack','password':'Wrong-password-123'}).status_code,401)
        correct=self.client.post('/api/auth/owner-invitations/accept',json={'token':token,'password':'Owner-password-123'})
        self.assertEqual(correct.status_code,200,correct.text);self.assertEqual(correct.json()['staff_id'],accepted['staff_id'])
        with server.db() as conn:self.assertEqual(conn.execute('SELECT password_hash FROM staff_users WHERE id=%s',(accepted['staff_id'],)).fetchone()['password_hash'],before)

    def test_suspend_revokes_brand_sessions_but_platform_can_reactivate_and_other_brand_stays_active(self):
        brand=self.brand();headers=self.owner_session(brand)
        body={'status':'suspended','reason':'Lifecycle regression fixture'}
        self.ok('super','put','/api/platform/brands/'+brand['id'],body)
        self.assertEqual(self.client.get('/api/orders',headers=headers).status_code,401)
        self.assertEqual(self.client.post('/api/auth/sign-in',json={'email':brand['invitation']['email'],'password':'Owner-password-123'}).status_code,403)
        self.assertEqual(self.request(0,'get','/api/orders').status_code,200)
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'status':'active','reason':'Reactivated for regression'})
        self.assertEqual(self.client.get('/api/orders',headers=headers).status_code,401)
        login=self.client.post('/api/auth/sign-in',json={'email':brand['invitation']['email'],'password':'Owner-password-123'})
        self.assertEqual(login.status_code,200,login.text)
        events=self.ok('super','get','/api/platform/audit?brand_id='+brand['id'])['events']
        self.assertTrue({'brand_suspended','brand_reactivated'}<={e['action'] for e in events})

    def test_suspended_brand_cannot_accept_pending_invitation(self):
        brand=self.brand()
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'status':'suspended','reason':'Pending owner hold'})
        response=self.client.post('/api/auth/owner-invitations/accept',json={'token':brand['invitation']['token'],'name':'Owner','password':'Owner-password-123'})
        self.assertEqual(response.status_code,403)

    def test_entitlements_restrict_direct_api_and_store_settings_cannot_enable_them(self):
        brand=self.brand('starter');headers=self.owner_session(brand)
        self.assertEqual(self.client.put('/api/settings',headers=headers,json={'offers_enabled':True,'pickup_enabled':True}).status_code,200)
        for method,path,body in [('get','/api/offers',None),('post','/api/offers',{'name':'Bypass','code':'BYPASS'}),('get','/api/handoffs',None),('get','/api/ai/status',None)]:
            args={'headers':headers}
            if body is not None:args['json']=body
            self.assertEqual(getattr(self.client,method)(path,**args).status_code,403)
        self.assertEqual(self.client.get('/api/orders',headers=headers).status_code,200)
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'features':{'offers':True}}})
        self.assertEqual(self.client.get('/api/offers',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/handoffs',headers=headers).status_code,403)
        with self.assertRaises(server.HTTPException):platform.validate_overrides({'features':{'not_supported':True}})

    def test_store_quota_and_concurrent_staff_creation_reserve_owner_seats(self):
        brand=self.brand('starter');headers=self.owner_session(brand)
        response=self.client.post('/api/brand/stores',headers=headers,json={'brand_id':brand['id'],'name':'Over quota','store_code':'SECOND'})
        self.assertEqual(response.status_code,409,response.text)
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'limits':{'staff':2}}})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda index:self.client.post('/api/admin/staff',headers=headers,json={'name':'Quota staff','email':uuid.uuid4().hex+'@example.invalid','password':'Staff-password-123','role':'counter'}),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.request('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'limits':{'staff':1}}}).status_code,409)

    def test_shared_plan_update_and_overrides_are_enforced_and_low_downgrade_is_rejected(self):
        code='fixture-'+uuid.uuid4().hex[:12]
        self.ok('super','post','/api/platform/plans',{'code':code,'name':'Fixture plan','features':platform.ALL_FEATURES,'limits':{'stores':3,'staff':5}})
        brand=self.brand(code);headers=self.owner_session(brand)
        self.ok('super','put','/api/platform/plans/'+code,{'features':{**platform.ALL_FEATURES,'ai':False}})
        self.assertEqual(self.client.get('/api/ai/status',headers=headers).status_code,403)
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'features':{'ai':True}}})
        self.assertEqual(self.client.get('/api/ai/status',headers=headers).status_code,200)
        self.assertEqual(self.request('super','put','/api/platform/plans/legacy',{'name':'Changed'}).status_code,400)

    def test_pending_invites_reserve_seats_and_replacement_does_not_consume_extra(self):
        brand=self.brand('starter')
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'limits':{'staff':1}}})
        path='/api/platform/brands/'+brand['id']+'/owner-invitations'
        self.assertEqual(self.request('super','post',path,{'email':'extra@example.invalid','store_id':brand['initial_store']['id']}).status_code,409)
        new=self.ok('super','post',path,{'email':brand['invitation']['email'],'store_id':brand['initial_store']['id']})
        self.assertNotEqual(new['token'],brand['invitation']['token'])
        self.accept({**brand,'invitation':new})
        with server.db() as conn:self.assertEqual(platform.usage(conn,brand['id']),{'stores':1,'staff':1,'pending_owner_seats':0})

    def test_control_plane_health_is_minimal_and_audit_is_append_only(self):
        health=self.ok('super','get','/api/platform/health')
        self.assertTrue(health['schema_ready']);self.assertNotIn('customers',health)
        brand=self.brand()
        with server.db() as conn:
            event=conn.execute('SELECT id FROM platform_audit WHERE brand_id=%s LIMIT 1',(brand['id'],)).fetchone()
            for sql in ('UPDATE platform_audit SET action=\'rewritten\' WHERE id=%s','DELETE FROM platform_audit WHERE id=%s'):
                with self.assertRaises(InsufficientPrivilege):conn.execute(sql,(event['id'],))

    def test_disabling_handoffs_with_open_custody_is_rejected(self):
        brand=self.brand();headers=self.owner_session(brand)
        destination=self.client.post('/api/brand/stores',headers=headers,json={'brand_id':brand['id'],'name':'Plant','store_code':'PLANT'}).json()
        service=self.client.post('/api/services',headers=headers,json={'id':'platform-wash','category':'Laundry','name':'Wash','pricing_type':'per_item','base_price':5})
        self.assertEqual(service.status_code,200,service.text)
        order=self.client.post('/api/orders',headers=headers,json={'customer_name':'Custody fixture','customer_phone':uuid.uuid4().hex,'items':[{'service_id':'platform-wash','service_name':'Wash','quantity':1,'unit_price':5}]}).json()
        handoff=self.client.post('/api/handoffs',headers=headers,json={'order_id':order['id'],'destination_store_id':destination['id']})
        self.assertEqual(handoff.status_code,200,handoff.text)
        change={'entitlement_overrides':{'features':{'handoffs':False}}}
        self.assertEqual(self.request('super','put','/api/platform/brands/'+brand['id'],change).status_code,409)
        self.assertEqual(self.client.post('/api/handoffs/'+handoff.json()['id']+'/actions',headers=headers,json={'action':'cancel'}).status_code,200)
        self.ok('super','put','/api/platform/brands/'+brand['id'],change)
        self.assertEqual(self.client.get('/api/handoffs',headers=headers).status_code,403)

    def test_quota_inactive_staff_and_role_assignment_bypasses_are_blocked(self):
        brand=self.brand('starter');owner=self.owner_session(brand)
        self.ok('super','put','/api/platform/brands/'+brand['id'],{'entitlement_overrides':{'limits':{'staff':1}}})
        inactive=self.client.post('/api/admin/staff',headers=owner,json={'name':'Inactive quota','email':uuid.uuid4().hex+'@example.invalid','password':'Staff-password-123','role':'counter','active':False})
        self.assertEqual(inactive.status_code,200,inactive.text)
        self.assertEqual(self.client.put('/api/admin/staff/'+inactive.json()['id'],headers=owner,json={'active':True}).status_code,409)
        other_uid=self.fixture.users[0]
        assignments=[{'role':'counter','scope_type':'store','brand_id':brand['id'],'store_id':brand['initial_store']['id']}]
        self.assertEqual(self.request('super','put','/api/admin/staff/'+other_uid+'/roles',{'assignments':assignments}).status_code,409)

    def test_signin_and_suspension_are_serialized_without_reviving_a_session(self):
        import threading
        brand=self.brand();self.accept(brand)
        started=threading.Event();release=threading.Event();original=server.verify_password
        def verify(*args):
            started.set()
            if not release.wait(10):raise AssertionError('Sign-in synchronization timed out')
            return original(*args)
        with patch.object(server,'verify_password',side_effect=verify),ThreadPoolExecutor(max_workers=2) as pool:
            login=pool.submit(self.client.post,'/api/auth/sign-in',json={'email':brand['invitation']['email'],'password':'Owner-password-123'})
            try:
                self.assertTrue(started.wait(10))
                suspended=pool.submit(self.request,'super','put','/api/platform/brands/'+brand['id'],{'status':'suspended','reason':'Concurrent sign-in hold'})
            finally:release.set()
            response=login.result(timeout=10);self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(suspended.result(timeout=10).status_code,200)
        self.assertEqual(self.client.get('/api/orders',headers={'X-Session-Token':response.json()['token']}).status_code,401)

    def test_inactive_existing_identity_is_not_invited_and_onboarding_rolls_back(self):
        first=self.brand();accepted=self.accept(first)
        with server.db() as conn:conn.execute('UPDATE staff_users SET active=FALSE WHERE id=%s',(accepted['staff_id'],))
        slug='disabled-'+uuid.uuid4().hex
        response=self.request('super','post','/api/platform/brands',{'name':'Disabled identity onboarding','slug':slug,'owner_email':first['invitation']['email'],'initial_store':{'name':'Store','store_code':'MAIN'}})
        self.assertEqual(response.status_code,403)
        with server.db() as conn:self.assertIsNone(conn.execute('SELECT id FROM brands WHERE slug=%s',(slug,)).fetchone())

    def test_onboarding_status_tracks_owner_acceptance_and_active_store(self):
        brand=self.brand()
        def status():
            return next(row for row in self.ok('super','get','/api/platform/brands')['brands'] if row['id']==brand['id'])['onboarding_status']
        self.assertEqual(status(),'owner_invited')
        self.accept(brand);self.assertEqual(status(),'ready')
        self.ok('super','put','/api/brand/stores/'+brand['initial_store']['id'],{'active':False})
        self.assertEqual(status(),'needs_store')

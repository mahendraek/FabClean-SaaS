import base64
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from psycopg.errors import InsufficientPrivilege, RaiseException
import notifications as n
import server
from tools import notification_worker
from tenant_scope import current_scope
from tests import test_postgres_isolation as fixtures


class NotificationValidationTests(unittest.TestCase):
    def test_provider_requests_use_persisted_recipient_and_scope_metadata(self):
        marker=current_scope.set(('fixture-brand','fixture-store'))
        try:
            row={'id':'fixture-message','channel':'email','message':'Persisted receipt','delivery':{'recipient':'customer@example.com','subject':'Fixture subject'}}
            with patch.object(server,'SENDGRID_API_KEY','synthetic-key'),patch.object(n.httpx,'post',return_value=httpx.Response(202,headers={'X-Message-Id':'fixture-id'})) as send:
                result=n.provider_send(server,row,'sender@example.com')
            self.assertEqual(result['status'],'accepted')
            body=send.call_args.kwargs['json'];self.assertEqual(body['personalizations'][0]['to'],[{'email':'customer@example.com'}])
            self.assertEqual(body['personalizations'][0]['custom_args']['fabclean_store_id'],'fixture-store')
            self.assertEqual(body['content'][0]['value'],'Persisted receipt')
        finally:current_scope.reset(marker)

    def test_worker_uses_scoped_pending_queue_and_preserves_conflict_outcomes(self):
        calls=[]
        def handle(request):
            calls.append(request.url.path)
            if request.method=='GET':
                self.assertEqual(request.url.params['pending'],'true')
                return httpx.Response(200,json={'notifications':[{'id':'queued','status':'queued','delivery':{}},{'id':'terminal','status':'accepted','delivery':{}}]})
            return httpx.Response(409,json={'detail':'Already claimed'})
        with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(handle)) as client:
            self.assertEqual(notification_worker.run_once(client),0)
        self.assertEqual(calls,['/api/notifications/outbox','/api/notifications/outbox/queued/dispatch'])

    def test_template_fields_cannot_access_attributes_or_hide_receipt_totals(self):
        n.validate_settings({'notification_templates': {'order_receipt': 'Thanks {name}, {business_name} {order_number}'}})
        for template in ('{name.__class__}', '{name[0]}', '{name!r}', '{total}', '{name:>1000000}', '{'):
            with self.assertRaises(server.HTTPException):
                n.validate_settings({'notification_templates': {'order_receipt': template}})

    def test_contact_and_channel_consent_validation(self):
        self.assertTrue(n.valid_contact('sms', '+15550102030'))
        self.assertFalse(n.valid_contact('sms', '5550102030'))
        self.assertFalse(n.valid_contact('email', 'mail@example.com\nBcc:other@example.com'))
        self.assertFalse(n.permitted({'email_opt_in': True}, 'order_receipt', 'email'))


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'), 'Disposable PostgreSQL required')
class NotificationAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixtures.PostgresIsolationTests
        cls.f.setUpClass()
        cls.addClassCleanup(cls.f.doClassCleanups)
        cls.client = cls.f.client

    def setUp(self):
        self.f.ok(0,'put','/api/settings',{'currency':'USD','notifications_enabled':False})
        self.order = self.f.ok(0, 'post', '/api/orders', {'customer_name': 'Receipt Customer',
            'customer_phone': '+1555'+uuid.uuid4().hex[:7].translate(str.maketrans('abcdef', '123456')),
            'customer_email': 'receipt-'+uuid.uuid4().hex+'@example.com',
            'items': [{'service_id': 'shared-service', 'service_name': 'Wash', 'quantity': 1, 'unit_price': 10}]})
        self.cid = self.order['customer']['id']
        self.f.ok(0, 'put', '/api/settings', {'notifications_enabled': True, 'business_name': 'Fixture Laundry',
            'notification_email_sender': 'sender@example.com', 'notification_sms_sender': '+15550102030', 'notification_templates': {}})
        self.key_patch = patch.object(server, 'SENDGRID_API_KEY', 'synthetic-test-key')
        self.key_patch.start(); self.addCleanup(self.key_patch.stop)

    def prefs(self, **values):
        return self.f.ok(0, 'put', '/api/customers/'+self.cid+'/communication-preferences', values)

    def queue(self):
        return self.f.ok(0, 'post', '/api/orders/'+self.order['id']+'/send-receipt')['notifications']

    def consent(self):
        self.prefs(email_opt_in=True, sms_opt_in=True, receipts=True, status_updates=True, consent_note='Synthetic fixture customer consent')

    def whatsapp_consent(self):
        return self.prefs(whatsapp_opt_in=True,receipts=True,consent_note='Synthetic WhatsApp permission')

    def test_whatsapp_requires_separate_consent_and_never_calls_a_provider(self):
        path='/api/orders/'+self.order['id']+'/whatsapp-receipt'
        self.assertEqual(self.f.request(0,'get',path).status_code,409)
        self.consent();self.assertEqual(self.f.request(0,'get',path).status_code,409)
        self.assertEqual(self.f.request(0,'put','/api/customers/'+self.cid+'/communication-preferences',{'whatsapp_opt_in':True}).status_code,400)
        self.whatsapp_consent()
        self.f.ok(0,'put','/api/settings',{'notifications_enabled':False})
        with patch.object(n,'provider_send') as send:
            preview=self.f.ok(0,'get',path)
            result=self.f.ok(0,'post',path,{'fingerprint':preview['fingerprint']})
            send.assert_not_called()
        self.assertEqual(result['phone'],self.order['customer']['phone'])
        self.assertIn('Total: USD 10.00',result['message'])
        events=self.f.ok(0,'get','/api/customers/'+self.cid+'/communication-events')['events']
        self.assertTrue(any(e['event']=='whatsapp_share_prepared' for e in events))
        self.assertFalse(any(e['event'] in ('sent','delivered') for e in events))

    def test_whatsapp_rechecks_optout_payment_changes_and_recipient_changes(self):
        self.whatsapp_consent();path='/api/orders/'+self.order['id']+'/whatsapp-receipt'
        preview=self.f.ok(0,'get',path)
        self.f.ok(0,'post','/api/orders/'+self.order['id']+'/payments',{'amount':5})
        self.assertEqual(self.f.request(0,'post',path,{'fingerprint':preview['fingerprint']}).status_code,409)
        refreshed=self.f.ok(0,'get',path);self.assertEqual(refreshed['receipt']['balance_due'],5)
        with server.db(maintenance=True) as conn:conn.execute("UPDATE customers SET phone='+15550102030' WHERE id=%s",(self.cid,))
        self.assertEqual(self.f.request(0,'post',path,{'fingerprint':refreshed['fingerprint']}).status_code,409)
        current=self.f.ok(0,'get',path)
        self.prefs(whatsapp_opt_in=False)
        self.assertEqual(self.f.request(0,'post',path,{'fingerprint':current['fingerprint']}).status_code,409)

    def test_whatsapp_foreign_store_invalid_phone_and_oversized_receipt_fail_closed(self):
        self.whatsapp_consent();path='/api/orders/'+self.order['id']+'/whatsapp-receipt'
        for actor in (1,2):
            self.assertEqual(self.f.request(actor,'get',path).status_code,404)
            self.assertEqual(self.f.request(actor,'post',path,{'fingerprint':'foreign'}).status_code,404)
        with server.db(maintenance=True) as conn:conn.execute("UPDATE customers SET phone='5550102030' WHERE id=%s",(self.cid,))
        self.assertEqual(self.f.request(0,'get',path).status_code,400)
        with server.db(maintenance=True) as conn:conn.execute("UPDATE customers SET phone='+1 (555) 010-2030' WHERE id=%s",(self.cid,))
        self.assertEqual(self.f.ok(0,'get',path)['phone'],'+15550102030')
        with patch.object(n,'render',return_value=('Subject','x'*6001,{})):
            self.assertEqual(self.f.request(0,'get',path).status_code,400)

    def dispatch(self, row):
        return self.f.request(0, 'post', '/api/notifications/outbox/'+row['id']+'/dispatch')

    def test_default_optout_and_no_receipt_send_without_consent(self):
        prefs = self.f.ok(0, 'get', '/api/customers/'+self.cid+'/communication-preferences')
        self.assertFalse(prefs['email_opt_in'])
        rows = self.queue(); self.assertTrue(all(r['status'] == 'suppressed' for r in rows))
        with patch.object(n, 'provider_send') as send:
            self.assertEqual(self.dispatch(rows[0]).status_code, 409)
            send.assert_not_called()
        r = self.f.request(0, 'put', '/api/customers/'+self.cid+'/communication-preferences', {'email_opt_in': True})
        self.assertEqual(r.status_code, 400)

    def test_receipt_snapshot_branding_and_payment_hook(self):
        self.consent()
        self.f.ok(0, 'put', '/api/settings', {'notification_templates': {'order_receipt': 'Thank you {name} from {business_name}'}})
        rows = self.queue(); email = rows[0]
        self.assertIn('Fixture Laundry', email['message'])
        self.assertIn('Total: USD 10.00', email['message'])
        self.assertEqual(email['delivery']['receipt']['total'], self.order['total'])
        payment = self.f.ok(0, 'post', '/api/orders/'+self.order['id']+'/payments', {'amount': 5})
        outbox = self.f.ok(0, 'get', '/api/notifications/outbox')['notifications']
        paid = next(r for r in outbox if r['order_id'] == self.order['id'] and r['notification_type'] == 'payment_receipt')
        self.assertEqual(paid['delivery']['receipt']['payment']['id'], payment['payment']['id'])
        self.assertEqual(paid['delivery']['receipt']['paid_total'], 5)
        self.assertEqual(self.queue()[0]['delivery']['receipt']['balance_due'], 5)
        self.assertEqual(email['delivery']['receipt']['balance_due'], 10)

    def test_concurrent_queue_and_dispatch_are_idempotent(self):
        self.consent()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.queue(), range(2)))
        self.assertEqual(results[0][0]['id'], results[1][0]['id'])
        row = results[0][0]
        with patch.object(n, 'provider_send', return_value={'status': 'accepted', 'provider_message_id': 'fixture-email'}) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.dispatch(row), range(2)))
            self.assertEqual(sorted(r.status_code for r in results), [200, 409])
            self.assertEqual(send.call_count, 1)

    def test_optout_after_queue_is_rechecked_before_dispatch(self):
        self.consent(); row = self.queue()[0]
        self.prefs(email_opt_in=False)
        with patch.object(n, 'provider_send') as send:
            r = self.dispatch(row)
            self.assertEqual(r.json()['status'], 'suppressed')
            send.assert_not_called()

    def test_unknown_timeout_cannot_be_resent_and_raw_error_is_hidden(self):
        self.consent(); row = self.queue()[0]
        with patch.object(n, 'provider_send', side_effect=httpx.ReadTimeout('do-not-expose-provider-key')):
            response = self.dispatch(row)
        self.assertEqual(response.json()['status'], 'unknown')
        self.assertNotIn('do-not-expose-provider-key', response.text)
        with patch.object(n, 'provider_send') as send:
            self.assertEqual(self.dispatch(row).status_code, 409)
            send.assert_not_called()

    def test_rate_limit_retry_backoff_and_max_attempts(self):
        self.consent(); row = self.queue()[0]
        rejection = {'status': 'failed', 'retryable': True, 'error_message': 'Provider rejected request (HTTP 429)'}
        with patch.object(n, 'provider_send', return_value=rejection) as send:
            self.assertEqual(self.dispatch(row).json()['delivery']['attempts'], 1)
            self.assertEqual(self.dispatch(row).status_code, 409)
            self.assertEqual(send.call_count, 1)
            future = n.now()+timedelta(hours=1)
            with patch.object(n, 'now', return_value=future):
                self.assertEqual(self.dispatch(row).json()['delivery']['attempts'], 2)
            with patch.object(n, 'now', return_value=future+timedelta(hours=1)):
                self.assertEqual(self.dispatch(row).json()['delivery']['attempts'], 3)
            with patch.object(n, 'now', return_value=future+timedelta(hours=2)):
                self.assertEqual(self.dispatch(row).status_code, 409)
            self.assertEqual(send.call_count, 3)

    def test_foreign_access_and_forced_rls(self):
        self.consent(); row = self.queue()[0]
        for actor in (1, 2):
            self.assertEqual(self.f.request(actor, 'post', '/api/notifications/outbox/'+row['id']+'/dispatch').status_code, 404)
            self.assertEqual(self.f.request(actor, 'get', '/api/customers/'+self.cid+'/communication-preferences').status_code, 404)
            self.assertFalse(any(r['id'] == row['id'] for r in self.f.ok(actor, 'get', '/api/notifications/outbox')['notifications']))
        marker = current_scope.set((self.f.brand_b, self.f.stores[2]))
        try:
            with server.db() as conn:
                for table in ('notification_preferences', 'notification_events'):
                    flags = conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
                    self.assertTrue(flags['relrowsecurity'] and flags['relforcerowsecurity'])
                self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM notification_preferences WHERE customer_id=%s',(self.cid,)).fetchone()['n'],0)
            with self.assertRaises(InsufficientPrivilege), server.db() as conn:
                conn.execute('INSERT INTO notification_preferences(customer_id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb)',(self.cid,self.f.brand_a,self.f.stores[0],'{}'))
        finally:
            current_scope.reset(marker)
        server.init_db(); server.init_db()

    def test_invalid_contact_is_blocked_and_no_provider_call_occurs(self):
        self.consent(); rows = self.queue()
        with patch.object(server, 'SENDGRID_API_KEY', ''), patch.object(n, 'provider_send') as send:
            r = self.dispatch(rows[0])
            self.assertEqual(r.json()['status'], 'blocked'); send.assert_not_called()

    def test_fresh_receipt_after_optin_and_changed_contact_uses_new_consent(self):
        suppressed=self.queue()[0]
        self.consent();row=self.queue()[0]
        self.assertNotEqual(row['id'],suppressed['id']);self.assertEqual(row['status'],'queued')
        with server.db(maintenance=True) as conn:conn.execute("UPDATE customers SET email='changed@example.com' WHERE id=%s",(self.cid,))
        with patch.object(n,'provider_send') as send:
            self.assertEqual(self.dispatch(row).json()['status'],'blocked');send.assert_not_called()
        fresh=self.queue()[0];self.assertEqual(fresh['delivery']['recipient'],'changed@example.com')

    def test_currency_snapshot_is_retained_after_settings_change(self):
        self.consent()
        self.f.ok(0,'put','/api/settings',{'currency':'EUR'})
        row=self.queue()[0]
        self.assertIn('Total: USD 10.00',row['message']);self.assertNotIn('Total: EUR',row['message'])

    def test_sms_acceptance_is_not_delivery_and_provider_status_is_scoped(self):
        self.consent();row=self.queue()[1];sid='SM'+'1'*32
        with patch.object(server,'TWILIO_ACCOUNT_SID','synthetic-account'),patch.object(server,'TWILIO_AUTH_TOKEN','synthetic-token'):
            with patch.object(n,'provider_send',return_value={'status':'accepted','provider_message_id':sid}):
                self.assertEqual(self.dispatch(row).json()['status'],'accepted')
            path='/api/notifications/outbox/'+row['id']+'/delivery-status'
            with patch.object(n.httpx,'get',return_value=httpx.Response(200,json={'sid':sid,'status':'delivered'},request=httpx.Request('GET','https://api.twilio.com/fixture'))):
                self.assertEqual(self.f.ok(0,'post',path)['status'],'delivered')
            self.assertEqual(self.f.request(2,'post',path).status_code,404)

    def test_order_transaction_rolls_back_outbox_if_creation_fails(self):
        self.consent()
        before={r['id'] for r in self.f.ok(0,'get','/api/notifications/outbox')['notifications']}
        with patch.object(n,'enqueue',side_effect=RuntimeError('Synthetic queue persistence failure')):
            with self.assertRaises(RuntimeError):
                self.f.request(0,'post','/api/orders',{'customer_id':self.cid,'customer_name':self.order['customer']['name'],
                    'customer_phone':self.order['customer']['phone'],'items':[{'service_id':'shared-service','service_name':'Wash','quantity':1,'unit_price':10}]})
        outbox=self.f.ok(0,'get','/api/notifications/outbox')['notifications']
        self.assertEqual({r['id'] for r in outbox},before)

    def signed(self, event, private, public, signature_override=None):
        raw = json.dumps([event]).encode(); stamp = str(int(n.now().timestamp()))
        signature = base64.b64encode(private.sign(stamp.encode()+raw,ec.ECDSA(hashes.SHA256()))).decode()
        with patch.dict(os.environ, {'FABCLEAN_SENDGRID_WEBHOOK_PUBLIC_KEY': public}):
            return self.client.post('/api/notifications/webhooks/sendgrid',content=raw,headers={
                'X-Twilio-Email-Event-Webhook-Timestamp':stamp,'X-Twilio-Email-Event-Webhook-Signature':signature_override or signature})

    def test_signed_delivery_events_replay_optout_and_wrong_scope(self):
        self.consent(); row=self.queue()[0]
        with patch.object(n,'provider_send',return_value={'status':'accepted','provider_message_id':'fixture-id'}):self.dispatch(row)
        private=ec.generate_private_key(ec.SECP256R1()); public=base64.b64encode(private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
        event={'fabclean_notification_id':row['id'],'fabclean_brand_id':self.f.brand_a,'fabclean_store_id':self.f.stores[0],
               'sg_event_id':uuid.uuid4().hex,'sg_message_id':'fixture-id.provider','email':row['delivery']['recipient'],'event':'delivered'}
        self.assertEqual(self.signed(event,private,public,'invalid').status_code,401)
        self.assertEqual(self.signed({**event,'fabclean_store_id':self.f.stores[1]},private,public).status_code,200)
        self.assertEqual(self.signed(event,private,public).status_code,200)
        self.assertEqual(self.signed(event,private,public).status_code,200)
        events=self.f.ok(0,'get','/api/customers/'+self.cid+'/communication-events')['events']
        self.assertEqual(sum(e['event']=='delivered' for e in events),1)
        self.assertEqual(self.signed({**event,'sg_event_id':uuid.uuid4().hex,'event':'unsubscribe'},private,public).status_code,200)
        self.assertFalse(self.f.ok(0,'get','/api/customers/'+self.cid+'/communication-preferences')['email_opt_in'])
        marker=current_scope.set((self.f.brand_a,self.f.stores[0]))
        try:
            with self.assertRaises(RaiseException),server.db() as conn:conn.execute('DELETE FROM notification_events WHERE customer_id=%s',(self.cid,))
        finally:current_scope.reset(marker)

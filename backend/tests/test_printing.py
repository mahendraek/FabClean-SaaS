"""Printer validation, forced-RLS access and atomic/idempotent confirmations."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
import printing
import server
from tests import test_postgres_isolation as fixtures


class PrinterProfileTests(unittest.TestCase):
    def test_reject_invalid_and_command_bearing_settings(self):
        for value in ({'printer_mode': 'network'}, {'printer_dpi': True}, {'printer_dpi': 600}, {'label_width_mm': float('nan')}, {'label_height_mm': 0}, {'label_gap_mm': 20}, {'label_width_mm': '50;RESET'}, {'receipt_paper': '80mm;'}, {'scanner_uppercase': 'yes'}, {'scanner_prefix': '\rCUT'}, {'printer_host': '127.0.0.1'}, []):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                printing.validate_profile(value)
        self.assertEqual(printing.validate_profile(printing.DEFAULT_PROFILE), printing.DEFAULT_PROFILE)

    def test_partial_and_legacy_profiles_get_safe_defaults(self):
        self.assertEqual(printing.validate_profile({'receipt_paper': '58mm'}), {'receipt_paper': '58mm'})
        p = printing.effective_profile({'printer_dpi': 999, 'printer_mode': 'tspl', 'label_width_mm': -1, 'receipt_paper': 'a4', 'unexpected': '^RESET'})
        self.assertEqual(p['printer_dpi'], 203)
        self.assertEqual(p['label_width_mm'], 50)
        self.assertEqual(p['printer_mode'], 'tspl')
        self.assertNotIn('unexpected', p)


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'), 'Disposable PostgreSQL required')
class PrintingAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixtures.PostgresIsolationTests
        cls.f.setUpClass()
        cls.addClassCleanup(cls.f.doClassCleanups)

    def path(self, index=0, endpoint='print-preview'):
        return '/api/orders/' + self.f.orders[index]['id'] + '/' + endpoint

    def counts(self, index=0):
        return {g['garment_code']: g['tag_print_count'] for g in self.f.ok(index, 'get', '/api/orders/' + self.f.orders[index]['id'] + '/garments')['garments']}

    def test_preview_matches_ledger_settings_and_does_not_print(self):
        f = self.f
        before = self.counts()
        f.ok(0, 'put', '/api/settings', {'hardware_profile': {'receipt_paper': '58mm'}})
        result = f.ok(0, 'get', self.path())
        self.assertEqual(result['receipt']['paid_total'], 5)
        self.assertEqual(result['receipt']['balance_due'], 5)
        self.assertEqual(result['receipt']['order']['currency'], 'USD')
        self.assertEqual(result['profile']['receipt_paper'], '58mm')
        self.assertEqual(result['profile']['label_width_mm'], 50)
        self.assertEqual(result['business']['business_name'], 'Store 0')
        self.assertEqual(before, self.counts())
        self.assertNotEqual(f.ok(1, 'get', self.path(1))['profile']['receipt_paper'], '58mm')

    def test_confirmation_is_atomic_and_idempotent_even_concurrently(self):
        f = self.f
        before = self.counts()
        payload = {'request_id': str(uuid4()), 'document': 'garment_tags', 'garment_codes': list(before)}
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: f.request(0, 'post', self.path(endpoint='print-confirmations'), payload), range(3)))
        self.assertTrue(all(r.status_code == 200 for r in results), [r.text for r in results])
        self.assertEqual(sum(not r.json()['duplicate'] for r in results), 1)
        self.assertEqual(self.counts(), {k: v + 1 for k, v in before.items()})
        events = f.ok(0, 'get', '/api/orders/' + f.orders[0]['id'] + '/events')['events']
        events = [e for e in events if e['event_type'] == 'physical_print_confirmed' and e['metadata']['request_id'] == payload['request_id']]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['metadata']['confirmation'], 'staff_confirmed_physical_print')
        changed = {**payload, 'document': 'receipt', 'garment_codes': []}
        self.assertEqual(f.request(0, 'post', self.path(endpoint='print-confirmations'), changed).status_code, 409)

    def test_foreign_orders_and_garments_fail_without_counts_or_audit(self):
        f = self.f
        before = self.counts()
        for index in (1, 2):
            self.assertEqual(f.request(0, 'get', self.path(index)).status_code, 404)
            self.assertEqual(f.request(0, 'post', self.path(index, 'print-confirmations'), {'request_id': str(uuid4()), 'document': 'receipt'}).status_code, 404)
        payload = {'request_id': str(uuid4()), 'document': 'garment_tags', 'garment_codes': list(before) + ['foreign-code']}
        self.assertEqual(f.request(0, 'post', self.path(endpoint='print-confirmations'), payload).status_code, 404)
        self.assertEqual(before, self.counts())
        self.assertEqual(f.client.get(self.path()).status_code, 401)

    def test_receipt_confirmation_never_increments_garment_counts(self):
        before = self.counts()
        for document in ('receipt', 'order_tag'):
            result = self.f.request(0, 'post', self.path(endpoint='print-confirmations'), {'request_id': str(uuid4()), 'document': document})
            self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(before, self.counts())

    def test_invalid_requests_and_rollback_preserve_counts(self):
        f = self.f
        before = self.counts()
        for extra in ({'document': 'arbitrary'}, {'document': 'receipt', 'garment_codes': list(before)}, {'document': 'garment_tags', 'garment_codes': []}, {'document': 'garment_tags', 'garment_codes': [1]}, {'document': 'receipt', 'copies': 100}):
            self.assertEqual(f.request(0, 'post', self.path(endpoint='print-confirmations'), {'request_id': str(uuid4()), **extra}).status_code, 400)
        with patch.object(server, 'record_order_event', side_effect=RuntimeError('controlled audit failure')):
            with self.assertRaises(RuntimeError):
                f.request(0, 'post', self.path(endpoint='print-confirmations'), {'request_id': str(uuid4()), 'document': 'garment_tags', 'garment_codes': list(before)})
        self.assertEqual(before, self.counts())
        self.assertEqual(f.request(0, 'put', '/api/settings', {'hardware_profile': {'printer_mode': 'unsafe'}}).status_code, 400)

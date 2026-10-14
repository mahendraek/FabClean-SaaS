import os,unittest
from unittest.mock import patch
import httpx
import locations,taxes,server
from tests import test_postgres_isolation as fixtures

class LocationTests(unittest.TestCase):
    def test_country_state_normalization_and_cross_country_rejection(self):
        d={'country':'United States','state':'Illinois'};locations.validate_location(d);self.assertEqual(d,{'country':'US','state':'IL'})
        self.assertEqual(locations.state('US-IL','US'),'IL')
        with self.assertRaises(server.HTTPException):locations.validate_location({'country':'US','state':'Maharashtra'})
    def test_postal_country_state_and_provider_errors(self):
        locations.postal_lookup.cache_clear()
        response=httpx.Response(200,json={'country abbreviation':'US','places':[{'state abbreviation':'IL','place name':'Schaumburg'}]},request=httpx.Request('GET','https://api.zippopotam.us/us/60193'))
        with patch.object(locations.httpx,'get',return_value=response):self.assertEqual(locations.postal_lookup('US','60193')['state'],'IL')
        locations.postal_lookup.cache_clear()
        with patch.object(locations.httpx,'get',side_effect=httpx.ConnectError('offline')):
            with self.assertRaises(server.HTTPException) as e:locations.postal_lookup('US','60193')
            self.assertEqual(e.exception.status_code,503)
    def test_location_tax_rules_match_legacy_full_names(self):
        r={'id':'r','component':'state','jurisdiction':'Configured rate','country':'US','state':'IL','rate':'5','effective_from':'2020-01-01','effective_to':None}
        self.assertEqual(taxes.selected([r],{'country':'United States','state':'Illinois','city':'Schaumburg'},'2026-10-13')[0]['rule_id'],'r')

@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable database required')
class AdminLocationAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
    def test_options_authentication_and_lookup_invalid_input(self):
        self.assertEqual(self.f.client.get('/api/locations/options').status_code,401)
        d=self.f.ok(0,'get','/api/locations/options');self.assertEqual(len(d['countries']),249);self.assertTrue(any(s['code']=='IL' for s in d['subdivisions']['US']))
        self.assertEqual(self.f.request(0,'get','/api/locations/postal?country_code=US&postal_code=../secret').status_code,400)
    def test_theme_validation_and_scope(self):
        self.f.ok(0,'put','/api/settings',{'brand_theme':'plum'});self.assertEqual(self.f.ok(0,'get','/api/settings')['brand_theme'],'plum');self.assertNotEqual(self.f.ok(1,'get','/api/settings').get('brand_theme'),'plum')
        self.assertEqual(self.f.request(0,'put','/api/settings',{'brand_theme':'invalid'}).status_code,400)
    def test_diagnostics_and_idempotent_targeted_sample_data(self):
        self.assertEqual(self.f.request(0,'post','/api/admin/cleananddry-samples').status_code,409)
        with server.db(maintenance=True) as conn:conn.execute("UPDATE stores SET name='CleanandDry',city='Schaumburg',country='US',state='Illinois' WHERE id=%s",(self.f.stores[0],))
        first=self.f.ok(0,'post','/api/admin/cleananddry-samples');second=self.f.ok(0,'post','/api/admin/cleananddry-samples');self.assertEqual(len(first['created_services']),3);self.assertEqual(second['created_services'],[])
        self.assertEqual(self.f.request(1,'post','/api/admin/cleananddry-samples').status_code,409)
        d=self.f.ok(0,'get','/api/taxes/rules');self.assertEqual(d['location']['state'],'IL');self.assertIn('diagnostics',d)
        service=self.f.ok(0,'get','/api/admin/services')['services'][0]
        self.f.ok(0,'put','/api/services/'+service['id'],{**service,'taxable':True})
        self.f.ok(0,'post','/api/taxes/rules',{'component':'state','jurisdiction':'TEST Illinois rate','country':'US','state':'IL','rate':'5','effective_from':'2020-01-01'})
        quote=self.f.ok(0,'post','/api/taxes/estimate',{'items':[{'service_id':service['id'],'quantity':1,'unit_price':10}]})
        self.assertEqual(quote['tax'],.5)
        self.assertEqual(self.f.ok(0,'get','/api/taxes/rules')['diagnostics']['status'],'location_rules_active')

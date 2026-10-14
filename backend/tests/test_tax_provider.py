import os
import unittest
from unittest.mock import patch
import httpx
import server,tax_provider,taxes
from tests import test_postgres_isolation as fixtures
from tenant_scope import current_scope


def response(**changes):
    return {'rCode':100,'results':[{'geoPostalCode':'60601','geoState':'IL','geoCity':'Chicago','geoCounty':'Cook','taxSales':.0625,**changes}]}


class TaxProviderParsingTests(unittest.TestCase):
    def test_exact_location_and_ambiguity_fail_closed(self):
        loc={'state':'IL','city':'Chicago','postal_code':'60601'}
        self.assertEqual(tax_provider.parse_response(response(),loc)['rate'],'6.25')
        for data in (response(geoState='CA'),response(taxSales=-1),response(taxSales=True),response(taxSales='nan'),{'rCode':100,'results':response()['results']*2}):
            with self.assertRaises(server.HTTPException):tax_provider.parse_response(data,loc)


@unittest.skipUnless(os.getenv('FABCLEAN_TEST_DATABASE_URL'),'Disposable PostgreSQL required')
class TaxProviderAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=fixtures.PostgresIsolationTests;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)

    def setUp(self):
        with server.db(maintenance=True) as c:
            c.execute("UPDATE stores SET country='US',state='IL',city='Chicago',postal_code='60601',timezone='America/Chicago' WHERE id=%s",(self.f.stores[0],))
            c.execute('DELETE FROM tax_rules WHERE business_id=%s',(self.f.brand_a,))
            c.execute('DELETE FROM tax_provider_quotes WHERE business_id=%s',(self.f.brand_a,))
        self.key=patch.dict(os.environ,{'FABCLEAN_TAX_PROVIDER_KEY':'synthetic-provider-key'});self.key.start();self.addCleanup(self.key.stop)

    def lookup(self):
        with patch.object(tax_provider.httpx,'get',return_value=httpx.Response(200,json=response(),request=httpx.Request('GET','https://api.zip-tax.com/request/v20'))) as get:
            result=self.f.ok(0,'post','/api/taxes/provider/lookup')
        self.assertEqual(get.call_count,1)
        return result

    def test_lookup_cache_review_import_order_snapshot_and_foreign_denial(self):
        quote=self.lookup()
        with patch.object(tax_provider.httpx,'get') as get:
            self.assertEqual(self.f.ok(0,'post','/api/taxes/provider/lookup')['id'],quote['id']);get.assert_not_called()
        path='/api/taxes/provider/'+quote['id']+'/import';body={'jurisdiction_verified':True,'service_taxability_verified':True}
        self.assertEqual(self.f.request(2,'post',path,body).status_code,404)
        self.assertEqual(self.f.request(0,'post',path,{}).status_code,400)
        rule=self.f.ok(0,'post',path,body)
        self.assertEqual(rule['provenance']['quote_id'],quote['id'])
        self.assertEqual(self.f.request(0,'post',path,body).status_code,409)
        service=self.f.ok(0,'get','/api/admin/services')['services'][0]
        self.f.ok(0,'put','/api/services/shared-service',{**service,'taxable':True,'tax_rate':99})
        order=self.f.ok(0,'post','/api/orders',{'customer_name':'Provider fixture','customer_phone':'provider-'+quote['id'],
            'items':[{'service_id':'shared-service','service_name':'Wash','quantity':1,'unit_price':10}]})
        self.assertEqual(order['tax'],.63)
        self.assertEqual(order['tax_snapshot']['components'][0]['provenance']['quote_id'],quote['id'])
        receipt=self.f.ok(0,'get','/api/orders/'+order['id']+'/receipt')
        self.assertEqual(receipt['order']['total'],10.63)

    def test_location_change_and_provider_failure_do_not_change_rules(self):
        quote=self.lookup()
        with server.db(maintenance=True) as c:c.execute("UPDATE stores SET postal_code='60602' WHERE id=%s",(self.f.stores[0],))
        self.assertEqual(self.f.request(0,'post','/api/taxes/provider/'+quote['id']+'/import',{'jurisdiction_verified':True,'service_taxability_verified':True}).status_code,409)
        with patch.object(tax_provider.httpx,'get',side_effect=httpx.ReadTimeout('secret-key-do-not-log')):
            result=self.f.request(0,'post','/api/taxes/provider/lookup')
        self.assertEqual(result.status_code,503);self.assertNotIn('secret-key-do-not-log',result.text)
        self.assertEqual(self.f.ok(0,'get','/api/taxes/rules')['rules'],[])

    def test_missing_key_and_double_tax_import_are_rejected(self):
        with patch.dict(os.environ,{'FABCLEAN_TAX_PROVIDER_KEY':''}):self.assertEqual(self.f.request(0,'post','/api/taxes/provider/lookup').status_code,503)
        quote=self.lookup()
        self.f.ok(0,'post','/api/taxes/rules',{'component':'state','jurisdiction':'Fixture state','country':'US','state':'IL','rate':'5','effective_from':'2020-01-01'})
        self.assertEqual(self.f.request(0,'post','/api/taxes/provider/'+quote['id']+'/import',{'jurisdiction_verified':True,'service_taxability_verified':True}).status_code,409)
        server.init_db();server.init_db()
        marker=current_scope.set((self.f.brand_b,self.f.stores[2]))
        try:
            with server.db() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM tax_provider_quotes').fetchone()['n'],0)
                flags=c.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='tax_provider_quotes'::regclass").fetchone();self.assertTrue(all(flags.values()))
        finally:current_scope.reset(marker)

"""Disposable local PR #11 fixtures; no external messages or provider lookups."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import server
from tests.test_postgres_isolation import PostgresIsolationTests

url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('localhost','127.0.0.1','::1') or 'test' not in url.path:
    raise SystemExit('Disposable local database required')
f=PostgresIsolationTests;f.setUpClass()
try:
    with server.db() as c:c.execute("UPDATE stores SET country='US',state='IL',city='Chicago',postal_code='60601',timezone='America/Chicago' WHERE id=%s",(f.stores[0],))
    f.ok(0,'post','/api/taxes/rules',{'component':'state','jurisdiction':'Fixture Illinois','country':'US','state':'IL','rate':'5','effective_from':'2020-01-01'})
    f.ok(0,'post','/api/services',{'id':'receipt-service','category':'Test','name':'Receipt fixture wash','pricing_type':'per_item','base_price':10,'taxable':True})
    order=f.ok(0,'post','/api/orders',{'customer_name':'Receipt Browser Customer','customer_phone':'+15550102030','customer_email':'receipt-browser@example.com',
        'items':[{'service_id':'receipt-service','service_name':'Receipt fixture wash','quantity':1,'unit_price':10}]})
    f.ok(0,'put','/api/settings',{'notifications_enabled':True,'business_name':'Receipt Fixture Laundry'})
    path=Path(sys.argv[1]);path.write_text(json.dumps({'token':f.tokens[0],'user':f.users[0],'foreign_token':f.tokens[2],
        'brand':f.brand_a,'store':f.stores[0],'order':order['id'],'customer':order['customer']['id']}));path.chmod(0o600)
    print('Private notification fixtures prepared')
finally:f.doClassCleanups()

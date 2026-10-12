"""Disposable local tax browser fixtures; never production."""
import json,os,sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_postgres_isolation import PostgresIsolationTests
import server
url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('localhost','127.0.0.1','::1') or not any(v in url.path.lower() for v in ('test','integration')):raise SystemExit('Disposable local database required')
f=PostgresIsolationTests;f.setUpClass()
try:
    with server.db() as conn:
        conn.execute("UPDATE brands SET name='Tax Test Brand' WHERE id=%s",(f.brand_a,));conn.execute("UPDATE stores SET name='Chicago Tax Store',country='US',state='IL',city='Chicago',postal_code='60601',timezone='America/Chicago' WHERE id=%s",(f.stores[0],))
    f.ok(0,'post','/api/services',{'id':'tax-service','name':'Tax demo wash','category':'Test','pricing_type':'per_item','base_price':10,'taxable':True})
    out=Path(sys.argv[1]);out.write_text(json.dumps({'user':f.users[0],'token':f.tokens[0],'foreign_token':f.tokens[2]}));out.chmod(0o600);print('Private tax fixtures prepared')
finally:f.doClassCleanups()

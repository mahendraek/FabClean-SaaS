import os,json,sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_postgres_isolation import PostgresIsolationTests
import server
u=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if u.hostname not in ('127.0.0.1','localhost') or 'test' not in u.path:raise SystemExit('Disposable local database required')
f=PostgresIsolationTests;f.setUpClass()
try:
    with server.db() as c:c.execute("UPDATE stores SET name='CleanandDry',city='Schaumburg',state='Illinois',country='US',postal_code='60193' WHERE id=%s",(f.stores[0],))
    p=Path(sys.argv[1]);p.write_text(json.dumps({'token':f.tokens['super'],'user':f.prefix+'-super','store':f.stores[0]}));p.chmod(0o600)
finally:f.doClassCleanups()

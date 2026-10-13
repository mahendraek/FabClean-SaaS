"""Private fixtures for local coverage browser validation; never production."""
import json,os,sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_postgres_isolation import PostgresIsolationTests
import server
from datetime import datetime,timezone

url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('localhost','127.0.0.1','::1') or not any(x in url.path.lower() for x in ('test','integration')):raise SystemExit('Disposable local database required')
f=PostgresIsolationTests;f.setUpClass()
try:
    with server.db() as conn:
        conn.execute("UPDATE brands SET name='Coverage Test Brand' WHERE id=%s",(f.brand_a,))
        conn.execute("UPDATE stores SET name='Coverage Test Store',latitude=41.5,longitude=-87.5 WHERE id=%s",(f.stores[0],))
    with server.db(maintenance=True) as conn:conn.execute('UPDATE delivery_slots SET day_of_week=%s WHERE id=%s AND business_id=%s AND location_id=%s',((datetime.now(timezone.utc).weekday()+1)%7,f.slots[0],f.brand_a,f.stores[0]))
    f.ok(0,'put','/api/settings',{'pickup_enabled':True,'delivery_enabled':True})
    out=Path(sys.argv[1]);out.write_text(json.dumps({'user':f.users[0],'token':f.tokens[0],'foreign_token':f.tokens[2],'other_token':f.tokens[1],'slot':f.slots[0],'store':f.stores[0]}));out.chmod(0o600)
    print('Private coverage fixtures prepared')
finally:f.doClassCleanups()

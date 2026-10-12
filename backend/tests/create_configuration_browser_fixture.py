"""Private configuration browser fixtures; disposable local database only."""
import json,os,sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_postgres_isolation import PostgresIsolationTests
import server
url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('localhost','127.0.0.1','::1') or not any(x in url.path.lower() for x in ('test','integration')):raise SystemExit('Disposable local database required')
f=PostgresIsolationTests;f.setUpClass()
try:
    with server.db() as conn:
        conn.execute("UPDATE brands SET name='Configuration Test Brand' WHERE id=%s",(f.brand_a,))
        for index,store in enumerate(f.stores):conn.execute('UPDATE stores SET name=%s WHERE id=%s',('Configuration Store '+str(index),store))
    output=Path(sys.argv[1]);output.write_text(json.dumps({'super_user':f.prefix+'-super','super_token':f.tokens['super'],'manager_user':f.users[0],'manager_token':f.tokens[0],'other_store_token':f.tokens[1],'foreign_token':f.tokens[2],'brand':f.brand_a,'stores':f.stores}));output.chmod(0o600)
    print('Private configuration fixtures prepared')
finally:f.doClassCleanups()

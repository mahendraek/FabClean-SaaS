"""Synthetic tax policies in a disposable local database; no real jurisdiction rates."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from tests.test_taxation import StoreTaxAPITests

url=urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL',''))
if url.hostname not in ('127.0.0.1','localhost','::1') or 'test' not in url.path:
    raise SystemExit('Disposable local database required')
StoreTaxAPITests.setUpClass();test=StoreTaxAPITests();f=test.f
try:
    test.publish(enabled=False)
    path=Path(sys.argv[1]);path.write_text(json.dumps({'token':f.tokens[0],'foreign_token':f.tokens[2],'user':f.users[0],'brand':f.brand_a,'store':f.stores[0]}));path.chmod(0o600)
    print('Synthetic tax browser fixtures prepared; not legal rate data')
finally:
    StoreTaxAPITests.doClassCleanups()

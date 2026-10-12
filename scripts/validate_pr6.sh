#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
python_bin=${PYTHON_BIN:-python}
: "${FABCLEAN_TEST_DATABASE_URL:?Set an explicitly disposable local PostgreSQL test database}"
export XDG_CACHE_HOME=${XDG_CACHE_HOME:-/tmp/fabclean-cache}
export __UNSAFE_EXPO_HOME_DIRECTORY=${__UNSAFE_EXPO_HOME_DIRECTORY:-/tmp/fabclean-expo}
export EXPO_NO_TELEMETRY=1 EXPO_NO_TYPESCRIPT_SETUP=1
# Refuse production before any migration or fixture code runs.
"$python_bin" - <<'PY'
import os
from urllib.parse import urlparse
url=urlparse(os.environ['FABCLEAN_TEST_DATABASE_URL'])
if url.hostname not in ('127.0.0.1','localhost','::1') or not any(x in url.path.lower() for x in ('test','integration')):
    raise SystemExit('Validation requires a disposable local test/integration database')
PY
cd "$repo_root/backend"
"$python_bin" -m unittest discover -s tests -v
"$python_bin" tools/performance_baseline.py --output /tmp/pr6-validation-load.json
"$python_bin" - <<'PY'
import json
r=json.load(open('/tmp/pr6-validation-load.json'))
assert r['errors']==0 and r['requests_per_second']>=10,r
assert all(p['p95_ms']<=1000 for p in r['paths'].values()),r
PY
fixture_path=$(mktemp /tmp/fabclean-browser-XXXXXX.json)
platform_fixture_path=$(mktemp /tmp/fabclean-platform-XXXXXX.json)
configuration_fixture_path=$(mktemp /tmp/fabclean-configuration-XXXXXX.json)
tax_fixture_path=$(mktemp /tmp/fabclean-tax-XXXXXX.json)
"$python_bin" - <<'PY'
import socket
with socket.socket() as listener:
    try: listener.bind(('127.0.0.1', 8005))
    except OSError: raise SystemExit('Port 8005 is occupied; stop your local validation API before running this gate')
PY
FABCLEAN_TEST_DATABASE_URL="$FABCLEAN_TEST_DATABASE_URL" "$python_bin" -m tests.create_handoff_browser_fixture "$fixture_path"
FABCLEAN_TEST_DATABASE_URL="$FABCLEAN_TEST_DATABASE_URL" "$python_bin" -m tests.create_platform_browser_fixture "$platform_fixture_path"
FABCLEAN_TEST_DATABASE_URL="$FABCLEAN_TEST_DATABASE_URL" "$python_bin" -m tests.create_configuration_browser_fixture "$configuration_fixture_path"
FABCLEAN_TEST_DATABASE_URL="$FABCLEAN_TEST_DATABASE_URL" "$python_bin" -m tests.create_tax_browser_fixture "$tax_fixture_path"
DATABASE_URL="$FABCLEAN_TEST_DATABASE_URL" "$python_bin" -m uvicorn server:app --host 127.0.0.1 --port 8005 --no-access-log > /tmp/pr6-validation-api.log 2>&1 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true; rm -f "$fixture_path" "$platform_fixture_path" "$configuration_fixture_path" "$tax_fixture_path"' EXIT
"$python_bin" - <<'PY'
import time,urllib.request
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8005/api/health',timeout=2) as response:
            if response.status==200:break
    except OSError:time.sleep(1)
else:raise SystemExit('Local API failed to start')
PY
kill -0 "$api_pid"
cd "$repo_root/frontend"
npm run test:unit
npx expo export -p web
node - <<'JS'
const path=require('path');const fs=require('fs');const root=process.cwd();
fs.mkdirSync(path.join(root,'.expo/types'),{recursive:true});
process.env.EXPO_ROUTER_APP_ROOT=path.join(root,'app');
const cli=require.resolve('expo/node_modules/@expo/cli/package.json');
const routes=require(require.resolve('@expo/router-server/build/typed-routes',{paths:[path.dirname(cli)]}));
routes.regenerateDeclarations(path.join(root,'.expo/types'));
JS
npx tsc --noEmit
kill -0 "$api_pid"
npm run test:context:browser
HANDOFF_TEST_FIXTURES="$fixture_path" npm run test:handoffs:browser

PLATFORM_TEST_FIXTURES="$platform_fixture_path" npm run test:platform:browser

CONFIGURATION_TEST_FIXTURES="$configuration_fixture_path" npm run test:configuration:browser

TAX_TEST_FIXTURES="$tax_fixture_path" npm run test:taxes:browser

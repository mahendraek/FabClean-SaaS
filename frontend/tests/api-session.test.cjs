const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const ts = require('typescript');
const source = ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../src/api.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
async function setup(platform = 'web', stored = {}) {
  const values = new Map(Object.entries(stored)), exports = {}, calls = [];
  const sandbox = { exports, process: { env: {} }, fetch: async (...args) => { calls.push(args); return { ok: true, status: 200, text: async () => '{}' }; },
    window: { localStorage: { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) } },
    require: name => name === 'react-native' ? { Platform: { OS: platform } } : { getItemAsync: async key => values.get(key) || null, setItemAsync: async (key, value) => values.set(key, value), deleteItemAsync: async key => values.delete(key) }
  };
  if (platform !== 'web') delete sandbox.window;
  vm.runInNewContext(source, sandbox);
  await exports.sessionReady;
  return { api: exports, values, sandbox, calls };
}
for (const platform of ['web', 'ios', 'android']) test(`${platform}: sessions survive reload and sign-out clears credentials`, async () => {
  const first = await setup(platform); await first.api.setStoredSession({ id: 'u1' }, 'test-token');
  const second = await setup(platform, Object.fromEntries(first.values));
  assert.equal(second.api.getStoredStaff().id, 'u1'); await second.api.api.get('/settings');
  assert.equal(second.calls[0][1].headers['X-Session-Token'], 'test-token');
  await second.api.setStoredSession(null, ''); assert.equal(second.values.size, 0);
});
test('late responses from the previous context are rejected', async () => {
  const { api, sandbox } = await setup(); let complete;
  sandbox.fetch = () => new Promise(resolve => { complete = resolve; });
  const request = api.api.get('/orders'); await Promise.resolve(); api.invalidateRequests();
  complete({ ok: true, text: async () => '{"orders":["old-store"]}' });
  await assert.rejects(request, /Active context changed/);
});
test('anonymous 401 does not cause a session notification/reload loop', async () => {
  const { api, sandbox } = await setup(); let events = 0; api.subscribeSession(() => events++);
  sandbox.fetch = async () => ({ ok: false, status: 401, text: async () => '{"detail":"Sign in"}' });
  await assert.rejects(api.api.get('/orders'), /Sign in/); assert.equal(events, 0);
});
test('a 401 from an old session cannot clear the new session', async () => {
  const { api, sandbox } = await setup(); await api.setStoredSession({ id: 'old' }, 'old'); let complete;
  sandbox.fetch = () => new Promise(resolve => { complete = resolve; });
  const request = api.api.get('/orders'); await Promise.resolve(); await api.setStoredSession({ id: 'new' }, 'new');
  complete({ ok: false, status: 401, text: async () => '{}' });
  await assert.rejects(request, /Active context changed/); assert.equal(api.getStoredToken(), 'new');
});
const selectionSource = ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../src/ActiveContext.tsx'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.React } }).outputText;
for (const [label, saved, allowed, expected] of [
  ['authorized selection', '{"brand_id":"b1","store_id":"s2"}', true, 1],
  ['revoked selection', '{"brand_id":"b1","store_id":"s2"}', false, 0],
  ['corrupt selection', 'null', true, 0]
]) test(`relogin restores only ${label}`, async () => {
  const exports = {}, updates = [];
  const apiModule = { api: {
    get: async () => ({ staff: { id: 'u1' }, active_brand: { id: 'b1' }, active_store: { id: 's1' }, brands: [{ id: 'b1' }], stores: allowed ? [{ id: 's2', brand_id: 'b1' }] : [] }),
    put: async (...args) => { updates.push(args); }
  }, readPreference: async key => { assert.equal(key, 'fabclean_context_u1'); return saved; }, writePreference: async () => {} };
  vm.runInNewContext(selectionSource, { exports, require: name => name === './api' ? apiModule : name === 'react-native' ? { StyleSheet: { create: x => x } } : name === './theme' ? { colors: {}, themedStyles: x => x } : {} });
  await exports.restoreSelection(); assert.equal(updates.length, expected);
});
test('sign-out revokes the server session before clearing persisted credentials', async () => {
  const { api, calls, values } = await setup();
  await api.setStoredSession({ id: 'u1' }, 'token');
  await api.signOut();
  assert.equal(calls[0][0], 'http://localhost:8000/api/auth/sign-out');
  assert.equal(calls[0][1].headers['X-Session-Token'], 'token');
  assert.equal(values.size, 0);
});
test('failed revocation keeps the session available for retry', async () => {
  const { api, sandbox } = await setup();
  await api.setStoredSession({ id: 'u1' }, 'token');
  sandbox.fetch = async () => { throw new Error('Offline'); };
  await assert.rejects(api.signOut(), /Offline/);
  assert.equal(api.getStoredToken(), 'token');
});
test('operational requests pin the displayed context and clear it on session change', async () => {
  const { api, sandbox, calls } = await setup();
  await api.setStoredSession({ id: 'u1' }, 'token');
  sandbox.fetch = async (...args) => { calls.push(args); return { ok: true, text: async () => '{"active_brand":{"id":"b"},"active_store":{"id":"s"}}' }; };
  await api.api.get('/context'); await api.api.post('/orders', {});
  assert.equal(calls[1][1].headers['X-Active-Store-ID'], 's');
  assert.equal(calls[1][1].headers['X-Active-Brand-ID'], 'b');
  await api.setStoredSession({ id: 'u2' }, 'new'); await api.api.get('/orders');
  assert.equal(calls[2][1].headers['X-Active-Store-ID'], undefined);
});
test('HTML gateway errors retain HTTP status and clear retry guidance', async () => {
 const { api, sandbox } = await setup();
 sandbox.fetch = async () => ({ ok: false, status: 503, text: async () => '<html>Unavailable</html>' });
 await assert.rejects(api.api.get('/orders'), e => e.status === 503 && /HTTP 503/.test(e.message));
});
test('non-JSON unauthorized responses clear expired credentials', async () => {
 const { api, sandbox } = await setup(); await api.setStoredSession({ id: 'u1' }, 'expired');
 sandbox.fetch = async () => ({ ok: false, status: 401, text: async () => '<html>Unauthorized</html>' });
 await assert.rejects(api.api.get('/orders'), e => e.status === 401); assert.equal(api.getStoredToken(), '');
});
test('rate limits expose retry guidance without clearing the session', async () => {
 const { api, sandbox } = await setup(); await api.setStoredSession({ id: 'u1' }, 'token');
 sandbox.fetch = async () => ({ ok: false, status: 429, headers: { get: () => '120' }, text: async () => '{"detail":"Too many attempts"}' });
 await assert.rejects(api.api.post('/auth/sign-in', {}), e => e.status === 429 && e.retryAfter === '120'); assert.equal(api.getStoredToken(), 'token');
});
test('permission removed during selection restoration discards the preference', async () => {
 const exports = {}; let removed = false;
 const module = { api: {
  get: async () => ({ staff: { id: 'u1' }, active_brand: { id: 'b1' }, active_store: { id: 's1' }, brands: [{ id: 'b1' }], stores: [{ id: 's2', brand_id: 'b1' }] }),
  put: async () => { const e = new Error('Revoked'); e.status = 403; throw e; }
 }, readPreference: async () => '{"brand_id":"b1","store_id":"s2"}', writePreference: async (key, value) => { assert.equal(key, 'fabclean_context_u1'); assert.equal(value, null); removed = true; } };
 vm.runInNewContext(selectionSource, { exports, require: name => name === './api' ? module : name === 'react-native' ? { StyleSheet: { create: x => x } } : name === './theme' ? { colors: {}, themedStyles: x => x } : {} });
 await exports.restoreSelection(); assert.equal(removed, true);
});
test('failed invitation identity proof preserves an unrelated valid session', async () => {
 const { api, sandbox } = await setup(); await api.setStoredSession({ id: 'current' }, 'valid-current-token');
 sandbox.fetch = async () => ({ ok: false, status: 401, text: async () => '{"detail":"Use the invited account password"}' });
 await assert.rejects(api.api.post('/auth/owner-invitations/accept', {}), e => e.status === 401);
 assert.equal(api.getStoredToken(), 'valid-current-token');
});
for (const platform of ['web', 'ios', 'android']) test(`${platform}: CSV requests retain authentication, scope and HTTP errors`, async () => {
  const { api, sandbox, calls } = await setup(platform);
  await api.setStoredSession({id:'report-user'}, 'report-token');
  sandbox.fetch=async()=>({ok:true,status:200,text:async()=>JSON.stringify({active_brand:{id:'brand-a'},active_store:{id:'store-a'}})});
  await api.api.get('/context');
  sandbox.fetch=async (...args)=>{calls.push(args);return {ok:true,status:200,text:async()=>'Brand,Order\r\nA,10\r\n'};};
  assert.equal(await api.api.getText('/reports/export'), 'Brand,Order\r\nA,10\r\n');
  assert.equal(calls[0][1].headers['X-Session-Token'],'report-token');
  assert.equal(calls[0][1].headers['X-Active-Brand-ID'],'brand-a');
  assert.equal(calls[0][1].headers['X-Active-Store-ID'],'store-a');
  sandbox.fetch=async()=>({ok:false,status:403,text:async()=>' {"detail":"Brand reporting denied"} '});
  await assert.rejects(api.api.getText('/reports/export'), /Brand reporting denied/);
  let complete;
  sandbox.fetch=()=>new Promise(resolve=>{complete=resolve;});
  const pending=api.api.getText('/reports/export');await Promise.resolve();api.invalidateRequests();
  complete({ok:true,status:200,text:async()=>'old brand data'});
  await assert.rejects(pending,/Active context changed/);
});

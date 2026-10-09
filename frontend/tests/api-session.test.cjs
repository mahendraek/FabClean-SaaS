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
  vm.runInNewContext(selectionSource, { exports, require: name => name === './api' ? apiModule : name === 'react-native' ? { StyleSheet: { create: x => x } } : name === './theme' ? { colors: {} } : {} });
  await exports.restoreSelection(); assert.equal(updates.length, expected);
});

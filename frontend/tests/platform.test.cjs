const { test } = require('node:test');
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs'), path = require('node:path'), ts = require('typescript');
const exportsModule = {};
const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/platform.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(source, { exports: exportsModule });
test('resource limits accept unlimited and positive whole numbers', () => {
 assert.equal(exportsModule.parseLimit(''), null); assert.equal(exportsModule.parseLimit(' 10 '), 10);
 for (const bad of ['0', '-1', '1.5', '1x', '10001']) assert.throws(() => exportsModule.parseLimit(bad));
});
test('brand feature overrides preserve unspecified plan flags', () => {
 const result = exportsModule.selectedFeatures({ features: { offers: false, ai: true, handoffs: true } }, { features: { offers: true, ai: false } });
 assert.equal(result.offers, true); assert.equal(result.ai, false); assert.equal(result.handoffs, true);
});
test('invitation cleanup removes parent and child credentials without changing route keys', () => {
 const state = { key: 'root', routes: [{ key: 'layout', params: { '#': 'token=fixture', other: 'keep' }, state: { key: 'stack', routes: [{ key: 'invite', name: 'accept-invite', path: '/accept-invite#token=fixture', params: { token: 'fixture', id: 'keep' } }] } }] };
 const clean = exportsModule.cleanInviteNavigation(state);
 assert.equal(clean.key, 'root'); assert.equal(clean.routes[0].params.other, 'keep');
 assert.equal(clean.routes[0].state.routes[0].key, 'invite'); assert.equal(clean.routes[0].state.routes[0].path, '/accept-invite');
 assert.equal(JSON.stringify(clean).includes('fixture'), false); assert.equal(JSON.stringify(state).includes('fixture'), true);
});

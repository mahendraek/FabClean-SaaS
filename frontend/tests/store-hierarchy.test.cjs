const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), ts = require('typescript');
const exportsModule = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../src/store-hierarchy.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, { exports: exportsModule });
const stores = [{ id: 'hub', name: 'Hub', active: true }, { id: 'plant', name: 'Plant', active: true, parent_store_id: 'hub' }, { id: 'drop', name: 'Dropoff', active: true, parent_store_id: 'plant' }];
test('parent choices exclude the store and all descendants', () => {
  assert.deepEqual([...exportsModule.storeDescendants(stores, 'hub')].sort(), ['drop', 'hub', 'plant']);
  assert.deepEqual([...exportsModule.storeDescendants(stores, 'plant')].sort(), ['drop', 'plant']);
});
test('hierarchy paths show all ancestor names', () => {
  assert.equal(exportsModule.storePath(stores, 'drop'), 'Hub › Plant › Dropoff');
});
test('historical cyclic hierarchies terminate without hanging', () => {
  const cyclic = [{ id: 'a', name: 'A', active: true, parent_store_id: 'b' }, { id: 'b', name: 'B', active: true, parent_store_id: 'a' }];
  assert.match(exportsModule.storePath(cyclic, 'a'), /^Invalid hierarchy/);
  assert.equal(exportsModule.storeDescendants(cyclic, 'a').size, 2);
});

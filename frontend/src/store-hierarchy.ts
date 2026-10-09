export type HierarchyStore = { id: string; name: string; parent_store_id?: string | null; active: boolean };
export function storeDescendants(stores: HierarchyStore[], id: string) {
  const found = new Set([id]);
  let size = 0;
  while (size !== found.size) {
    size = found.size;
    stores.forEach(store => { if (store.parent_store_id && found.has(store.parent_store_id)) found.add(store.id); });
  }
  return found;
}
export function storePath(stores: HierarchyStore[], id: string): string {
  const names: string[] = [], visited = new Set<string>();
  let store = stores.find(value => value.id === id);
  while (store) {
    if (visited.has(store.id)) return `Invalid hierarchy · ${names.reverse().join(" › ")}`;
    visited.add(store.id); names.push(store.name);
    store = stores.find(value => value.id === store?.parent_store_id);
  }
  return names.reverse().join(" › ");
}

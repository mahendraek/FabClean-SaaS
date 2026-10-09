import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, AppState, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { api, getStoredStaff, getStoredToken, invalidateRequests, readPreference, refreshSession, sessionReady, subscribeSession, writePreference } from "./api";
import { colors } from "./theme";
type Brand = { id: string; name: string };
type Store = { id: string; brand_id: string; name: string; store_code: string };
type Context = { staff: { id: string }; brands: Brand[]; stores: Store[]; active_brand: Brand | null; active_store: Store | null };
const preferenceKey = (id: string) => `fabclean_context_${id}`;
export async function restoreSelection() {
  const context = await api.get<Context>("/context");
  const saved = await readPreference(preferenceKey(context.staff.id));
  if (!saved) return;
  let selected: { brand_id: string; store_id: string };
  try { selected = JSON.parse(saved); } catch { return; }
  if (!selected || typeof selected.brand_id !== "string" || typeof selected.store_id !== "string") return;
  if (!context.brands.some(b => b.id === selected.brand_id) || !context.stores.some(s => s.id === selected.store_id && s.brand_id === selected.brand_id)) {
    await writePreference(preferenceKey(context.staff.id), null); return;
  }
  if (context.active_brand?.id !== selected.brand_id || context.active_store?.id !== selected.store_id) await api.put("/context", selected);
}
export function ActiveContext({ children }: { children: (key: string) => React.ReactNode }) {
  const router = useRouter(), pathname = usePathname();
  const [context, setContext] = useState<Context | null>(null);
  const [ready, setReady] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [open, setOpen] = useState(false), [brandId, setBrandId] = useState("");
  const [selected, setSelected] = useState<Store | null>(null), [revision, setRevision] = useState(0);
  const sequence = useRef(0), previous = useRef(""), mounted = useRef(true);
  const load = useCallback(async (block = true) => {
    const attempt = ++sequence.current;
    if (block) setReady(false);
    try {
      await sessionReady;
      if (!getStoredToken()) { setContext(null); previous.current = ""; return; }
      const next = await api.get<Context>("/context");
      if (!mounted.current || attempt !== sequence.current) return;
      const identity = `${next.staff.id}:${next.active_brand?.id}:${next.active_store?.id}`;
      if (previous.current && previous.current !== identity) router.replace("/");
      if (previous.current !== identity) { invalidateRequests(); setRevision(value => value + 1); }
      previous.current = identity; setContext(next); setError("");
    } catch (e: any) {
      if (mounted.current && attempt === sequence.current) { setContext(null); setError(e.message || "Could not load active store"); }
    } finally { if (mounted.current && attempt === sequence.current) setReady(true); }
  }, [router]);
  useEffect(() => {
    mounted.current = true; void load();
    const unsubscribe = subscribeSession(() => { setOpen(false); invalidateRequests(); void load(); });
    const resume = () => { void refreshSession().then(() => load(false)).catch((e: Error) => setError(e.message)); };
    const app = AppState.addEventListener("change", state => { if (state === "active") resume(); });
    if (typeof window !== "undefined") { window.addEventListener("focus", resume); window.addEventListener("storage", resume); }
    return () => { mounted.current = false; sequence.current += 1; unsubscribe(); app.remove(); if (typeof window !== "undefined") { window.removeEventListener("focus", resume); window.removeEventListener("storage", resume); } };
  }, [load]);
  async function switchStore() {
    if (!selected || busy) return;
    setBusy(true); setError(""); setReady(false); invalidateRequests();
    try {
      const updated = await api.put<Context>("/context", { brand_id: selected.brand_id, store_id: selected.id });
      if (updated.active_brand?.id !== selected.brand_id || updated.active_store?.id !== selected.id) throw new Error("Store selection was not persisted. Retry the selection.");
      await writePreference(preferenceKey(updated.staff.id), JSON.stringify({ brand_id: selected.brand_id, store_id: selected.id }));
      setOpen(false); router.replace("/"); await load();
    } catch (e: any) { await load(); setError(e.message || "Could not switch store"); }
    finally { setBusy(false); }
  }
  const signedIn = ready && Boolean(getStoredStaff());
  return <View style={{ flex: 1 }}>
    {signedIn && pathname !== "/sign-in" && <View style={s.header}>
      <View style={{ flex: 1 }}><Text style={s.label}>ACTIVE BRAND / STORE</Text><Text style={s.title}>{context?.active_brand?.name || "Select brand"} · {context?.active_store?.name || "Select store"}</Text></View>
      <Pressable accessibilityRole="button" disabled={!ready || busy || !context} onPress={() => { setBrandId(context?.active_brand?.id || context?.brands[0]?.id || ""); setSelected(null); setOpen(true); }} style={s.button}><Text style={s.buttonText}>Switch store</Text></Pressable>
    </View>}
    {error && <View style={s.notice}><Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text><Pressable onPress={() => void load()}><Text>Retry</Text></Pressable></View>}
    {!ready || busy ? <ActivityIndicator style={{ flex: 1 }} accessibilityLabel="Loading active store" /> : signedIn && !context && pathname !== "/sign-in" ? <View style={s.notice}><Text>Store context is unavailable.</Text><Pressable onPress={() => router.replace("/sign-in")}><Text>Sign in</Text></Pressable></View> : children(`${previous.current}:${revision}`)}
    <Modal visible={open} transparent animationType="fade" onRequestClose={() => { if (!busy) setOpen(false); }}>
      <View style={s.overlay}><View style={s.dialog}>
        <Text style={s.title}>Switch brand and store</Text><Text>Changing stores closes the current screen and discards unsaved changes.</Text>
        <ScrollView style={{ maxHeight: 320 }}>
          <Text style={s.label}>BRAND</Text>
          {context?.brands.map(brand => <Pressable key={brand.id} accessibilityRole="button" accessibilityState={{ selected: brandId === brand.id }} disabled={busy} style={[s.option, brandId === brand.id && s.chosen]} onPress={() => { setBrandId(brand.id); setSelected(null); }}><Text>{brand.name}</Text></Pressable>)}
          <Text style={s.label}>STORE</Text>
          {context?.stores.filter(store => store.brand_id === brandId).map(store => <Pressable key={store.id} accessibilityRole="button" accessibilityState={{ selected: selected?.id === store.id }} disabled={busy} style={[s.option, selected?.id === store.id && s.chosen]} onPress={() => setSelected(store)}><Text>{store.name} · {store.store_code}</Text></Pressable>)}
          {context && !context.stores.some(store => store.brand_id === brandId) && <Text>No accessible stores for this brand.</Text>}
        </ScrollView>
        {selected && <Text>Switch to {context?.brands.find(b => b.id === selected.brand_id)?.name} · {selected.name}?</Text>}
        {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
        <View style={{ flexDirection: "row", gap: 16, justifyContent: "flex-end" }}>
          <Pressable disabled={busy} onPress={() => setOpen(false)} style={s.option}><Text>Cancel</Text></Pressable>
          <Pressable disabled={!selected || busy} onPress={() => void switchStore()} style={[s.button, (!selected || busy) && { opacity: 0.5 }]}><Text style={s.buttonText}>{busy ? "Switching…" : "Confirm switch"}</Text></Pressable>
        </View>
      </View></View>
    </Modal>
  </View>;
}
const s = StyleSheet.create({
  header: { padding: 14, paddingTop: 20, backgroundColor: "white", borderBottomWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 12 },
  label: { fontSize: 11, color: colors.muted, marginVertical: 8, fontWeight: "700" }, title: { fontSize: 17, color: colors.ink, fontWeight: "700" },
  button: { backgroundColor: colors.primary, borderRadius: 8, padding: 12, minHeight: 44, justifyContent: "center" }, buttonText: { color: "white", fontWeight: "700" },
  notice: { padding: 16, gap: 12 }, overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 16 },
  dialog: { backgroundColor: "white", padding: 20, borderRadius: 16, width: "100%", maxWidth: 540, alignSelf: "center", gap: 12 },
  option: { padding: 12, minHeight: 44, borderRadius: 8, marginVertical: 3 }, chosen: { backgroundColor: colors.soft, borderWidth: 1, borderColor: colors.primary }
});

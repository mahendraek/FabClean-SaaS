import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Store = { id: string; name: string; store_type: string; store_code: string };
type Order = { id: string; order_number: string; status: string; items: unknown[] };
type Event = { id: string; action: string; staff_name: string; store_id: string; at: string; notes: string };
type Handoff = { id: string; order_id: string; order_number: string; source_store_id: string; destination_store_id: string; source_name: string; destination_name: string; status: string; manifest: { service_name: string; quantity: number; unit_label: string; barcode_value?: string }[]; events: Event[] };
type Confirmation = { action: string; handoff?: Handoff };
const closed = new Set(["completed", "cancelled"]);
const labels: Record<string, string> = { dispatch: "Dispatch order", receive: "Confirm receipt", return: "Dispatch return", complete: "Confirm return received", cancel: "Cancel dispatch" };
const stateLabels: Record<string, string> = { dispatched: "In transit to destination", received: "At destination", returning: "In transit to origin", completed: "Returned to origin", cancelled: "Dispatch cancelled" };

export default function Handoffs() {
  const router = useRouter();
  const [handoffs, setHandoffs] = useState<Handoff[]>([]), [stores, setStores] = useState<Store[]>([]), [orders, setOrders] = useState<Order[]>([]);
  const [storeId, setStoreId] = useState("");
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [filter, setFilter] = useState("open"), [query, setQuery] = useState("");
  const [orderId, setOrderId] = useState(""), [destinationId, setDestinationId] = useState(""), [notes, setNotes] = useState("");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null), [formOpen, setFormOpen] = useState(false);
  async function load() {
    setLoading(true); setError("");
    try {
      const [history, destinations, localOrders, context] = await Promise.all([
        api.get<{ handoffs: Handoff[] }>("/handoffs"), api.get<{ stores: Store[] }>("/handoff-destinations"),
        api.get<{ orders: Order[] }>("/orders"), api.get<{ active_store: Store | null }>("/context")
      ]);
      setHandoffs(history.handoffs); setStores(destinations.stores); setStoreId(context.active_store?.id || "");
      setOrders(localOrders.orders.filter(order => !["completed", "collected", "cancelled", "delivered", "picked_up"].includes(order.status) && order.items.length > 0));
    } catch (e: any) { setError(e.message || "Could not load handoffs"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  const visible = useMemo(() => handoffs.filter(handoff => {
    const matches = !query.trim() || [handoff.order_number, handoff.source_name, handoff.destination_name].some(value => value.toLowerCase().includes(query.trim().toLowerCase()));
    return matches && (filter === "all" || (filter === "open" ? !closed.has(handoff.status) : closed.has(handoff.status)));
  }), [handoffs, filter, query]);
  const available = orders.filter(order => !handoffs.some(handoff => handoff.order_id === order.id && !closed.has(handoff.status)));
  async function confirm() {
    if (!confirmation || busy) return;
    setBusy(true); setError("");
    try {
      if (confirmation.action === "dispatch") {
        await api.post("/handoffs", { order_id: orderId, destination_store_id: destinationId, notes });
        setOrderId(""); setDestinationId(""); setFormOpen(false);
      } else {
        await api.post(`/handoffs/${confirmation.handoff?.id}/actions`, { action: confirmation.action, notes });
      }
      setNotes(""); setConfirmation(null); await load();
    } catch (e: any) { setError(e.message || "Could not update handoff"); }
    finally { setBusy(false); }
  }
  function actions(handoff: Handoff) {
    if (handoff.source_store_id === storeId) return handoff.status === "dispatched" ? ["cancel"] : handoff.status === "returning" ? ["complete"] : [];
    return handoff.status === "dispatched" ? ["receive"] : handoff.status === "received" ? ["return"] : [];
  }
  return <ScrollView style={{ backgroundColor: colors.soft }} contentContainerStyle={s.page}>
    <View style={s.row}><Pressable accessibilityRole="button" onPress={() => router.push("/orders")} style={s.secondary}><Text>Orders</Text></Pressable><Pressable accessibilityRole="button" disabled={loading || busy} onPress={() => void load()} style={s.secondary}><Text>Refresh</Text></Pressable></View>
    <View style={s.card}><Text style={s.title}>Store handoffs</Text><Text>Track bags and garments sent to another store in this brand. The originating store keeps the order, customer and payments.</Text><Pressable accessibilityRole="button" disabled={loading || busy} style={s.primary} onPress={() => { setFormOpen(!formOpen); setNotes(""); }}><Text style={s.primaryText}>{formOpen ? "Close dispatch form" : "New handoff"}</Text></Pressable></View>
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
    {loading && <ActivityIndicator accessibilityLabel="Loading handoffs" />}
    {formOpen && <View style={s.card}>
      <Text style={s.heading}>Dispatch from this store</Text><Text>Order</Text>
      <ScrollView style={{ maxHeight: 180 }}>{available.map(order => <Pressable accessibilityRole="button" accessibilityState={{ selected: orderId === order.id }} key={order.id} disabled={busy} style={[s.option, orderId === order.id && s.selected]} onPress={() => setOrderId(order.id)}><Text>{order.order_number}</Text></Pressable>)}</ScrollView>
      {!available.length && <Text>No eligible orders. Add items to an open order or finish its existing handoff.</Text>}
      <Text>Destination store</Text><ScrollView style={{ maxHeight: 180 }}>{stores.map(store => <Pressable accessibilityRole="button" accessibilityState={{ selected: destinationId === store.id }} disabled={busy} key={store.id} style={[s.option, destinationId === store.id && s.selected]} onPress={() => setDestinationId(store.id)}><Text>{store.name} · {store.store_type.replaceAll("_", " ")}</Text></Pressable>)}</ScrollView>
      {!stores.length && <Text>No other active stores in this brand. A brand administrator can add a hub, plant or drop-off location.</Text>}
      <Text>Shared handoff notes</Text><TextInput accessibilityLabel="Shared handoff notes" multiline maxLength={1000} style={s.input} value={notes} onChangeText={setNotes} placeholder="Bag count, seal or handling instructions" />
      <Pressable accessibilityRole="button" disabled={!orderId || !destinationId || busy} style={[s.primary, (!orderId || !destinationId || busy) && s.disabled]} onPress={() => setConfirmation({ action: "dispatch" })}><Text style={s.primaryText}>Review dispatch</Text></Pressable>
    </View>}
    <View style={s.row}>{["open", "closed", "all"].map(value => <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: filter === value }} onPress={() => setFilter(value)} style={[s.option, filter === value && s.selected]}><Text>{value === "all" ? "All handoffs" : value === "open" ? "Open handoffs" : "Closed handoffs"}</Text></Pressable>)}</View>
    <TextInput accessibilityLabel="Search handoffs" placeholder="Search order or store" style={s.input} value={query} onChangeText={setQuery} />
    {!loading && !visible.length && <Text>No handoffs in this view.</Text>}
    {visible.map(handoff => <View key={handoff.id} style={s.card}>
      <Text style={s.heading}>{handoff.order_number} · {handoff.source_store_id === storeId ? "Outgoing" : "Incoming"}</Text>
      <Text>{handoff.source_name} → {handoff.destination_name}</Text><Text style={{ color: colors.primary, fontWeight: "700" }}>{stateLabels[handoff.status] || handoff.status}</Text>
      {handoff.manifest.map((item, index) => <Text key={index}>{item.quantity} {item.unit_label} · {item.service_name}{item.barcode_value ? ` · ${item.barcode_value}` : ""}</Text>)}
      {handoff.events.map(event => <View key={event.id} style={s.event}><Text>{labels[event.action] || event.action} · {event.staff_name} · {new Date(event.at).toLocaleString()}</Text>{event.notes ? <Text>{event.notes}</Text> : null}</View>)}
      <View style={s.row}>{actions(handoff).map(action => <Pressable accessibilityRole="button" key={action} disabled={busy || loading} style={s.primary} onPress={() => { setNotes(""); setConfirmation({ action, handoff }); }}><Text style={s.primaryText}>{labels[action]}</Text></Pressable>)}</View>
    </View>)}
    <Modal visible={Boolean(confirmation)} transparent animationType="fade" onRequestClose={() => { if (!busy) setConfirmation(null); }}>
      <View style={s.overlay}><View style={s.dialog}>
        <Text style={s.heading}>{labels[confirmation?.action || ""]}</Text>
        <Text>{confirmation?.action === "dispatch" ? `${orders.find(order => order.id === orderId)?.order_number} → ${stores.find(store => store.id === destinationId)?.name}` : `${confirmation?.handoff?.order_number} · ${confirmation?.handoff?.source_name} → ${confirmation?.handoff?.destination_name}`}</Text>
        <Text>{confirmation?.action === "cancel" ? "Confirm that the garments have not left this store. A received handoff cannot be cancelled." : "Confirm the physical handoff. This adds a permanent custody event visible to both stores."}</Text>
        {confirmation?.action !== "dispatch" && <TextInput accessibilityLabel="Custody notes" multiline maxLength={1000} placeholder="Shared custody notes (optional)" style={s.input} value={notes} onChangeText={setNotes} />}
        {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
        <View style={s.row}><Pressable accessibilityRole="button" disabled={busy} style={s.secondary} onPress={() => setConfirmation(null)}><Text>Back</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={s.primary} onPress={() => void confirm()}><Text style={s.primaryText}>{busy ? "Saving…" : "Confirm handoff"}</Text></Pressable></View>
      </View></View>
    </Modal>
  </ScrollView>;
}
const s = StyleSheet.create({
  page: { padding: 18, maxWidth: 1080, width: "100%", alignSelf: "center", gap: 14 }, row: { flexDirection: "row", flexWrap: "wrap", gap: 10, alignItems: "center" },
  card: { backgroundColor: "white", borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 18, gap: 12 }, title: { fontSize: 28, fontWeight: "800", color: colors.ink }, heading: { fontSize: 18, fontWeight: "700", color: colors.ink },
  primary: { backgroundColor: colors.primary, borderRadius: 10, padding: 12, minHeight: 44, alignSelf: "flex-start", justifyContent: "center" }, primaryText: { color: "white", fontWeight: "700" }, secondary: { padding: 12, minHeight: 44 },
  option: { padding: 12, minHeight: 44, borderWidth: 1, borderColor: colors.border, borderRadius: 10, marginVertical: 3 }, selected: { backgroundColor: colors.soft, borderColor: colors.primary }, disabled: { opacity: 0.5 },
  input: { borderWidth: 1, borderColor: colors.border, backgroundColor: "white", borderRadius: 10, padding: 12, minHeight: 44 }, event: { borderLeftWidth: 2, borderColor: colors.border, paddingLeft: 10, gap: 4 },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 16 }, dialog: { backgroundColor: "white", borderRadius: 16, padding: 20, gap: 14, maxWidth: 540, width: "100%", alignSelf: "center" }
});

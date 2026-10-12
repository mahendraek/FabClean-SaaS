import { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Share, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/src/api";
import { colors } from "@/src/theme";
import { Entitlements, FEATURE_LABELS, Feature, Overrides, parseLimit, selectedFeatures } from "@/src/platform";
type Plan = { code: string; name: string; active: boolean; features: Entitlements["features"]; limits: Entitlements["limits"] };
type Brand = { id: string; name: string; slug: string; status: string; plan_code: string; entitlement_overrides: Overrides; store_count?: number; onboarding_status?: string; primary_email?: string; timezone?: string; country?: string; currency?: string };
type Invitation = { id: string; email: string; status: string; expires_at: string };
type Detail = { brand: Brand; entitlements: Entitlements; usage: { stores: number; staff: number; pending_owner_seats: number }; stores: { id: string; name: string; active: boolean }[]; invitations: Invitation[] };
type Audit = { id: string; action: string; created_at: string; actor_user_id: string; metadata: Record<string, unknown> };
const blank = () => ({ name: "", slug: "", primary_email: "", country: "US", currency: "USD", timezone: "America/Chicago", plan_code: "starter", store_name: "Main Store", store_code: "MAIN", owner_email: "" });
const featureKeys = Object.keys(FEATURE_LABELS) as Feature[];
export default function PlatformAdmin() {
  const router = useRouter();
  const [brands, setBrands] = useState<Brand[]>([]), [plans, setPlans] = useState<Plan[]>([]), [health, setHealth] = useState<any>(null);
  const [form, setForm] = useState(blank()), [detail, setDetail] = useState<Detail | null>(null), [events, setEvents] = useState<Audit[]>([]);
  const [overrides, setOverrides] = useState<Overrides>({}), [inviteEmail, setInviteEmail] = useState(""), [inviteStore, setInviteStore] = useState("");
  const [newStoreName, setNewStoreName] = useState("Main Store"), [newStoreCode, setNewStoreCode] = useState("MAIN");
  const [link, setLink] = useState(""), [error, setError] = useState(""), [success, setSuccess] = useState(""), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<{ text: string; action: () => Promise<void>; lifecycle?: boolean } | null>(null), [reason, setReason] = useState("");
  const [planForm, setPlanForm] = useState<{ code: string; name: string; active: boolean; features: Entitlements["features"]; stores: string; staff: string } | null>(null), [editingPlan, setEditingPlan] = useState(false);
  async function refresh() {
    setLoading(true); setError("");
    try {
      const [b, p, h] = await Promise.all([api.get<{ brands: Brand[] }>("/platform/brands"), api.get<{ plans: Plan[] }>("/platform/plans"), api.get<any>("/platform/health")]);
      setBrands(b.brands); setPlans(p.plans); setHealth(h);
    } catch (e: any) { setBrands([]); setPlans([]); setHealth(null); setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  async function openBrand(id: string) {
    setError(""); setLink(""); setLoading(true);
    try {
      const [d, a] = await Promise.all([api.get<Detail>(`/platform/brands/${id}`), api.get<{ events: Audit[] }>(`/platform/audit?brand_id=${encodeURIComponent(id)}`)]);
      setDetail(d); setOverrides(d.brand.entitlement_overrides || {}); setEvents(a.events);
      setForm({ ...blank(), ...d.brand, owner_email: "", store_name: "", store_code: "" });
      setInviteStore(d.stores.find(store => store.active)?.id || ""); setInviteEmail("");
    } catch (e: any) { setDetail(null); setEvents([]); setError(e.message); }
    finally { setLoading(false); }
  }
  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(""); setSuccess("");
    try { await action(); setConfirmation(null); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function saveBrand() {
    if (detail) {
      await api.put(`/platform/brands/${detail.brand.id}`, { name: form.name, slug: form.slug, primary_email: form.primary_email, country: form.country, timezone: form.timezone, currency: form.currency, plan_code: form.plan_code, entitlement_overrides: overrides });
      await refresh(); await openBrand(detail.brand.id); setSuccess("Brand and entitlements updated.");
    } else {
      const created = await api.post<Brand & { invitation?: { acceptance_url: string } }>("/platform/brands", { name: form.name, slug: form.slug || form.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""), primary_email: form.primary_email, country: form.country, currency: form.currency, timezone: form.timezone, plan_code: form.plan_code, initial_store: { name: form.store_name, store_code: form.store_code, store_type: "regular" }, owner_email: form.owner_email });
      await refresh(); await openBrand(created.id); setLink(created.invitation?.acceptance_url || ""); setSuccess("Brand created. Share the invitation with its owner.");
    }
  }
  async function lifecycle() {
    if (!detail) return;
    await api.put(`/platform/brands/${detail.brand.id}`, { status: detail.brand.status === "active" ? "suspended" : "active", reason });
    await refresh(); await openBrand(detail.brand.id); setSuccess("Brand lifecycle updated.");
  }
  async function invite() {
    if (!detail) return;
    const result = await api.post<{ acceptance_url: string }>(`/platform/brands/${detail.brand.id}/owner-invitations`, { email: inviteEmail, store_id: inviteStore });
    await openBrand(detail.brand.id); setLink(result.acceptance_url); setSuccess("Owner invitation ready to share.");
  }
  const selectedPlan = plans.find(plan => plan.code === form.plan_code);
  const previewFeatures = selectedPlan ? selectedFeatures({ ...selectedPlan, plan_code: selectedPlan.code }, overrides) : null;
  function beginPlan(plan?: Plan) {
    setEditingPlan(Boolean(plan)); setPlanForm({ code: plan?.code || "", name: plan?.name || "", active: plan?.active ?? true, features: plan?.features || Object.fromEntries(featureKeys.map(key => [key, false])) as Entitlements["features"], stores: plan?.limits.stores == null ? "" : String(plan.limits.stores), staff: plan?.limits.staff == null ? "" : String(plan.limits.staff) });
  }
  async function savePlan() {
    if (!planForm) return;
    const payload = { code: planForm.code, name: planForm.name, active: planForm.active, features: planForm.features, limits: { stores: parseLimit(planForm.stores), staff: parseLimit(planForm.staff) } };
    editingPlan ? await api.put(`/platform/plans/${planForm.code}`, payload) : await api.post("/platform/plans", payload);
    setPlanForm(null); await refresh(); if (detail) await openBrand(detail.brand.id); setSuccess("Platform plan saved.");
  }
  return <ScrollView style={{ backgroundColor: colors.soft }} contentContainerStyle={s.page}>
    <View style={s.row}><Button text="Admin" onPress={() => router.push("/admin")} /><Text style={s.title}>Platform administration</Text><Button text="Refresh platform" disabled={busy || loading} onPress={() => void refresh()} /></View>
    <Text>Manage brands, owners and platform access.</Text>
    {loading && <ActivityIndicator accessibilityLabel="Loading platform" />}
    {error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}{success && <Text style={s.success}>{success}</Text>}
    {health && <View style={s.panel}><Text style={s.heading}>Platform online</Text><Text>Active brands: {health.brand_counts.active || 0} · Suspended: {health.brand_counts.suspended || 0} · Active stores: {health.active_stores} · Pending owner invitations: {health.pending_owner_invitations}</Text></View>}
    <View style={s.row}><Button text="Add brand" disabled={busy} onPress={() => { setDetail(null); setEvents([]); setOverrides({}); setLink(""); setForm(blank()); }} />{brands.map(brand => <Button key={brand.id} text={`${brand.name} · ${brand.status} · ${brand.plan_code} · ${(brand.onboarding_status || "").replace(/_/g, " ")}`} disabled={busy} onPress={() => void openBrand(brand.id)} />)}</View>
    <View style={s.panel}><Text style={s.heading}>{detail ? "Edit brand" : "Onboard a brand"}</Text>
      <View style={s.row}><Field label="Brand name" value={form.name} onChange={name => setForm({ ...form, name })} /><Field label="Brand slug" value={form.slug} onChange={slug => setForm({ ...form, slug })} /><Field label="Contact email" value={form.primary_email} onChange={primary_email => setForm({ ...form, primary_email })} /></View>
      <View style={s.row}><Field label="Country code" value={form.country} onChange={country => setForm({ ...form, country })} /><Field label="Currency code" value={form.currency} onChange={currency => setForm({ ...form, currency })} /><Field label="Timezone" value={form.timezone} onChange={timezone => setForm({ ...form, timezone })} /></View>
      <Text style={s.label}>PLAN</Text><View style={s.row}>{plans.filter(plan => plan.active && (detail || plan.code !== "legacy")).map(plan => <Button key={plan.code} text={plan.name} selected={form.plan_code === plan.code} disabled={busy} onPress={() => setForm({ ...form, plan_code: plan.code })} />)}</View>
      {selectedPlan && <Text>Plan limits: {selectedPlan.limits.stores ?? "Unlimited"} active stores · {selectedPlan.limits.staff ?? "Unlimited"} active staff seats</Text>}
      {!detail && <View style={s.row}><Field label="Initial store name" value={form.store_name} onChange={store_name => setForm({ ...form, store_name })} /><Field label="Initial store code" value={form.store_code} onChange={store_code => setForm({ ...form, store_code })} /><Field label="Owner email" value={form.owner_email} onChange={owner_email => setForm({ ...form, owner_email })} /></View>}
      {detail && <><Text>Usage: {detail.usage.stores} active stores · {detail.usage.staff} active staff · {detail.usage.pending_owner_seats} reserved owner seats</Text><Text style={s.heading}>Brand feature overrides</Text>
        {featureKeys.map(key => <View key={key} style={s.row}><Text style={s.feature}>{FEATURE_LABELS[key]}</Text><Text>{previewFeatures?.[key] ? "Included" : "Not included"}</Text>{(["inherit", "on", "off"] as const).map(mode => <Button key={mode} text={mode === "inherit" ? `Use plan (${selectedPlan?.features[key] ? "enabled" : "disabled"})` : mode === "on" ? "Enabled" : "Disabled"} selected={mode === "inherit" ? overrides.features?.[key] === undefined : overrides.features?.[key] === (mode === "on")} disabled={busy} onPress={() => { const features = { ...overrides.features }; mode === "inherit" ? delete features[key] : features[key] = mode === "on"; setOverrides({ ...overrides, features }); }} />)}</View>)}
        {(["stores", "staff"] as const).map(key => <View key={key} style={s.row}><Text>{key === "stores" ? "Store" : "Staff"} limit override</Text><Button text={`Use plan ${key} limit`} selected={overrides.limits?.[key] === undefined} disabled={busy} onPress={() => { const limits = { ...overrides.limits }; delete limits[key]; setOverrides({ ...overrides, limits }); }} /><Field label={`${key} limit (blank = unlimited)`} value={overrides.limits?.[key] == null ? "" : String(overrides.limits[key])} onChange={value => { try { setOverrides({ ...overrides, limits: { ...overrides.limits, [key]: parseLimit(value) } }); setError(""); } catch (e: any) { setError(e.message); } }} /><Button text={`Unlimited ${key}`} selected={overrides.limits?.[key] === null} disabled={busy} onPress={() => setOverrides({ ...overrides, limits: { ...overrides.limits, [key]: null } })} /></View>)}
      </>}
      <Button text={detail ? "Review brand changes" : "Create brand and invite owner"} disabled={busy || loading || !plans.length || !form.name || (!detail && (!form.owner_email || !form.store_name || !form.store_code))} onPress={() => detail ? setConfirmation({ text: "Apply these plan and entitlement changes to this brand?", action: saveBrand }) : void perform(saveBrand)} />
      {detail && <Button text={detail.brand.status === "active" ? "Suspend brand" : "Reactivate brand"} disabled={busy} onPress={() => { setReason(""); setConfirmation({ lifecycle: true, text: detail.brand.status === "active" ? "Suspending blocks brand operations and revokes staff sessions in this brand. Existing data and pending work are retained." : "Reactivate this brand. Staff must sign in again; revoked sessions remain invalid.", action: lifecycle }); }} />}
    </View>
    {link && <View style={s.panel}><Text style={s.heading}>Owner invitation</Text><Text>Share this single-use link with the owner. It expires in 48 hours. Creating a replacement revokes the earlier link.</Text><Text selectable accessibilityLabel="Owner invitation link">{link}</Text><Button text="Share invitation" onPress={() => void Share.share({ message: link }).catch(e => setError(e.message))} /></View>}
    {detail && <View style={s.panel}><Text style={s.heading}>Brand stores</Text>{detail.stores.map(store => <View key={store.id} style={s.row}><Text>{store.name} · {store.active ? "Active" : "Inactive"}</Text>{!store.active && <Button text={`Reactivate store ${store.name}`} disabled={busy || detail.brand.status !== "active"} onPress={() => setConfirmation({ text: `Reactivate ${store.name} in this brand? Plan limits will be checked.`, action: async () => { await api.put(`/brand/stores/${store.id}`, { active: true }); await openBrand(detail.brand.id); await refresh(); } })} />}</View>)}{!detail.stores.some(store => store.active) && <><Text>Create or reactivate an initial store before inviting an owner.</Text><Field label="New store name" value={newStoreName} onChange={setNewStoreName} /><Field label="New store code" value={newStoreCode} onChange={setNewStoreCode} /><Button text="Create initial store" disabled={busy || detail.brand.status !== "active" || !newStoreName.trim() || !newStoreCode.trim()} onPress={() => void perform(async () => { await api.post("/brand/stores", { brand_id: detail.brand.id, name: newStoreName, store_code: newStoreCode, country: form.country, timezone: form.timezone }); await openBrand(detail.brand.id); await refresh(); })} /></>}</View>}
    {detail && <View style={s.panel}><Text style={s.heading}>Owner invitations</Text><Field label="Invitation email" value={inviteEmail} onChange={setInviteEmail} /><View style={s.row}>{detail.stores.filter(store => store.active).map(store => <Button key={store.id} text={store.name} selected={inviteStore === store.id} disabled={busy} onPress={() => setInviteStore(store.id)} />)}</View><Button text="Create owner invitation" disabled={busy || !inviteEmail || !inviteStore || detail.brand.status !== "active"} onPress={() => void perform(invite)} />
      {detail.invitations.map(invitation => <View key={invitation.id} style={s.row}><Text>{invitation.email} · {invitation.status} · expires {new Date(invitation.expires_at).toLocaleString()}</Text>{invitation.status === "pending" && <Button text={`Revoke invitation for ${invitation.email}`} disabled={busy} onPress={() => setConfirmation({ text: `Revoke the invitation for ${invitation.email}?`, action: async () => { await api.post(`/platform/owner-invitations/${invitation.id}/revoke`); await openBrand(detail.brand.id); } })} />}</View>)}
    </View>}
    <View style={s.panel}><Text style={s.heading}>Platform plans</Text><Button text="Add platform plan" disabled={busy} onPress={() => beginPlan()} /><View style={s.row}>{plans.map(plan => <Button key={plan.code} text={`Edit ${plan.name}`} disabled={busy || plan.code === "legacy"} onPress={() => beginPlan(plan)} />)}</View>
      {planForm && <><View style={s.row}><Field label="Plan code" value={planForm.code} editable={!editingPlan} onChange={code => setPlanForm({ ...planForm, code })} /><Field label="Plan name" value={planForm.name} onChange={name => setPlanForm({ ...planForm, name })} /><Field label="Plan store limit" value={planForm.stores} onChange={stores => setPlanForm({ ...planForm, stores })} /><Field label="Plan staff limit" value={planForm.staff} onChange={staff => setPlanForm({ ...planForm, staff })} /></View><Text>Blank limits mean unlimited. Inactive plans cannot be assigned to new brands.</Text><View style={s.row}><Text>Available for assignment</Text><Switch accessibilityLabel="Plan available for assignment" value={planForm.active} onValueChange={active => setPlanForm({ ...planForm, active })} /></View>{featureKeys.map(key => <View key={key} style={s.row}><Text style={s.feature}>{FEATURE_LABELS[key]}</Text><Switch accessibilityLabel={`Plan ${FEATURE_LABELS[key]}`} value={planForm.features[key]} onValueChange={value => setPlanForm({ ...planForm, features: { ...planForm.features, [key]: value } })} /></View>)}<Button text="Review platform plan" disabled={busy} onPress={() => setConfirmation({ text: "Shared plan changes apply to every brand assigned to this plan. Confirm the limits and features?", action: savePlan })} /><Button text="Cancel plan edit" onPress={() => setPlanForm(null)} /></>}
    </View>
    {detail && <View style={s.panel}><Text style={s.heading}>Brand audit history</Text>{events.map(event => <View key={event.id}><Text style={s.label}>{event.action} · {new Date(event.created_at).toLocaleString()}</Text><Text selectable>{JSON.stringify(event.metadata)}</Text></View>)}</View>}
    <Modal transparent visible={Boolean(confirmation)} animationType="fade" onRequestClose={() => { if (!busy) setConfirmation(null); }}><View style={s.overlay}><View style={s.dialog}><Text style={s.heading}>Confirm platform change</Text><Text>{confirmation?.text}</Text>{confirmation?.lifecycle && <Field label="Lifecycle reason" value={reason} onChange={setReason} />}{error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}<Button text="Confirm change" disabled={busy || Boolean(confirmation?.lifecycle && !reason.trim())} onPress={() => confirmation && void perform(confirmation.lifecycle ? lifecycle : confirmation.action)} /><Button text="Cancel change" disabled={busy} onPress={() => setConfirmation(null)} /></View></View></Modal>
  </ScrollView>;
}
function Button({ text, onPress, disabled = false, selected = false }: { text: string; onPress: () => void; disabled?: boolean; selected?: boolean }) { return <Pressable accessibilityRole="button" accessibilityState={{ selected, disabled }} disabled={disabled} onPress={onPress} style={[s.button, selected && s.selected, disabled && { opacity: .45 }]}><Text style={s.buttonText}>{text}</Text></Pressable>; }
function Field({ label, value, onChange, editable = true }: { label: string; value: string; onChange: (value: string) => void; editable?: boolean }) { return <View style={s.field}><Text style={s.label}>{label}</Text><TextInput accessibilityLabel={label} style={s.input} value={value || ""} editable={editable} autoCapitalize="none" onChangeText={onChange} /></View>; }
const s = StyleSheet.create({ page: { padding: 18, maxWidth: 1200, width: "100%", alignSelf: "center", gap: 16 }, title: { fontSize: 26, fontWeight: "900", color: colors.ink }, heading: { fontSize: 18, fontWeight: "800", color: colors.ink }, label: { fontSize: 12, fontWeight: "700", color: colors.muted }, row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 10 }, panel: { backgroundColor: "white", borderRadius: 16, padding: 18, gap: 14, borderWidth: 1, borderColor: colors.border }, field: { flex: 1, minWidth: 190, gap: 6 }, feature: { minWidth: 160, fontWeight: "700" }, input: { borderWidth: 1, borderColor: colors.border, borderRadius: 8, minHeight: 44, padding: 10 }, button: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.soft, padding: 12, minHeight: 44, borderRadius: 8, justifyContent: "center" }, selected: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, buttonText: { color: colors.ink, fontWeight: "700" }, error: { color: colors.danger }, success: { color: colors.success }, overlay: { flex: 1, padding: 20, backgroundColor: "rgba(0,0,0,.4)", justifyContent: "center" }, dialog: { backgroundColor: "white", width: "100%", maxWidth: 560, alignSelf: "center", borderRadius: 16, padding: 22, gap: 16 } });

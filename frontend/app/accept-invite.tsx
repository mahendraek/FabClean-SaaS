import { themedStyles } from "@/src/theme";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter, useNavigation, useRootNavigationState } from "expo-router";
import { api, writePreference } from "@/src/api";
import { cleanInviteNavigation } from "@/src/platform";
import { useInvitationToken } from "@/src/InvitationToken";
import { colors } from "@/src/theme";
type Invitation = { brand_name: string; store_name: string; email: string; existing_account: boolean; expires_at: string };
export default function AcceptInvite() {
  const router = useRouter(), params = useLocalSearchParams<{ token?: string }>();
  const navigation = useNavigation("/");
  const navigationState = useRootNavigationState();
  const buffer = useInvitationToken();
  const [token, setToken] = useState((typeof params.token === "string" ? params.token : "") || buffer.token), [info, setInfo] = useState<Invitation | null>(null);
  const [name, setName] = useState(""), [password, setPassword] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(""), [accepted, setAccepted] = useState(false);
  useEffect(() => {
    const fromLink = typeof window !== "undefined" ? new URLSearchParams(window.location.hash.slice(1)).get("token") : params.token;
    if (typeof fromLink === "string" && fromLink) {
      buffer.setToken(fromLink); setToken(fromLink);
      if (navigationState) {
        let root = navigation;
        let parent = root.getParent();
        while (parent) { root = parent; parent = root.getParent(); }
        const state = root.getState();
        if (state) root.dispatch({ type: "RESET", payload: cleanInviteNavigation(state) });
        if (typeof window !== "undefined") {
          requestAnimationFrame(() => window.history.replaceState(window.history.state, "", window.location.pathname));
        }
      }
    }
  }, [navigationState?.key]);
  async function preview() {
    setBusy(true); setError(""); setInfo(null);
    try { setInfo(await api.post<Invitation>("/auth/owner-invitations/preview", { token: token.trim() })); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function accept() {
    setBusy(true); setError("");
    try {
      const result = await api.post<{ staff_id: string; brand_id: string; store_id: string }>("/auth/owner-invitations/accept", { token: token.trim(), name, password });
      setAccepted(true); setPassword(""); setToken(""); buffer.setToken(""); setInfo(null);
      // Preference storage can fail without undoing an already committed acceptance.
      try { await writePreference(`fabclean_context_${result.staff_id}`, JSON.stringify({ brand_id: result.brand_id, store_id: result.store_id })); } catch { /* Store can be selected after sign-in. */ }
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <ScrollView contentContainerStyle={s.page}><View style={s.card}><Text style={s.title}>Join your brand</Text>
    {busy && <ActivityIndicator accessibilityLabel="Checking invitation" />}{error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {accepted ? <><Text>Owner invitation accepted. Sign in to continue.</Text><Pressable accessibilityRole="button" style={s.button} onPress={() => router.replace("/sign-in")}><Text style={s.buttonText}>Go to sign in</Text></Pressable></> : <>
      <Text>Use the owner invitation link or enter its invitation code.</Text><TextInput accessibilityLabel="Invitation code" secureTextEntry autoCorrect={false} autoCapitalize="none" style={s.input} value={token} onChangeText={value => { setToken(value); setInfo(null); }} />
      <Pressable accessibilityRole="button" disabled={busy || !token.trim()} style={s.button} onPress={() => void preview()}><Text style={s.buttonText}>Check invitation</Text></Pressable>
      {info && <><Text style={s.heading}>{info.brand_name} · {info.store_name}</Text><Text>{info.email}</Text><Text>{info.existing_account ? "Use your current account password, or continue while signed in as this account. Your password will remain unchanged." : "Create your owner account. This grants administration of this brand."}</Text>{!info.existing_account && <TextInput accessibilityLabel="Owner name" style={s.input} value={name} onChangeText={setName} placeholder="Your name" />}<TextInput accessibilityLabel={info.existing_account ? "Current password" : "New password"} style={s.input} value={password} secureTextEntry onChangeText={setPassword} placeholder={info.existing_account ? "Current password" : "New password (at least 8 characters)"} /><Pressable accessibilityRole="button" disabled={busy || (!info.existing_account && (!name.trim() || password.length < 8))} style={s.button} onPress={() => void accept()}><Text style={s.buttonText}>Accept owner invitation</Text></Pressable></>}
    </>}
  </View></ScrollView>;
}
const s = themedStyles({ page: { flexGrow: 1, padding: 20, alignItems: "center", justifyContent: "center", backgroundColor: colors.soft }, card: { width: "100%", maxWidth: 560, gap: 16, padding: 24, borderRadius: 18, backgroundColor: "white", borderWidth: 1, borderColor: colors.border }, title: { fontSize: 28, fontWeight: "900", color: colors.ink }, heading: { fontSize: 18, fontWeight: "800", color: colors.ink }, input: { borderWidth: 1, borderColor: colors.border, borderRadius: 10, minHeight: 44, padding: 12 }, button: { minHeight: 44, backgroundColor: colors.primary, borderRadius: 10, padding: 12, alignItems: "center", justifyContent: "center" }, buttonText: { color: "white", fontWeight: "800" }, error: { color: colors.danger } });

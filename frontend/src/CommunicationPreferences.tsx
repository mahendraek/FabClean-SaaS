import { useEffect, useState } from "react";
import { Pressable, Switch, Text, TextInput, View } from "react-native";
import { api } from "./api";
import { colors } from "./theme";

const options = [["email_opt_in", "Email consent"], ["sms_opt_in", "SMS consent"], ["receipts", "Order and payment receipts"], ["status_updates", "Order status updates"]] as const;
export function CommunicationPreferences({customerId}: {customerId: string}) {
  const [saved, setSaved] = useState<Record<string, any> | null>(null);
  const [draft, setDraft] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; setSaved(null); setDraft({}); setNote("");
    api.get<Record<string, any>>("/customers/"+encodeURIComponent(customerId)+"/communication-preferences").then(v => {if(active)setSaved(v);}).catch(e => {if(active)setMessage(e.message);});
    return () => {active = false;};
  }, [customerId]);
  async function save() {
    setBusy(true); setMessage("");
    try {setSaved(await api.put("/customers/"+encodeURIComponent(customerId)+"/communication-preferences", {...draft, ...(note.trim()?{consent_note:note}:{})}));setDraft({});setNote("");setMessage("Communication preferences saved");}
    catch(e:any) {setMessage(e.message);} finally {setBusy(false);}
  }
  return <View style={{gap:10}}><Text style={{fontSize:18,fontWeight:"700"}}>Communication preferences</Text><Text>Record the customer's permission before enabling a channel. Customers are opted out by default. Receipts and status updates can be selected separately.</Text>
    {saved && options.map(([key,label]) => <View key={key} style={{flexDirection:"row",alignItems:"center",gap:10}}><Text style={{flex:1}}>{label}</Text><Switch accessibilityLabel={label} disabled={busy} value={draft[key]??!!saved[key]} onValueChange={value => setDraft({...draft,[key]:value})}/></View>)}
    <TextInput accessibilityLabel="Customer consent note" placeholder="How and when did the customer give consent?" value={note} onChangeText={setNote} style={{borderWidth:1,borderColor:colors.border,borderRadius:8,padding:10}}/>
    <Pressable accessibilityRole="button" disabled={busy||!saved||!Object.keys(draft).length} onPress={()=>void save()} style={{padding:10}}><Text style={{color:colors.primary,fontWeight:"700"}}>{busy?"Saving preferences…":"Save communication preferences"}</Text></Pressable>
    {!!message&&<Text accessibilityRole="alert">{message}</Text>}
  </View>;
}

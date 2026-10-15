import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/src/api";
import { colors, themedStyles } from "@/src/theme";

export default function Notifications() {
  const router=useRouter();const [rows,setRows]=useState<any[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [pending,setPending]=useState<any|null>(null);
  async function load(){setRows((await api.get<any>("/notifications/outbox")).notifications);}
  useEffect(()=>{void load().catch(e=>setError(e.message));},[]);
  async function send(row:any,check=false){setBusy(true);setError("");try{await api.post("/notifications/outbox/"+row.id+(check?"/delivery-status":"/dispatch"));setPending(null);await load();}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  return <ScrollView contentContainerStyle={s.page}><View style={s.wrap}><Button label="Back" onPress={()=>router.back()}/><Text style={s.title}>Receipts & notifications</Text><Text>Messages belong to the selected store. Dispatch checks current consent and sender settings. Accepted means the provider received the message; delivered requires provider evidence. Uncertain outcomes cannot be resent automatically.</Text>
    <Button label="Refresh notifications" disabled={busy} onPress={()=>void load().catch(e=>setError(e.message))}/>{busy&&<ActivityIndicator/>}{!!error&&<Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {pending&&<View style={s.card}><Text style={s.heading}>Send this {pending.channel} message?</Text><Text>{pending.delivery?.recipient}</Text><Text>{pending.message}</Text><Button label="Cancel delivery" onPress={()=>setPending(null)}/><Button label="Confirm delivery" disabled={busy} onPress={()=>void send(pending)}/></View>}
    {!rows.length&&<Text>No queued receipts or notifications for this store.</Text>}
    {rows.map(row=><View key={row.id} style={s.card}><Text style={s.heading}>{row.notification_type.replaceAll("_"," ")} · {row.channel.toUpperCase()}</Text><Text>Status: {row.status} · Attempts: {row.delivery?.attempts||0}</Text><Text>{row.delivery?.subject}</Text><Text>{row.message}</Text>{!!row.error_message&&<Text style={s.error}>{row.error_message}</Text>}{row.delivery?.next_attempt_at&&<Text>Retry after {new Date(row.delivery.next_attempt_at).toLocaleString()}</Text>}
      {['queued','blocked','failed'].includes(row.status)&&<Button label={"Review delivery "+row.id} disabled={busy||row.delivery?.attempts>=3||row.status==='failed'&&!row.delivery?.retryable} onPress={()=>setPending(row)}/>}
      {row.status==='accepted'&&row.channel==='sms'&&<Button label={"Check delivery "+row.id} disabled={busy} onPress={()=>void send(row,true)}/>}
    </View>)}
  </View></ScrollView>;
}
function Button({label,onPress,disabled=false}:{label:string;onPress:()=>void;disabled?:boolean}){return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={[s.button,disabled&&{opacity:.4}]}><Text style={{color:colors.primary,fontWeight:"700"}}>{label}</Text></Pressable>}
const s=themedStyles({page:{padding:16,paddingBottom:40},wrap:{width:"100%",maxWidth:1000,alignSelf:"center",gap:14},title:{fontSize:26,fontWeight:"700"},heading:{fontSize:17,fontWeight:"700"},card:{backgroundColor:"white",borderWidth:1,borderColor:colors.border,borderRadius:12,padding:16,gap:10},button:{padding:10,borderWidth:1,borderColor:colors.border,borderRadius:8,alignSelf:"flex-start"},error:{color:colors.danger}});

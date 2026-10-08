import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

const today=()=>new Date().toISOString().slice(0,10);

export default function Financial(){
  const router=useRouter();
  const [date,setDate]=useState(today());
  const [data,setData]=useState<any>(null);
  const [err,setErr]=useState("");

  async function load(){
    setErr("");
    try{setData(await api.get<any>("/financial/daily?date="+encodeURIComponent(date)));}
    catch(e:any){setErr(e.message||"Could not load daily financial summary");}
  }
  useEffect(()=>{load();},[]);

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Admin</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Financial</Text></View>
    </View>
    <View style={s.header}><View><Text style={s.kicker}>FINANCIAL OPERATIONS</Text><Text style={s.title}>Daily Reconciliation</Text><Text style={s.sub}>Review payment totals, refunds and transactions for a business day.</Text></View></View>
    <View style={s.filter}><TextInput style={s.input} value={date} onChangeText={setDate} placeholder="YYYY-MM-DD"/><Pressable style={s.loadBtn} onPress={load}><Text style={s.loadText}>Load</Text></Pressable></View>
    {err?<Text style={s.err}>{err}</Text>:null}
    {data?<><View style={s.metrics}>
      <Metric label="Cash" value={"$"+Number(data.cash||0).toFixed(2)}/>
      <Metric label="Card" value={"$"+Number(data.card||0).toFixed(2)}/>
      <Metric label="Other" value={"$"+Number(data.other||0).toFixed(2)}/>
      <Metric label="Refunds" value={"$"+Number(data.refunds||0).toFixed(2)}/>
      <Metric label="Net Collected" value={"$"+Number(data.net_collected||0).toFixed(2)}/>
      <Metric label="Transactions" value={String(data.transaction_count||0)}/>
    </View>
    <View style={s.panel}><Text style={s.sectionTitle}>Transactions</Text>
      {(data.transactions||[]).length===0?<Text style={s.meta}>No transactions for this date.</Text>:(data.transactions||[]).map((p:any)=><View key={p.id} style={s.row}><View style={{flex:1}}><Text style={s.rowTitle}>{p.receipt_number}</Text><Text style={s.meta}>{p.transaction_type} · {p.payment_method} · {p.staff_name||"Staff"}{p.reference_number?" · "+p.reference_number:""}</Text></View><Text style={s.amount}>{Number(p.amount||0)<0?"-$"+Math.abs(Number(p.amount||0)).toFixed(2):"$"+Number(p.amount||0).toFixed(2)}</Text></View>)}
    </View></>:null}
  </ScrollView>;
}
function Metric({label,value}:{label:string;value:string}){return <View style={s.metric}><Text style={s.metricValue}>{value}</Text><Text style={s.metricLabel}>{label}</Text></View>}
const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:24},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5},
  filter:{flexDirection:"row",gap:8,flexWrap:"wrap"},input:{flex:1,borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11,backgroundColor:"#fff"},loadBtn:{backgroundColor:colors.primary,borderRadius:11,paddingHorizontal:18,minHeight:42,alignItems:"center",justifyContent:"center"},loadText:{color:"#fff",fontWeight:"900"},err:{color:colors.danger},
  metrics:{flexDirection:"row",flexWrap:"wrap",gap:10},metric:{flex:1,minWidth:150,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:15},metricValue:{fontSize:22,fontWeight:"900",color:colors.ink},metricLabel:{fontSize:11,color:colors.muted,marginTop:3},
  panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:17},sectionTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginBottom:8},row:{paddingVertical:10,borderTopWidth:1,borderTopColor:colors.border,flexDirection:"row",gap:10,alignItems:"center"},rowTitle:{fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:2},amount:{fontWeight:"900",color:colors.ink}
});
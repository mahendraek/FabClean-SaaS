import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type LoginRow={
  id:string;staff_name:string;staff_email:string;staff_role:string;ip_address:string;
  city:string;region:string;country:string;timezone:string;user_agent:string;login_at:string;
};

const pretty=(x:string)=>String(x||"").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const locationText=(x:LoginRow)=>[x.city,x.region,x.country].filter(Boolean).join(", ")||"Location unavailable";

export default function LoginAudit(){
  const router=useRouter();
  const [rows,setRows]=useState<LoginRow[]>([]);
  const [err,setErr]=useState("");
  const [loading,setLoading]=useState(true);

  async function load(){
    setLoading(true);setErr("");
    try{const x=await api.get<{logins:LoginRow[]}>("/admin/login-audit?limit=200");setRows(x.logins||[]);}
    catch(e:any){setErr(e.message||"Could not load login history");}
    finally{setLoading(false);}
  }
  useEffect(()=>{load();},[]);

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Admin</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Access Audit</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>SECURITY & DEMO USAGE</Text><Text style={s.title}>Login History</Text><Text style={s.sub}>Successful staff logins with approximate network location and browser details. Location is IP-based and may not be exact.</Text></View>
      <Pressable style={s.refreshBtn} onPress={load}><Text style={s.refreshText}>{loading?"Loading…":"Refresh"}</Text></Pressable>
    </View>

    {err?<Text style={s.err}>{err}</Text>:null}
    <View style={s.summary}><Text style={s.summaryValue}>{rows.length}</Text><Text style={s.summaryLabel}>Recent successful logins</Text></View>

    <View style={s.table}>
      {rows.length===0&&!loading?<View style={s.empty}><Text style={s.emptyTitle}>No login history yet</Text><Text style={s.meta}>New successful sign-ins will appear here.</Text></View>:rows.map(x=><View key={x.id} style={s.row}>
        <View style={s.user}><Text style={s.name}>{x.staff_name}</Text><Text style={s.meta}>{x.staff_email} · {pretty(x.staff_role)}</Text></View>
        <View style={s.col}><Text style={s.label}>Login time</Text><Text style={s.value}>{new Date(x.login_at).toLocaleString()}</Text><Text style={s.meta}>{x.timezone||"Server timestamp"}</Text></View>
        <View style={s.col}><Text style={s.label}>Approx. location</Text><Text style={s.value}>{locationText(x)}</Text><Text style={s.meta}>{x.ip_address||"IP unavailable"}</Text></View>
        <View style={s.browser}><Text style={s.label}>Browser / device</Text><Text style={s.meta} numberOfLines={2}>{x.user_agent||"Unavailable"}</Text></View>
      </View>)}
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1180,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5,maxWidth:760},refreshBtn:{backgroundColor:colors.primary,borderRadius:12,minHeight:42,paddingHorizontal:15,justifyContent:"center"},refreshText:{color:"#fff",fontWeight:"900"},
  summary:{alignSelf:"flex-start",backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:15,minWidth:190},summaryValue:{fontSize:24,fontWeight:"900",color:colors.ink},summaryLabel:{fontSize:12,color:colors.muted,marginTop:2},
  table:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,overflow:"hidden"},row:{padding:15,borderBottomWidth:1,borderBottomColor:colors.border,flexDirection:"row",gap:16,alignItems:"flex-start",flexWrap:"wrap"},user:{flex:1,minWidth:210},col:{flex:1,minWidth:180},browser:{flex:1.5,minWidth:240},name:{fontSize:15,fontWeight:"900",color:colors.ink},label:{fontSize:10,fontWeight:"900",color:colors.muted,textTransform:"uppercase"},value:{fontWeight:"800",color:colors.ink,marginTop:3},meta:{fontSize:12,color:colors.muted,marginTop:3},err:{color:colors.danger},empty:{padding:30,alignItems:"center"},emptyTitle:{fontSize:18,fontWeight:"900",color:colors.ink}
});
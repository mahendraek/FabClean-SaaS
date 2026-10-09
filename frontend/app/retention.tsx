import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Plus, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Offer={
  id:string;name:string;code?:string|null;discount_type:"fixed"|"percent";discount_value:number;
  min_order:number;first_order_only:boolean;auto_apply:boolean;active:boolean;usage_limit?:number|null;usage_count?:number;
};

const empty:Offer={id:"",name:"",code:"",discount_type:"percent",discount_value:10,min_order:0,first_order_only:false,auto_apply:false,active:true};

export default function RetentionAdmin(){
  const router=useRouter();
  const [offers,setOffers]=useState<Offer[]>([]);
  const [draft,setDraft]=useState<Offer>(empty);
  const [selected,setSelected]=useState<string|null>(null);
  const [saving,setSaving]=useState(false);
  const [err,setErr]=useState("");
  const [ok,setOk]=useState("");

  async function load(){
    setErr("");
    try{const x=await api.get<{offers:Offer[]}>("/offers?include_inactive=true");setOffers(x.offers);}
    catch(e:any){setErr(e.message||"Could not load offers");}
  }
  useEffect(()=>{load();},[]);

  function edit(o:Offer){setSelected(o.id);setDraft({...o});setErr("");setOk("");}
  function createNew(){setSelected(null);setDraft({...empty});setErr("");setOk("");}
  async function save(){
    if(!draft.name.trim()){setErr("Offer name is required");return;}
    setSaving(true);setErr("");setOk("");
    try{
      const payload={...draft,code:(draft.code||"").trim().toUpperCase()||null,discount_value:Number(draft.discount_value||0),min_order:Number(draft.min_order||0)};
      const saved=selected?await api.put<Offer>("/offers/"+selected,payload):await api.post<Offer>("/offers",payload);
      setSelected(saved.id);setDraft(saved);setOk("Offer saved");await load();
    }catch(e:any){setErr(e.message||"Could not save offer");}
    finally{setSaving(false);}
  }

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Admin</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Retention</Text></View>
    </View>
    <View style={s.header}>
      <View><Text style={s.kicker}>CUSTOMER RETENTION</Text><Text style={s.title}>Offers, Rewards & Referrals</Text><Text style={s.sub}>Configure promotional offers now; customer reward and referral activity is tracked through the customer APIs in this release.</Text></View>
      <Pressable style={s.newBtn} onPress={createNew}><Plus size={17} color="#fff"/><Text style={s.newText}>New Offer</Text></Pressable>
    </View>
    <View style={s.shortcuts}>
      <Pressable style={s.shortcut} onPress={()=>router.push("/subscriptions")}><Text style={s.shortcutTitle}>Subscriptions</Text><Text style={s.help}>Plans and recurring pickups</Text></Pressable>
      <Pressable style={s.shortcut} onPress={()=>router.push("/login-audit")}><Text style={s.shortcutTitle}>Login History</Text><Text style={s.help}>Recent staff sign-ins</Text></Pressable>
    </View>
    <View style={s.layout}>
      <View style={s.list}>
        <Text style={s.sectionTitle}>Offers</Text>
        {offers.length===0?<Text style={s.help}>No offers configured.</Text>:offers.map(o=><Pressable key={o.id} onPress={()=>edit(o)} style={[s.offerRow,selected===o.id&&s.offerRowOn]}>
          <View style={{flex:1}}><Text style={s.offerName}>{o.name}</Text><Text style={s.help}>{o.code||"Automatic / no code"} · {o.discount_type==="percent"?o.discount_value+"%":"$"+o.discount_value.toFixed(2)}</Text></View>
          <Text style={[s.status,o.active?s.active:s.inactive]}>{o.active?"Active":"Inactive"}</Text>
        </Pressable>)}
      </View>
      <View style={s.editor}>
        <Text style={s.sectionTitle}>{selected?"Edit offer":"Create offer"}</Text>
        <Text style={s.label}>Name</Text><TextInput style={s.input} value={draft.name} onChangeText={v=>setDraft(d=>({...d,name:v}))} placeholder="First Order 15% Off"/>
        <Text style={s.label}>Promo code</Text><TextInput style={s.input} value={draft.code||""} onChangeText={v=>setDraft(d=>({...d,code:v.toUpperCase()}))} placeholder="WELCOME15" autoCapitalize="characters"/>
        <Text style={s.label}>Discount type</Text>
        <View style={s.chips}>{["percent","fixed"].map(x=><Pressable key={x} onPress={()=>setDraft(d=>({...d,discount_type:x as any}))} style={[s.chip,draft.discount_type===x&&s.chipOn]}><Text style={[s.chipText,draft.discount_type===x&&s.chipTextOn]}>{x==="percent"?"Percentage":"Fixed amount"}</Text></Pressable>)}</View>
        <View style={s.row}>
          <View style={{flex:1}}><Text style={s.label}>Discount value</Text><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.discount_value)} onChangeText={v=>setDraft(d=>({...d,discount_value:Number(v)||0}))}/></View>
          <View style={{flex:1}}><Text style={s.label}>Minimum order</Text><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.min_order)} onChangeText={v=>setDraft(d=>({...d,min_order:Number(v)||0}))}/></View>
        </View>
        <View style={s.toggle}><Text style={s.toggleText}>First order only</Text><Switch value={draft.first_order_only} onValueChange={v=>setDraft(d=>({...d,first_order_only:v}))}/></View>
        <View style={s.toggle}><Text style={s.toggleText}>Auto apply</Text><Switch value={draft.auto_apply} onValueChange={v=>setDraft(d=>({...d,auto_apply:v}))}/></View>
        <View style={s.toggle}><Text style={s.toggleText}>Active</Text><Switch value={draft.active} onValueChange={v=>setDraft(d=>({...d,active:v}))}/></View>
        {err?<Text style={s.err}>{err}</Text>:null}{ok?<Text style={s.ok}>{ok}</Text>:null}
        <Pressable style={[s.saveBtn,saving&&{opacity:.5}]} disabled={saving} onPress={save}><Text style={s.saveText}>{saving?"Saving…":"Save Offer"}</Text></Pressable>
      </View>
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:30,fontWeight:"900",color:colors.ink},sub:{color:colors.muted,marginTop:5,maxWidth:700},newBtn:{backgroundColor:colors.primary,borderRadius:12,paddingHorizontal:14,minHeight:42,paddingVertical:10,justifyContent:"center",flexDirection:"row",gap:6,alignItems:"center"},newText:{color:"#fff",fontWeight:"900"},
  shortcuts:{flexDirection:"row",gap:10,flexWrap:"wrap"},shortcut:{flex:1,minWidth:220,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:14,padding:14},shortcutTitle:{fontWeight:"900",color:colors.ink},layout:{flexDirection:"row",gap:16,alignItems:"flex-start",flexWrap:"wrap"},list:{width:360,maxWidth:"100%",backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:16},editor:{flex:1,minWidth:300,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},sectionTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginBottom:10},offerRow:{paddingVertical:12,borderTopWidth:1,borderTopColor:colors.border,flexDirection:"row",gap:10,alignItems:"center"},offerRowOn:{backgroundColor:colors.primarySoft},offerName:{fontWeight:"900",color:colors.ink},help:{fontSize:12,color:colors.muted,marginTop:3},status:{fontSize:11,fontWeight:"900"},active:{color:colors.success},inactive:{color:colors.danger},
  label:{fontSize:10,fontWeight:"900",letterSpacing:.8,color:colors.muted,textTransform:"uppercase",marginTop:12,marginBottom:6},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11},row:{flexDirection:"row",gap:10,flexWrap:"wrap"},chips:{flexDirection:"row",gap:7},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:10,paddingVertical:8},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},toggle:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",backgroundColor:colors.soft,borderRadius:10,padding:10,marginTop:9},toggleText:{fontWeight:"800",color:colors.ink},saveBtn:{alignSelf:"flex-start",backgroundColor:colors.primary,borderRadius:12,paddingHorizontal:18,paddingVertical:12,marginTop:14},saveText:{color:"#fff",fontWeight:"900"},err:{color:colors.danger,marginTop:10},ok:{color:colors.success,marginTop:10}
});

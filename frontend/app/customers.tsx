import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, MagnifyingGlass, PencilSimple, Plus, Sparkle, UserCircle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Customer={
  id:string;name:string;phone:string;email?:string;notes?:string;
  order_count?:number;lifetime_value?:number;reward_points?:number;referral_code?:string;
};

export default function Customers(){
  const router=useRouter();
  const [items,setItems]=useState<Customer[]>([]);
  const [q,setQ]=useState("");
  const [err,setErr]=useState("");
  const [editing,setEditing]=useState<Customer|null>(null);
  const [form,setForm]=useState({name:"",phone:"",email:"",notes:""});
  const [saving,setSaving]=useState(false);
  const [ok,setOk]=useState("");

  async function load(search=""){
    setErr("");
    try{
      const suffix=search.trim()?("?q="+encodeURIComponent(search.trim())):"";
      const x=await api.get<{customers:Customer[]}>("/customers"+suffix);
      setItems(x.customers);
    }catch(e:any){setErr(e.message||"Could not load customers");}
  }


  function startNew(){setEditing({id:"",name:"",phone:"",email:"",notes:""});setForm({name:"",phone:"",email:"",notes:""});setErr("");setOk("");}
  function startEdit(customer:Customer){setEditing(customer);setForm({name:customer.name||"",phone:customer.phone||"",email:customer.email||"",notes:customer.notes||""});setErr("");setOk("");}
  async function saveCustomer(){
    if(!form.name.trim()||!form.phone.trim()){setErr("Name and phone are required");return;}
    setSaving(true);setErr("");setOk("");
    try{
      const payload={name:form.name.trim(),phone:form.phone.trim(),email:form.email.trim(),notes:form.notes.trim(),business_id:"demo",location_id:"main"};
      if(editing?.id) await api.put("/customers/"+editing.id,payload); else await api.post("/customers",payload);
      setOk(editing?.id?"Customer updated":"Customer created");setEditing(null);await load(q);
    }catch(e:any){setErr(e.message||"Could not save customer");}
    finally{setSaving(false);}
  }

  useEffect(()=>{load();},[]);
  const totals=useMemo(()=>({
    customers:items.length,
    orders:items.reduce((a,c)=>a+(c.order_count||0),0),
    lifetime:items.reduce((a,c)=>a+(c.lifetime_value||0),0)
  }),[items]);

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>CUSTOMERS</Text><Text style={s.title}>Customer Directory</Text><Text style={s.sub}>Find repeat customers, review order history metrics and reuse their details at the counter.</Text></View>
      <View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}><Pressable style={s.secondaryBtn} onPress={startNew}><Plus size={16} color={colors.primary}/><Text style={s.secondaryBtnText}>New Customer</Text></Pressable><Pressable style={s.newBtn} onPress={()=>router.push("/walk-in")}><Text style={s.newText}>+ New Order</Text></Pressable></View>
    </View>

    <View style={s.searchRow}>
      <View style={s.searchBox}><MagnifyingGlass size={20} color={colors.muted}/><TextInput style={s.input} placeholder="Search name, phone or email" value={q} onChangeText={setQ} onSubmitEditing={()=>load(q)}/></View>
      <Pressable style={s.findBtn} onPress={()=>load(q)}><Text style={s.findText}>Search</Text></Pressable>
      {q?<Pressable style={s.clearBtn} onPress={()=>{setQ("");load("");}}><Text style={s.clearText}>Clear</Text></Pressable>:null}
    </View>
    {err?<Text style={s.err}>{err}</Text>:null}{ok?<Text style={s.ok}>{ok}</Text>:null}
    {editing?<View style={s.editor}><View style={s.editorHead}><Text style={s.editorTitle}>{editing.id?"Edit Customer":"New Customer"}</Text><Pressable onPress={()=>setEditing(null)}><Text style={s.clearText}>Cancel</Text></Pressable></View><View style={s.formRow}><TextInput style={s.editInput} placeholder="Name *" value={form.name} onChangeText={v=>setForm(x=>({...x,name:v}))}/><TextInput style={s.editInput} placeholder="Phone *" value={form.phone} onChangeText={v=>setForm(x=>({...x,phone:v}))}/></View><View style={s.formRow}><TextInput style={s.editInput} placeholder="Email" value={form.email} onChangeText={v=>setForm(x=>({...x,email:v}))}/><TextInput style={s.editInput} placeholder="Notes" value={form.notes} onChangeText={v=>setForm(x=>({...x,notes:v}))}/></View><Pressable disabled={saving} style={[s.saveBtn,saving&&{opacity:.5}]} onPress={saveCustomer}><Text style={s.saveText}>{saving?"Saving…":"Save Customer"}</Text></Pressable></View>:null}

    <View style={s.summary}>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{totals.customers}</Text><Text style={s.summaryLabel}>Customers shown</Text></View>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{totals.orders}</Text><Text style={s.summaryLabel}>Orders represented</Text></View>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{"$"+totals.lifetime.toFixed(2)}</Text><Text style={s.summaryLabel}>Lifetime value shown</Text></View>
    </View>

    <View style={s.table}>
      {items.length===0?<View style={s.empty}><UserCircle size={38} color={colors.muted}/><Text style={s.emptyTitle}>No customers found</Text><Text style={s.meta}>Customers are created automatically when a new walk-in order is saved.</Text></View>:
      items.map(c=><Pressable key={c.id} style={s.row} onPress={()=>router.push({pathname:"/customer-profile",params:{id:c.id}})}>
        <View style={s.avatar}><Text style={s.avatarText}>{(c.name||"?").slice(0,1).toUpperCase()}</Text></View>
        <View style={s.main}><Text style={s.name}>{c.name}</Text><Text style={s.meta}>{c.phone}{c.email?" · "+c.email:""}</Text></View><Pressable onPress={(e:any)=>{e?.stopPropagation?.();startEdit(c);}} style={s.editBtn}><PencilSimple size={16} color={colors.primary}/></Pressable>
        <View style={s.metric}><Text style={s.metricLabel}>Orders</Text><Text style={s.metricValue}>{c.order_count||0}</Text></View>
        <View style={s.metric}><Text style={s.metricLabel}>Lifetime</Text><Text style={s.metricValue}>{"$"+(c.lifetime_value||0).toFixed(2)}</Text></View>
        <View style={s.metric}><Text style={s.metricLabel}>Rewards</Text><Text style={s.metricValue}>{c.reward_points||0}</Text></View><View style={s.metric}><Text style={s.metricLabel}>Referral</Text><Text style={s.referralValue}>{c.referral_code||"—"}</Text></View>
      </Pressable>)}
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap",gap:10,flexWrap:"wrap"},
  back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"700",color:colors.ink},
  brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},
  kicker:{fontSize:11,fontWeight:"900",letterSpacing:1.4,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:2},sub:{color:colors.muted,marginTop:5,maxWidth:700},
  newBtn:{backgroundColor:colors.primary,paddingHorizontal:18,minHeight:42,paddingVertical:10,alignItems:"center",justifyContent:"center",borderRadius:13},newText:{color:"#fff",fontWeight:"800"},secondaryBtn:{borderWidth:1,borderColor:colors.border,paddingHorizontal:14,paddingVertical:12,borderRadius:13,flexDirection:"row",gap:6,alignItems:"center",backgroundColor:"#fff"},secondaryBtnText:{color:colors.primary,fontWeight:"900"},
  searchRow:{flexDirection:"row",gap:10,flexWrap:"wrap",flexWrap:"wrap"},searchBox:{flex:1,flexDirection:"row",alignItems:"center",gap:10,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:14,paddingHorizontal:14},input:{flex:1,paddingVertical:14},
  findBtn:{backgroundColor:colors.ink,borderRadius:14,paddingHorizontal:18,justifyContent:"center"},findText:{color:"#fff",fontWeight:"800"},clearBtn:{borderWidth:1,borderColor:colors.border,borderRadius:14,paddingHorizontal:16,justifyContent:"center",backgroundColor:"#fff"},clearText:{fontWeight:"800",color:colors.primary},
  err:{color:colors.danger},ok:{color:colors.success,fontWeight:"800"},editor:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:16},editorHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},editorTitle:{fontSize:18,fontWeight:"900",color:colors.ink},formRow:{flexDirection:"row",gap:10,flexWrap:"wrap",marginTop:10},editInput:{flex:1,minWidth:220,borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11},saveBtn:{alignSelf:"flex-start",backgroundColor:colors.primary,borderRadius:11,paddingHorizontal:18,paddingVertical:11,marginTop:12},saveText:{color:"#fff",fontWeight:"900"},editBtn:{padding:7},summary:{flexDirection:"row",gap:10,flexWrap:"wrap"},summaryCard:{flex:1,minWidth:180,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:16},summaryValue:{fontSize:25,fontWeight:"900",color:colors.ink},summaryLabel:{color:colors.muted,marginTop:2},
  table:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,overflow:"hidden"},row:{padding:16,borderBottomWidth:1,borderBottomColor:colors.border,flexDirection:"row",alignItems:"center",gap:14,flexWrap:"wrap"},
  avatar:{width:42,height:42,borderRadius:21,backgroundColor:colors.primarySoft,alignItems:"center",justifyContent:"center"},avatarText:{fontWeight:"900",color:colors.primary,fontSize:18},main:{flex:2,minWidth:180},name:{fontWeight:"900",fontSize:16,color:colors.ink},meta:{color:colors.muted,marginTop:3},
  metric:{minWidth:105},metricLabel:{fontSize:10,fontWeight:"900",textTransform:"uppercase",color:colors.muted},metricValue:{fontSize:16,fontWeight:"900",color:colors.ink,marginTop:3},referralValue:{fontSize:13,fontWeight:"900",color:colors.primary,marginTop:3},
  empty:{padding:40,alignItems:"center"},emptyTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginTop:10}
});

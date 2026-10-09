import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, CalendarBlank, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Order={
  id:string;order_number:string;status:string;fulfillment_type?:string;
  customer:{name:string;phone:string;email?:string};
  pickup_date?:string;pickup_slot_label?:string;
  delivery_date?:string;delivery_slot_label?:string;
};

function localToday(){
  const d=new Date(), y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,"0"), day=String(d.getDate()).padStart(2,"0");
  return y+"-"+m+"-"+day;
}

export default function PickupSchedule(){
  const router=useRouter();
  const [orders,setOrders]=useState<Order[]>([]);
  const [date,setDate]=useState(localToday());
  const [query,setQuery]=useState("");
  const [mode,setMode]=useState<"all"|"pickup"|"delivery">("all");
  const [appliedDate,setAppliedDate]=useState(localToday());
  const [appliedQuery,setAppliedQuery]=useState("");
  const [appliedMode,setAppliedMode]=useState<"all"|"pickup"|"delivery">("all");
  const [err,setErr]=useState("");
  const [loading,setLoading]=useState(false);

  async function searchSchedule(nextDate=date,nextQuery=query,nextMode=mode){
    setLoading(true);setErr("");
    try{
      const x=await api.get<{orders:Order[]}>("/scheduling/orders?date="+encodeURIComponent(nextDate)+"&q="+encodeURIComponent(nextQuery.trim()));
      setOrders(x.orders||[]);
      setAppliedDate(nextDate);setAppliedQuery(nextQuery);setAppliedMode(nextMode);
    }catch(e:any){setErr(e.message||"Could not load scheduled orders");}
    finally{setLoading(false);}
  }
  useEffect(()=>{searchSchedule(localToday(),"","all");},[]);

  const events=useMemo(()=>{
    const q=appliedQuery.trim().toLowerCase();
    const rows:any[]=[];
    orders.filter(o=>["pickup_only","delivery_only","pickup_and_delivery"].includes(String(o.fulfillment_type||""))).forEach(o=>{
      if(o.pickup_date)rows.push({key:o.id+"-pickup",type:"pickup",date:o.pickup_date,slot:o.pickup_slot_label||"",order:o});
      if(o.delivery_date)rows.push({key:o.id+"-delivery",type:"delivery",date:o.delivery_date,slot:o.delivery_slot_label||"",order:o});
    });
    return rows.filter(e=>
      (!appliedDate||e.date===appliedDate)&&
      (appliedMode==="all"||e.type===appliedMode)&&
      (!q||e.order.order_number.toLowerCase().includes(q)||e.order.customer.name.toLowerCase().includes(q)||e.order.customer.phone.toLowerCase().includes(q))
    ).sort((a,b)=>(a.slot||"").localeCompare(b.slot||""));
  },[orders,appliedDate,appliedQuery,appliedMode]);

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}><Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View></View>
    <View style={s.header}><View><Text style={s.kicker}>ROUTE SCHEDULE</Text><Text style={s.title}>Scheduled Pickups & Deliveries</Text><Text style={s.sub}>View today or select a date, then search by customer, phone or order number.</Text></View><CalendarBlank size={38} color={colors.primary}/></View>

    <View style={s.filtersPanel}>
      <View style={s.dateRow}>
        <Pressable style={s.todayBtn} onPress={()=>{const d=localToday();setDate(d);searchSchedule(d,query,mode);}}><Text style={s.todayText}>Today</Text></Pressable>
        <TextInput style={s.dateInput} placeholder="YYYY-MM-DD" value={date} onChangeText={setDate} autoCapitalize="none"/>
        <TextInput style={s.search} placeholder="Search customer, phone or order" value={query} onChangeText={setQuery} onSubmitEditing={()=>searchSchedule(date,query,mode)}/>
        <Pressable style={s.searchBtn} onPress={()=>searchSchedule(date,query,mode)}><Text style={s.searchBtnText}>{loading?"Searching…":"Search"}</Text></Pressable>
      </View>
      <View style={s.modeRow}>{(["all","pickup","delivery"] as const).map(x=><Pressable key={x} onPress={()=>setMode(x)} style={[s.modeBtn,mode===x&&s.modeBtnOn]}><Text style={[s.modeText,mode===x&&s.modeTextOn]}>{x==="all"?"All":x==="pickup"?"Pickups":"Deliveries"}</Text></Pressable>)}</View>
    </View>

    {err?<Text style={s.err}>{err}</Text>:null}
    <View style={s.summary}><Text style={s.summaryValue}>{loading?"…":events.length}</Text><Text style={s.summaryLabel}>scheduled event{events.length===1?"":"s"} for {appliedDate||"all dates"}</Text></View>

    <View style={s.list}>
      {events.length===0?<View style={s.empty}><Text style={s.emptyTitle}>No scheduled pickups or deliveries</Text><Text style={s.meta}>Change the date or search filters to view another schedule.</Text></View>:events.map(e=><Pressable key={e.key} style={s.card} onPress={()=>router.push({pathname:"/order-detail",params:{id:e.order.id}})}>
        <View style={[s.typeBadge,e.type==="pickup"?s.pickup:s.delivery]}><Text style={s.typeText}>{e.type==="pickup"?"PICKUP":"DELIVERY"}</Text></View>
        <View style={s.cardMain}><Text style={s.orderNo}>{e.order.order_number} · {e.order.customer.name}</Text><Text style={s.meta}>{e.order.customer.phone} · {e.slot||"Time not set"}</Text><Text style={s.meta}>Status: {String(e.order.status||"received").replaceAll("_"," ")}</Text></View>
        <Text style={s.open}>Open →</Text>
      </Pressable>)}
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:14},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:30,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5},
  filtersPanel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:16,gap:10},dateRow:{flexDirection:"row",flexWrap:"wrap",gap:8},todayBtn:{backgroundColor:colors.primary,borderRadius:11,paddingHorizontal:16,justifyContent:"center",minHeight:43},todayText:{color:"#fff",fontWeight:"900"},dateInput:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11,minWidth:150},search:{flex:1,minWidth:240,borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11},searchBtn:{backgroundColor:colors.ink,borderRadius:11,paddingHorizontal:18,justifyContent:"center",minHeight:43},searchBtnText:{color:"#fff",fontWeight:"900"},modeRow:{flexDirection:"row",gap:8,flexWrap:"wrap"},modeBtn:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:13,paddingVertical:8},modeBtnOn:{backgroundColor:colors.primary,borderColor:colors.primary},modeText:{fontWeight:"800",color:colors.ink},modeTextOn:{color:"#fff"},
  summary:{flexDirection:"row",alignItems:"baseline",gap:7},summaryValue:{fontSize:26,fontWeight:"900",color:colors.primary},summaryLabel:{color:colors.muted},list:{gap:8},card:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:15,padding:14,flexDirection:"row",alignItems:"center",gap:12},typeBadge:{borderRadius:999,paddingHorizontal:9,paddingVertical:6},pickup:{backgroundColor:colors.primarySoft},delivery:{backgroundColor:colors.softBlue},typeText:{fontSize:10,fontWeight:"900",color:colors.ink},cardMain:{flex:1},orderNo:{fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:3},open:{fontWeight:"900",color:colors.primary},empty:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:24,alignItems:"center"},emptyTitle:{fontWeight:"900",fontSize:17,color:colors.ink},err:{color:colors.danger}
});

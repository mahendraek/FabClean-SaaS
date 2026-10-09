import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, MagnifyingGlass, Package, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { defaultHardwareProfile, normalizeScan, profileFromSettings, HardwareProfile } from "@/src/hardware";
import { colors } from "@/src/theme";

type Order={id:string;order_number:string;barcode_value:string;status:string;total:number;payment_status:string;fulfillment_type:string;created_at:string;customer:{name:string;phone:string}};
const pretty=(x:string)=>x.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());

export default function Orders(){
  const router=useRouter();
  const [items,setItems]=useState<Order[]>([]);
  const [q,setQ]=useState("");
  const [selected,setSelected]=useState<Order|null>(null);
  const [statusFilter,setStatusFilter]=useState("all");
  const [paymentFilter,setPaymentFilter]=useState("all");
  const [fromDate,setFromDate]=useState("");
  const [toDate,setToDate]=useState("");
  const [err,setErr]=useState("");
  const [loading,setLoading]=useState(true);
  const [hardware,setHardware]=useState<HardwareProfile>(defaultHardwareProfile);

  async function load(){
    setLoading(true);
    setErr("");
    try{
      const x=await api.get<{orders:Order[],scope?:string}>("/orders");
      setItems(x.orders||[]);
    }catch(e:any){
      if(e?.status===401){
        setErr("Your staff session has expired. Please sign in again.");
        router.replace("/sign-in");
        return;
      }
      if(e?.status===403){
        setErr("Your role does not have permission to view orders.");
        return;
      }
      setErr(e.message||"Could not load orders");
    }finally{
      setLoading(false);
    }
  }

  useEffect(()=>{load();api.get<any>("/settings").then(x=>setHardware(profileFromSettings(x))).catch(()=>{});},[]);

  const filtered=useMemo(()=>{
    const z=q.trim().toLowerCase();
    return items.filter(o=>{
      const matchesText=!z||[o.order_number,o.barcode_value,o.customer.name,o.customer.phone,o.status]
        .some(v=>String(v||"").toLowerCase().includes(z));
      const matchesStatus=statusFilter==="all"||o.status===statusFilter;
      const matchesPayment=paymentFilter==="all"||o.payment_status===paymentFilter;
      const d=String(o.created_at||"").slice(0,10);
      const matchesDate=(!fromDate||d>=fromDate)&&(!toDate||d<=toDate);
      return matchesText&&matchesStatus&&matchesPayment&&matchesDate;
    });
  },[q,items,statusFilter,paymentFilter,fromDate,toDate]);

  async function findExact(){
    const value=normalizeScan(q,hardware);
    if(!value)return;
    setErr("");
    try{const order=await api.get<Order>("/orders/"+encodeURIComponent(value));setSelected(order);setQ("");}
    catch(e:any){setErr(e.message)}
  }

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable>
      <Pressable onPress={()=>router.push("/handoffs")} style={s.back}><Text style={s.backText}>Store handoffs</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>FIND ORDER</Text><Text style={s.title}>Find Order</Text><Text style={s.sub}>Scan the bill/order barcode, enter the order number, or search by customer name or phone.</Text></View>
      <Pressable style={s.newBtn} onPress={()=>router.push("/walk-in")}><Text style={s.newText}>+ Create Order</Text></Pressable>
    </View>

    <View style={s.searchRow}>
      <View style={s.searchBox}><MagnifyingGlass size={20} color={colors.muted}/><TextInput value={q} onChangeText={setQ} placeholder="Scan bill/order barcode or search order, customer, phone" style={s.input} autoCapitalize="characters" onSubmitEditing={findExact}/></View>
      <Pressable style={s.findBtn} onPress={findExact}><Text style={s.findText}>Find / Scan</Text></Pressable>
    </View>

    <View style={s.filters}>
      <View style={s.filterGroup}><Text style={s.filterLabel}>Status</Text><View style={s.chips}>{["all","received","inspection","cleaning","quality_check","ready_for_pickup","collected","completed"].map(x=><Pressable key={x} onPress={()=>setStatusFilter(x)} style={[s.chip,statusFilter===x&&s.chipOn]}><Text style={[s.chipText,statusFilter===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View></View>
      <View style={s.filterGroup}><Text style={s.filterLabel}>Payment</Text><View style={s.chips}>{["all","unpaid","partial","paid"].map(x=><Pressable key={x} onPress={()=>setPaymentFilter(x)} style={[s.chip,paymentFilter===x&&s.chipOn]}><Text style={[s.chipText,paymentFilter===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View></View>
      <View style={s.dateRow}><View style={s.dateField}><Text style={s.filterLabel}>From</Text><TextInput value={fromDate} onChangeText={setFromDate} placeholder="YYYY-MM-DD" style={s.dateInput}/></View><View style={s.dateField}><Text style={s.filterLabel}>To</Text><TextInput value={toDate} onChangeText={setToDate} placeholder="YYYY-MM-DD" style={s.dateInput}/></View><Pressable style={s.clearBtn} onPress={()=>{setStatusFilter("all");setPaymentFilter("all");setFromDate("");setToDate("");setQ("");}}><Text style={s.clearText}>Clear filters</Text></Pressable></View>
    </View>

    {err?<Text style={s.err}>{err}</Text>:null}

    {selected?<View style={s.selected}>
      <Text style={s.selectedKicker}>MATCHED ORDER</Text>
      <Text style={s.selectedTitle}>{selected.order_number}</Text>
      <Text style={s.meta}>{selected.customer.name} · {selected.customer.phone}</Text>
      <View style={s.detailRow}><Text style={s.status}>{pretty(selected.status)}</Text><Text style={s.amount}>{"$"+selected.total.toFixed(2)}</Text></View>
      <Text style={s.meta}>Barcode: {selected.barcode_value}</Text><Pressable style={s.openBtn} onPress={()=>router.push({pathname:"/order-detail",params:{id:selected.id}})}><Text style={s.openBtnText}>Open Order Details</Text></Pressable>
    </View>:null}

    <View style={s.summary}>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{items.length}</Text><Text style={s.summaryLabel}>Total orders</Text></View>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{items.filter(x=>x.status==="ready_for_pickup").length}</Text><Text style={s.summaryLabel}>Ready for pickup</Text></View>
      <View style={s.summaryCard}><Text style={s.summaryValue}>{items.filter(x=>x.payment_status!=="paid").length}</Text><Text style={s.summaryLabel}>Payment pending</Text></View>
    </View>

    <View style={s.listHeader}><Text style={s.listTitle}>Recent / Matching Orders</Text><Text style={s.count}>{filtered.length} shown</Text></View>

    <View style={s.table}>
      {loading
        ? <View style={s.empty}><Package size={36} color={colors.muted}/><Text style={s.emptyTitle}>Loading orders…</Text></View>
        : filtered.length===0 && !err
        ? <View style={s.empty}><Package size={36} color={colors.muted}/><Text style={s.emptyTitle}>No orders found</Text><Text style={s.meta}>Create an order or change your search.</Text></View>
        : filtered.map(o=><Pressable key={o.id} onPress={()=>router.push({pathname:"/order-detail",params:{id:o.id}})} style={s.row}>
            <View style={s.orderMain}><Text style={s.orderNo}>{o.order_number}</Text><Text style={s.meta}>{o.customer.name} · {o.customer.phone}</Text></View>
            <View style={s.col}><Text style={s.label}>Status</Text><Text style={s.status}>{pretty(o.status)}</Text></View>
            <View style={s.col}><Text style={s.label}>Payment</Text><Text style={[s.pay,o.payment_status==="paid"&&{color:colors.success}]}>{pretty(o.payment_status)}</Text></View>
            <View style={s.amountCol}><Text style={s.label}>Total</Text><Text style={s.amount}>{"$"+o.total.toFixed(2)}</Text></View>
          </Pressable>)
      }
    </View>
  </ScrollView>
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},
  back:{flexDirection:"row",gap:7,alignItems:"center"},
  backText:{fontWeight:"700",color:colors.ink},
  brand:{flexDirection:"row",alignItems:"center",gap:6},
  brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},
  kicker:{fontSize:11,fontWeight:"900",letterSpacing:1.4,color:colors.primary},
  title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:2},
  sub:{color:colors.muted,marginTop:5},
  newBtn:{backgroundColor:colors.primary,paddingHorizontal:18,minHeight:42,paddingVertical:10,alignItems:"center",justifyContent:"center",borderRadius:13},
  newText:{color:"#fff",fontWeight:"800"},
  searchRow:{flexDirection:"row",gap:10,flexWrap:"wrap"},
  searchBox:{flex:1,flexDirection:"row",alignItems:"center",gap:10,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:14,paddingHorizontal:14},
  input:{flex:1,paddingVertical:14},
  findBtn:{backgroundColor:colors.ink,borderRadius:14,paddingHorizontal:18,justifyContent:"center"},
  findText:{color:"#fff",fontWeight:"800"},
  filters:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:14,gap:12},filterGroup:{gap:7},filterLabel:{fontSize:10,fontWeight:"900",letterSpacing:.7,color:colors.muted,textTransform:"uppercase"},chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:10,paddingVertical:7},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},dateRow:{flexDirection:"row",gap:8,alignItems:"flex-end",flexWrap:"wrap"},dateField:{minWidth:160,flex:1},dateInput:{borderWidth:1,borderColor:colors.border,borderRadius:10,paddingHorizontal:11,paddingVertical:9,backgroundColor:"#fff"},clearBtn:{borderWidth:1,borderColor:colors.border,borderRadius:10,minHeight:40,paddingHorizontal:13,justifyContent:"center"},clearText:{fontWeight:"800",color:colors.primary},
  err:{color:colors.danger},
  selected:{backgroundColor:colors.primarySoft,borderRadius:18,padding:18,borderWidth:1,borderColor:"#BFE6DE"},
  selectedKicker:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.primary},
  selectedTitle:{fontSize:22,fontWeight:"900",color:colors.ink,marginTop:3},
  detailRow:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",marginVertical:8},
  summary:{flexDirection:"row",gap:10,flexWrap:"wrap"},
  summaryCard:{flex:1,minWidth:180,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:16},
  summaryValue:{fontSize:25,fontWeight:"900",color:colors.ink},
  summaryLabel:{color:colors.muted,marginTop:2},
  listHeader:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",marginTop:4},
  listTitle:{fontSize:20,fontWeight:"900",color:colors.ink},
  count:{color:colors.muted,fontWeight:"700"},
  table:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,overflow:"hidden"},
  row:{padding:16,borderBottomWidth:1,borderBottomColor:colors.border,flexDirection:"row",alignItems:"center",gap:18,flexWrap:"wrap"},
  orderMain:{flex:2,minWidth:180},
  col:{flex:1,minWidth:120},
  amountCol:{minWidth:90,alignItems:"flex-end"},
  orderNo:{fontSize:16,fontWeight:"900",color:colors.ink},
  meta:{color:colors.muted,marginTop:3},
  label:{fontSize:10,fontWeight:"800",color:colors.muted,textTransform:"uppercase"},
  status:{fontWeight:"800",color:colors.primary,marginTop:3},
  pay:{fontWeight:"800",color:colors.accentDark,marginTop:3},
  amount:{fontWeight:"900",fontSize:17,color:colors.ink},
  openBtn:{alignSelf:"flex-start",marginTop:12,backgroundColor:colors.primary,borderRadius:10,paddingHorizontal:14,paddingVertical:9},openBtnText:{color:"#fff",fontWeight:"900"},empty:{padding:36,alignItems:"center"},
  emptyTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginTop:10}
});

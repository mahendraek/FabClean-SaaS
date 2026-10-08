import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, DownloadSimple, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Order={id:string;order_number:string;created_at:string;status:string;total:number;customer:{name:string;phone:string};items:any[]};
type Ledger={payments:any[];paid_total:number;balance_due:number;order_total:number};

const isoToday=()=>new Date().toISOString().slice(0,10);
const isoMonthStart=()=>{const d=new Date();return new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),1)).toISOString().slice(0,10)};
const money=(n:number)=>"$"+Number(n||0).toFixed(2);

export default function Reports(){
  const router=useRouter();
  const [fromDate,setFromDate]=useState(isoMonthStart());
  const [toDate,setToDate]=useState(isoToday());
  const [orders,setOrders]=useState<Order[]>([]);
  const [ledgers,setLedgers]=useState<Record<string,Ledger>>({});
  const [loading,setLoading]=useState(false);
  const [err,setErr]=useState("");

  async function load(){
    setLoading(true);setErr("");
    try{
      const o=await api.get<{orders:Order[]}>("/orders");
      const all=o.orders||[];
      const pairs=await Promise.all(all.map(async order=>{
        try{return [order.id,await api.get<Ledger>("/orders/"+encodeURIComponent(order.id)+"/payments")] as const;}
        catch{return [order.id,{payments:[],paid_total:0,balance_due:Number(order.total||0),order_total:Number(order.total||0)}] as const;}
      }));
      setOrders(all);
      setLedgers(Object.fromEntries(pairs));
    }catch(e:any){setErr(e.message||"Could not load reports");}
    finally{setLoading(false);}
  }
  useEffect(()=>{load();},[]);

  const filtered=useMemo(()=>orders.filter(o=>{
    const d=String(o.created_at||"").slice(0,10);
    return (!fromDate||d>=fromDate)&&(!toDate||d<=toDate);
  }),[orders,fromDate,toDate]);

  const metrics=useMemo(()=>{
    const orderValue=filtered.reduce((s,o)=>s+Number(o.total||0),0);
    const collected=filtered.reduce((s,o)=>s+Number(ledgers[o.id]?.paid_total||0),0);
    const outstanding=filtered.reduce((s,o)=>s+Number(ledgers[o.id]?.balance_due||0),0);
    const pending=filtered.filter(o=>Number(ledgers[o.id]?.balance_due||0)>.005).length;

    const serviceMap:Record<string,{qty:number,revenue:number}>={};
    for(const o of filtered){
      for(const i of o.items||[]){
        const key=i.service_name||"Other";
        const qty=Number(i.quantity||0), revenue=qty*Number(i.unit_price||0);
        serviceMap[key]??={qty:0,revenue:0};
        serviceMap[key].qty+=qty; serviceMap[key].revenue+=revenue;
      }
    }
    const paymentMap:Record<string,number>={};
    for(const o of filtered){
      for(const p of ledgers[o.id]?.payments||[]){
        const method=String(p.payment_method||"other");
        paymentMap[method]=(paymentMap[method]||0)+Number(p.amount||0);
      }
    }
    return {orderValue,collected,outstanding,pending,serviceMap,paymentMap};
  },[filtered,ledgers]);

  function exportCsv(){
    if(typeof window==="undefined")return;
    const esc=(v:any)=>'"'+String(v??"").replaceAll('"','""')+'"';
    const rows=[["Order","Date","Customer","Status","Order Total","Paid","Balance"]];
    filtered.forEach(o=>rows.push([o.order_number,String(o.created_at||"").slice(0,10),o.customer?.name||"",o.status,Number(o.total||0).toFixed(2),Number(ledgers[o.id]?.paid_total||0).toFixed(2),Number(ledgers[o.id]?.balance_due||0).toFixed(2)]));
    const csv=rows.map(r=>r.map(esc).join(",")).join("\n");
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="fabclean-report-"+fromDate+"-to-"+toDate+".csv";a.click();URL.revokeObjectURL(url);
  }

  const serviceRows=Object.entries(metrics.serviceMap).sort((a,b)=>b[1].revenue-a[1].revenue);
  const paymentRows=Object.entries(metrics.paymentMap).sort((a,b)=>b[1]-a[1]);
  const outstandingRows=filtered.filter(o=>Number(ledgers[o.id]?.balance_due||0)>.005);

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Admin</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Reports</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>REPORTING</Text><Text style={s.title}>Business Reports</Text><Text style={s.sub}>Review order value, collections, balances, services and payment methods for any date range.</Text></View>
      <Pressable style={s.exportBtn} onPress={exportCsv}><DownloadSimple size={17} color="#fff"/><Text style={s.exportText}>Export CSV</Text></Pressable>
    </View>

    <View style={s.filters}>
      <View style={s.field}><Text style={s.label}>From</Text><TextInput style={s.input} value={fromDate} onChangeText={setFromDate} placeholder="YYYY-MM-DD"/></View>
      <View style={s.field}><Text style={s.label}>To</Text><TextInput style={s.input} value={toDate} onChangeText={setToDate} placeholder="YYYY-MM-DD"/></View>
      <Pressable style={s.refreshBtn} onPress={load}><Text style={s.refreshText}>{loading?"Loading…":"Refresh"}</Text></Pressable>
    </View>
    {err?<Text style={s.err}>{err}</Text>:null}

    <View style={s.metrics}>
      <Metric label="Orders" value={String(filtered.length)}/>
      <Metric label="Order value" value={money(metrics.orderValue)}/>
      <Metric label="Payments collected" value={money(metrics.collected)}/>
      <Metric label="Outstanding balance" value={money(metrics.outstanding)}/>
      <Metric label="Orders with balance" value={String(metrics.pending)}/>
      <Metric label="Average order" value={money(filtered.length?metrics.orderValue/filtered.length:0)}/>
    </View>

    <View style={s.twoCol}>
      <View style={s.panel}><Text style={s.sectionTitle}>Revenue by service</Text>
        {serviceRows.length===0?<Text style={s.meta}>No service activity in this period.</Text>:serviceRows.map(([name,v])=><View key={name} style={s.row}><View style={{flex:1}}><Text style={s.rowTitle}>{name}</Text><Text style={s.meta}>{v.qty} units</Text></View><Text style={s.amount}>{money(v.revenue)}</Text></View>)}
      </View>
      <View style={s.panel}><Text style={s.sectionTitle}>Payments by method</Text>
        {paymentRows.length===0?<Text style={s.meta}>No payments in this period.</Text>:paymentRows.map(([name,total])=><View key={name} style={s.row}><Text style={[s.rowTitle,{flex:1,textTransform:"capitalize"}]}>{name}</Text><Text style={s.amount}>{money(total)}</Text></View>)}
      </View>
    </View>

    <View style={s.panel}><View style={s.panelHead}><Text style={s.sectionTitle}>Outstanding balances</Text><Text style={s.meta}>{outstandingRows.length} orders</Text></View>
      {outstandingRows.length===0?<Text style={s.meta}>No outstanding balances in this period.</Text>:outstandingRows.map(o=><Pressable key={o.id} style={s.row} onPress={()=>router.push("/order-detail?id="+encodeURIComponent(o.id))}><View style={{flex:1}}><Text style={s.rowTitle}>{o.order_number} · {o.customer?.name}</Text><Text style={s.meta}>{String(o.created_at||"").slice(0,10)} · {o.status.replaceAll("_"," ")}</Text></View><View style={{alignItems:"flex-end"}}><Text style={s.amount}>{money(Number(ledgers[o.id]?.balance_due||0))}</Text><Text style={s.meta}>of {money(o.total)}</Text></View></Pressable>)}
    </View>
  </ScrollView>
}

function Metric({label,value}:{label:string;value:string}){return <View style={s.metric}><Text style={s.metricValue}>{value}</Text><Text style={s.metricLabel}>{label}</Text></View>}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1180,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5,maxWidth:760},
  exportBtn:{backgroundColor:colors.primary,borderRadius:12,minHeight:42,paddingHorizontal:15,paddingVertical:10,flexDirection:"row",gap:7,alignItems:"center",justifyContent:"center"},exportText:{color:"#fff",fontWeight:"900"},
  filters:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:14,flexDirection:"row",gap:10,alignItems:"flex-end",flexWrap:"wrap"},field:{flex:1,minWidth:180},label:{fontSize:10,fontWeight:"900",letterSpacing:.7,color:colors.muted,textTransform:"uppercase",marginBottom:5},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11,backgroundColor:"#fff"},refreshBtn:{backgroundColor:colors.ink,borderRadius:11,minHeight:43,paddingHorizontal:18,justifyContent:"center"},refreshText:{color:"#fff",fontWeight:"900"},
  metrics:{flexDirection:"row",gap:10,flexWrap:"wrap"},metric:{flex:1,minWidth:165,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:15},metricValue:{fontSize:23,fontWeight:"900",color:colors.ink},metricLabel:{fontSize:12,color:colors.muted,marginTop:3},
  twoCol:{flexDirection:"row",gap:14,flexWrap:"wrap"},panel:{flex:1,minWidth:300,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:17},panelHead:{flexDirection:"row",justifyContent:"space-between",gap:10,alignItems:"center",flexWrap:"wrap"},sectionTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginBottom:7},row:{paddingVertical:10,borderTopWidth:1,borderTopColor:colors.border,flexDirection:"row",gap:12,alignItems:"center"},rowTitle:{fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:2},amount:{fontWeight:"900",color:colors.ink},err:{color:colors.danger}
});

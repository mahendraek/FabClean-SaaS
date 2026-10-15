import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, ScrollView, Share, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { api } from '@/src/api';
import { SelectField } from '@/src/SelectField';
import { colors, themedStyles } from '@/src/theme';

type Options = {brand_id:string;active_store_id:string;can_report_brand:boolean;timezone:string;stores:{id:string;name:string;active:boolean}[];default_from_date:string;default_to_date:string;statuses:string[]};
type Metrics = {orders:number;overdue:number;awaiting_pricing:number;cancelled:number;orders_with_balance:number;turnaround_samples:number;turnaround_missing:number;average_turnaround_hours:number|null;unspecified_currency:number};
type Money = {currency:string;orders:number;order_value:string;paid_on_orders:string;outstanding:string;overpaid:string;payments:string;refunds:string;adjustments:string;other_transactions:string;net_collected:string;payment_methods:Record<string,string>};
type Report = Options & {generated_at:string;metrics:Metrics;currencies:Money[];by_store:{store_id:string;store_name:string;metrics:Metrics;currencies:Money[]}[]};
type Row = {id:string;order_number:string;store_id:string;store_name:string;created_at:string;status:string;currency:string;order_value:string;paid_on_orders:string;outstanding:string;overpaid:string;turnaround_hours:number|null;overdue:boolean};
type Detail = {orders:Row[];total:number};
const label = (s:string)=>s.replaceAll('_',' ');

export default function Reports(){
 const router=useRouter();
 const [options,setOptions]=useState<Options|null>(null),[report,setReport]=useState<Report|null>(null),[detail,setDetail]=useState<Detail|null>(null);
 const [from,setFrom]=useState(''),[to,setTo]=useState(''),[store,setStore]=useState(''),[status,setStatus]=useState('');
 const [applied,setApplied]=useState(''),[offset,setOffset]=useState(0),[loading,setLoading]=useState(true),[exporting,setExporting]=useState(false),[error,setError]=useState('');
 const sequence=useRef(0);
 const query=(f=from,t=to,st=store,ss=status)=>`from_date=${encodeURIComponent(f)}&to_date=${encodeURIComponent(t)}&scope=${st==='all'?'brand':'store'}${st==='all'?'':'&store_id='+encodeURIComponent(st)}${ss?'&status='+encodeURIComponent(ss):''}`;
 const current=query(),dirty=current!==applied;
 async function load(q:string,page=0){
  const seq=++sequence.current;setLoading(true);setError('');setReport(null);setDetail(null);
  try{
   const r=await api.get<Report & Detail>('/reports/summary?'+q+'&offset='+page+'&limit=25');
   if(sequence.current===seq){setReport(r);setDetail({orders:r.orders,total:r.total});setApplied(q);setOffset(page);}
  }catch(e:any){if(sequence.current===seq)setError(e.message||'Could not load report');}
  finally{if(sequence.current===seq)setLoading(false);}
 }
 useEffect(()=>{
  let active=true;
  api.get<Options>('/reports/options').then(o=>{
   if(!active)return;setOptions(o);setFrom(o.default_from_date);setTo(o.default_to_date);setStore(o.active_store_id);
   void load(query(o.default_from_date,o.default_to_date,o.active_store_id,''));
  }).catch(e=>{if(active){setError(e.message);setLoading(false);}});
  return()=>{active=false;sequence.current++;};
 },[]);
 async function exportCsv(dataset:'orders'|'summary'){
  if(dirty||!report||loading||exporting)return;
  const seq=sequence.current;setExporting(true);setError('');
  try{
   const text=await api.getText('/reports/export?'+applied+'&dataset='+dataset);
   if(sequence.current!==seq)return;
   const filename=`fabclean-${dataset}-report-${from}-to-${to}.csv`;
   if(Platform.OS==='web'){
    const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   }else await Share.share({message:text,title:filename});
  }catch(e:any){if(sequence.current===seq)setError(e.message||'Could not export report');}
  finally{setExporting(false);}
 }
 const disabled=dirty||loading||!report||exporting;
 return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
  <Pressable accessibilityRole="button" onPress={()=>router.back()}><Text style={s.link}>Back</Text></Pressable>
  <View style={s.panel}><Text style={s.title}>Business Reports</Text><Text style={s.meta}>Compare authorized stores, review order value and payments, and export order details.</Text>
   {options?<Text style={s.meta}>Dates use brand timezone: {options.timezone}. Report filters do not change your active store.</Text>:null}
  </View>
  {options?<View style={s.panel}>
   <View style={s.filters}>
    <View style={s.field}><Text>From date</Text><TextInput accessibilityLabel="Report from date" value={from} onChangeText={setFrom} placeholder="YYYY-MM-DD" style={s.input}/></View>
    <View style={s.field}><Text>To date</Text><TextInput accessibilityLabel="Report to date" value={to} onChangeText={setTo} placeholder="YYYY-MM-DD" style={s.input}/></View>
    <View style={s.field}><SelectField label="Report store" value={store} onChange={setStore} options={[...(options.can_report_brand?[{code:'all',name:'All brand stores'}]:[]),...options.stores.map(v=>({code:v.id,name:v.name+(v.active?'':' (inactive)')}))]}/></View>
    <View style={s.field}><SelectField label="Report status" value={status} onChange={setStatus} options={[{code:'',name:'All statuses'},...options.statuses.map(v=>({code:v,name:label(v)}))]}/></View>
   </View>
   <View style={s.actions}><Button title={loading?'Loading…':'Apply filters'} disabled={loading||exporting} onPress={()=>void load(current)}/><Button title={exporting?'Exporting…':'Export CSV'} disabled={disabled} onPress={()=>void exportCsv('orders')}/><Button title="Export summary CSV" disabled={disabled} onPress={()=>void exportCsv('summary')}/></View>
   {dirty&&report?<Text style={s.meta}>Filters changed. Apply filters to update results and enable export.</Text>:null}
  </View>:null}
  {error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}
  {loading?<Text>Loading report…</Text>:null}
  {report&&detail?<>
   <Text style={s.meta}>Generated {new Date(report.generated_at).toLocaleString()}. Current statuses; financial balances as of generation time.</Text>
   <View style={s.metrics}><Metric title="Orders" value={report.metrics.orders}/><Metric title="Overdue orders" value={report.metrics.overdue}/><Metric title="Awaiting pricing" value={report.metrics.awaiting_pricing}/><Metric title="Cancelled orders" value={report.metrics.cancelled}/><Metric title="Orders with balance" value={report.metrics.orders_with_balance}/><Metric title="Average turnaround" value={report.metrics.average_turnaround_hours===null?'No samples':report.metrics.average_turnaround_hours.toFixed(2)+' hours'}/></View>
   <View style={s.panel}><Text style={s.heading}>Order value and collections</Text><Text style={s.meta}>Order value includes orders created in the date range, including cancelled orders. Paid on orders includes their full ledger to now. Collections include transactions posted in the date range, even for older orders. Currencies are reported separately; no conversion is applied.</Text>
    {report.currencies.length?report.currencies.map(c=><Financial key={c.currency} data={c}/>):<Text>No activity in this period.</Text>}
   </View>
   <View style={s.panel}><Text style={s.heading}>Store comparison</Text>{report.by_store.map(st=><View key={st.store_id} style={s.row}><Text style={s.heading}>{st.store_name}</Text><Text>{st.metrics.orders} orders · {st.metrics.overdue} overdue · {st.metrics.average_turnaround_hours===null?'No turnaround samples':st.metrics.average_turnaround_hours.toFixed(2)+' hours average turnaround'}</Text>{st.currencies.map(c=><Text key={c.currency}>{c.currency}: order value {c.order_value} · net collected {c.net_collected} · outstanding {c.outstanding}</Text>)}{options?.can_report_brand&&!dirty?<Pressable accessibilityRole="button" onPress={()=>{setStore(st.store_id);void load(query(from,to,st.store_id,status));}}><Text style={s.link}>View {st.store_name} orders</Text></Pressable>:null}</View>)}</View>
   <View style={s.panel}><Text style={s.heading}>Order details</Text><Text style={s.meta}>{detail.total} matching orders. Showing {detail.total?offset+1:0}–{Math.min(offset+25,detail.total)}. CSV contains all matching orders, up to 5,000.</Text>
    {!detail.orders.length?<Text>No orders in this period.</Text>:detail.orders.map(o=><View key={o.id} style={s.row}><Text style={s.heading}>{o.order_number} · {o.store_name}</Text><Text>{new Date(o.created_at).toLocaleDateString(undefined,{timeZone:report.timezone})} · {label(o.status)}{o.overdue?' · Overdue':''}</Text><Text>{o.currency} {o.order_value} · paid {o.paid_on_orders} · balance {o.outstanding}</Text>{o.store_id===report.active_store_id?<Pressable accessibilityRole="button" onPress={()=>router.push({pathname:'/order-detail',params:{id:o.id}})}><Text style={s.link}>Open order {o.order_number}</Text></Pressable>:<Text style={s.meta}>Select this store in the header to open the order.</Text>}</View>)}
    <View style={s.actions}><Button title="Previous page" disabled={dirty||loading||exporting||offset===0} onPress={()=>void load(applied,Math.max(0,offset-25))}/><Button title="Next page" disabled={dirty||loading||exporting||offset+25>=detail.total} onPress={()=>void load(applied,offset+25)}/></View>
   </View>
   <View style={s.panel}><Text style={s.heading}>How to read this report</Text><Text style={s.meta}>Turnaround measures creation to first ready-for-pickup event, or first completion/collection/delivery when no ready event exists. {report.metrics.turnaround_samples} orders have samples; {report.metrics.turnaround_missing} completed orders have no usable event. Overdue excludes completed, collected, delivered and cancelled orders. Estimated pricing can change order values. Missing historical currency is shown as UNSPECIFIED ({report.metrics.unspecified_currency} orders). Reports require PostgreSQL and a range of at most 366 days; narrow filters if a report exceeds its size limit.</Text></View>
  </>:null}
 </ScrollView>;
}
function Button({title,disabled,onPress}:{title:string;disabled:boolean;onPress:()=>void}){return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={[s.button,disabled&&{opacity:.45}]}><Text style={s.buttonText}>{title}</Text></Pressable>}
function Metric({title,value}:{title:string;value:string|number}){return <View style={s.metric}><Text style={s.metricValue}>{value}</Text><Text style={s.meta}>{title}</Text></View>}
function Financial({data:c}:{data:Money}){return <View style={s.row}><Text style={s.heading}>{c.currency}</Text><Text>Order value: {c.order_value} · Paid on orders: {c.paid_on_orders}</Text><Text>Outstanding: {c.outstanding} · Overpaid: {c.overpaid}</Text><Text>Payments: {c.payments} · Refunds: {c.refunds} · Adjustments: {c.adjustments} · Other: {c.other_transactions}</Text><Text style={s.heading}>Net collected: {c.net_collected}</Text>{Object.entries(c.payment_methods).map(([method,value])=><Text key={method}>{label(method)}: {value}</Text>)}</View>}
const s=themedStyles({page:{padding:20,gap:16,maxWidth:1180,width:'100%',alignSelf:'center'},panel:{flexShrink:0,backgroundColor:'#fff',borderWidth:1,borderColor:colors.border,borderRadius:16,padding:18,gap:10},title:{fontSize:30,fontWeight:'900',color:colors.ink},heading:{fontSize:17,fontWeight:'800',color:colors.ink},meta:{fontSize:13,color:colors.muted,lineHeight:20},filters:{flexDirection:'row',flexWrap:'wrap',gap:12},field:{flexGrow:1,flexBasis:210,gap:6},input:{borderWidth:1,borderColor:colors.border,borderRadius:8,padding:12,color:colors.ink},actions:{flexDirection:'row',flexWrap:'wrap',gap:12},button:{backgroundColor:colors.primary,padding:12,borderRadius:10},buttonText:{color:'#fff',fontWeight:'800'},metrics:{flexDirection:'row',flexWrap:'wrap',gap:10},metric:{flexGrow:1,flexBasis:170,backgroundColor:'#fff',borderWidth:1,borderColor:colors.border,padding:16,borderRadius:12},metricValue:{fontSize:23,fontWeight:'800',color:colors.ink},row:{borderTopWidth:1,borderTopColor:colors.border,paddingTop:14,paddingBottom:8,gap:6},link:{color:colors.primary,fontWeight:'800',paddingVertical:6},error:{color:colors.danger}});

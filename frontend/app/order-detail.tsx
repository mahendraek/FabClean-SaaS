import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Barcode, CheckCircle, Minus, Plus, Printer, Sparkle, Trash } from "phosphor-react-native";
import { api } from "@/src/api";
import { Code128 } from "@/src/Code128";
import { colors } from "@/src/theme";
import { printOrderReceipt } from "@/src/receipt";

type Service={id:string;name:string;category:string;base_price:number;unit_label:string};
type Line={service_id:string;service_name:string;quantity:number;unit_price:number;unit_label:string;modifiers:string[];notes:string;barcode_value?:string|null};
type OrderEvent={id:string;event_type:string;from_value?:string|null;to_value?:string|null;notes?:string;created_at?:string};
type Garment={id:string;garment_code:string;garment_index:number;service_name:string;last_stage:string;assembled:boolean;tag_print_count:number};
type Order={
  id:string;order_number:string;barcode_value:string;status:string;total:number;subtotal:number;
  discount:number;tax:number;payment_status:string;payment_method:string;notes:string;
  due_at?:string|null;pricing_status?:string;
  fulfillment_type?:string;service_area_name?:string;scheduled_slot_label?:string;service_address?:string;service_postal_code?:string;delivery_fee?:number;pickup_date?:string;pickup_slot_label?:string;delivery_date?:string;delivery_slot_label?:string;
  customer:{name:string;phone:string;email?:string};items:Line[];
};

const statuses=["received","inspection","cleaning","quality_check","ready_for_pickup","collected","completed"];
const pretty=(x:string)=>x.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());

export default function OrderDetail(){
  const router=useRouter();
  const params=useLocalSearchParams<{id?:string}>();
  const id=String(params.id||"");
  const [order,setOrder]=useState<Order|null>(null);
  const [services,setServices]=useState<Service[]>([]);
  const [lines,setLines]=useState<Line[]>([]);
  const [notes,setNotes]=useState("");
  const [dueAt,setDueAt]=useState("");
  const [paymentStatus,setPaymentStatus]=useState("unpaid");
  const [status,setStatus]=useState("received");
  const [pricingStatus,setPricingStatus]=useState("estimated");
  const [saving,setSaving]=useState(false);
  const [err,setErr]=useState("");
  const [ok,setOk]=useState("");
  const [events,setEvents]=useState<OrderEvent[]>([]);
  const [barcodeMode,setBarcodeMode]=useState("both");
  const [aiRisks,setAiRisks]=useState<any[]>([]);
  const [aiDraft,setAiDraft]=useState("");
  const [aiBusy,setAiBusy]=useState(false);
  const [payments,setPayments]=useState<any[]>([]);
  const [paidTotal,setPaidTotal]=useState(0);
  const [balanceDue,setBalanceDue]=useState(0);
  const [paymentAmount,setPaymentAmount]=useState("");
  const [paymentMethod,setPaymentMethod]=useState("cash");
  const [paymentRef,setPaymentRef]=useState("");
  const [paymentNotes,setPaymentNotes]=useState("");
  const [paymentBusy,setPaymentBusy]=useState(false);
  const [garments,setGarments]=useState<Garment[]>([]);

  async function load(){
    if(!id)return;
    setErr("");
    try{
      const [o,s,h,cfg,p,g]=await Promise.all([
        api.get<Order>("/orders/"+encodeURIComponent(id)),
        api.get<{services:Service[]}>("/services"),
        api.get<{events:OrderEvent[]}>("/orders/"+encodeURIComponent(id)+"/events"),
        api.get<any>("/settings"),
        api.get<any>("/orders/"+encodeURIComponent(id)+"/payments"),
        api.get<any>("/orders/"+encodeURIComponent(id)+"/garments")
      ]);
      setOrder(o);setServices(s.services);setEvents(h.events||[]);setBarcodeMode(cfg.barcode_mode||"both");setLines(o.items||[]);setNotes(o.notes||"");
      setDueAt(o.due_at||"");setPaymentStatus(o.payment_status||"unpaid");setStatus(o.status||"received");
      setPricingStatus(o.pricing_status||"estimated");setPayments(p.payments||[]);setPaidTotal(Number(p.paid_total||0));setBalanceDue(Number(p.balance_due||0));setGarments(g.garments||[]);
    }catch(e:any){setErr(e.message||"Could not load order");}
  }
  useEffect(()=>{load();},[id]);

  const total=useMemo(()=>lines.reduce((a,l)=>a+l.quantity*l.unit_price,0),[lines]);

  function addService(s:Service){
    const i=lines.findIndex(x=>x.service_id===s.id);
    if(i>=0){setLines(v=>v.map((x,j)=>j===i?{...x,quantity:x.quantity+1}:x));return;}
    setLines(v=>[...v,{service_id:s.id,service_name:s.name,quantity:1,unit_price:s.base_price,unit_label:s.unit_label||"item",modifiers:[],notes:""}]);
  }
  function adjust(i:number,d:number){setLines(v=>v.map((x,j)=>j===i?{...x,quantity:Math.max(.5,x.quantity+d)}:x));}
  function remove(i:number){setLines(v=>v.filter((_,j)=>j!==i));}

  async function save(){
    if(!order)return;
    setSaving(true);setErr("");setOk("");
    try{
      const updated=await api.put<Order>("/orders/"+order.id,{
        items:lines,notes,due_at:dueAt.trim()||null,payment_status:paymentStatus,status,
        pricing_status:pricingStatus,quick_dropoff:false,
        bag_count:0
      });
      setOrder(updated);setOk("Order updated");
      const h=await api.get<{events:OrderEvent[]}>("/orders/"+order.id+"/events");setEvents(h.events||[]);
    }catch(e:any){setErr(e.message||"Could not update order");}
    finally{setSaving(false);}
  }

  async function reviewRisks(){setAiBusy(true);setErr("");try{const x=await api.get<any>("/ai/orders/"+id+"/risks");setAiRisks(x.risks||[]);}catch(e:any){setErr(e.message||"Could not review order risks");}finally{setAiBusy(false);}}
  async function draftMessage(kind:string){setAiBusy(true);setErr("");try{const x=await api.post<any>("/ai/orders/"+id+"/communication-draft",{kind});setAiDraft(x.draft||"");}catch(e:any){setErr(e.message||"Could not draft message");}finally{setAiBusy(false);}}
  async function recordPayment(){
    if(!order)return;
    const amount=Number(paymentAmount||0);
    if(!amount){setErr("Enter a payment amount");return;}
    setPaymentBusy(true);setErr("");setOk("");
    try{
      const x=await api.post<any>("/orders/"+order.id+"/payments",{amount,payment_method:paymentMethod,reference_number:paymentRef,notes:paymentNotes});
      setPaidTotal(Number(x.paid_total||0));setBalanceDue(Number(x.balance_due||0));setPaymentAmount("");setPaymentRef("");setPaymentNotes("");setOk("Payment recorded");
      const p=await api.get<any>("/orders/"+order.id+"/payments");setPayments(p.payments||[]);
      const refreshed=await api.get<Order>("/orders/"+order.id);setOrder(refreshed);setPaymentStatus(refreshed.payment_status||"unpaid");
    }catch(e:any){setErr(e.message||"Could not record payment");}finally{setPaymentBusy(false);}
  }
  async function recordRefund(){
    if(!order)return;
    const amount=Number(paymentAmount||0);
    if(!amount){setErr("Enter a refund amount");return;}
    setPaymentBusy(true);setErr("");setOk("");
    try{
      const x=await api.post<any>("/orders/"+order.id+"/payments",{amount,transaction_type:"refund",payment_method:paymentMethod,reference_number:paymentRef,notes:paymentNotes});
      setPaidTotal(Number(x.paid_total||0));setBalanceDue(Number(x.balance_due||0));setPaymentAmount("");setPaymentRef("");setPaymentNotes("");setOk("Refund recorded");
      const p=await api.get<any>("/orders/"+order.id+"/payments");setPayments(p.payments||[]);
    }catch(e:any){setErr(e.message||"Could not record refund");}finally{setPaymentBusy(false);}
  }
  async function printReceipt(){
    if(!order)return;
    setErr("");
    try{await printOrderReceipt(order.id);}
    catch(e:any){setErr(e.message||"Could not generate receipt");}
  }
  function printLabels(){
    if(typeof window!=="undefined") window.print();
  }

  if(!order)return <View style={s.loading}><Text>{err||"Loading order…"}</Text></View>;

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/orders")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Orders</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View>
    </View>

    <View style={s.header}>
      <View>
        <Text style={s.kicker}>ORDER</Text>
        <Text style={s.title}>{order.order_number}</Text>
        <Text style={s.sub}>{order.customer.name} · {order.customer.phone} · {order.barcode_value}</Text>
      </View>
      <View style={s.headerActions}>
        <Pressable style={s.printBtn} onPress={()=>router.push({pathname:"/inspection",params:{id:order.id}})}><Text style={s.printText}>Inspection</Text></Pressable><Pressable style={s.printBtn} onPress={()=>router.push({pathname:"/garment-tags",params:{id:order.id}})}><Printer size={17} color="#fff"/><Text style={s.printText}>Garment Tags</Text></Pressable><Pressable style={s.printBtn} onPress={()=>router.push({pathname:"/garment-assembly",params:{id:order.id}})}><Barcode size={17} color="#fff"/><Text style={s.printText}>Assembly</Text></Pressable>
        <View style={s.headerMetric}><Text style={s.metricLabel}>Current total</Text><Text style={s.metricValue}>{"$"+total.toFixed(2)}</Text></View>
      </View>
    </View>

    {order.fulfillment_type&&order.fulfillment_type!=="walk_in"?<View style={s.panel}><Text style={s.panelTitle}>Pickup / Delivery</Text><Text style={s.meta}>Pickup: {order.fulfillment_type==="delivery_only"?"Walk-In":(order.pickup_date||"—")+(order.pickup_slot_label?" · "+order.pickup_slot_label:"")}</Text><Text style={s.meta}>Delivery: {order.fulfillment_type==="pickup_only"?"Walk-In":(order.delivery_date||"—")+(order.delivery_slot_label?" · "+order.delivery_slot_label:"")}</Text><Pressable onPress={()=>router.push("/pickup-schedule")}><Text style={s.aiLink}>Open Schedule</Text></Pressable></View>:null}

    <View style={s.panel}>
      <Text style={s.panelTitle}>Order lifecycle</Text>
      <View style={s.timeline}>{statuses.map((x,i)=>{
        const currentIndex=statuses.indexOf(order.status);
        const done=i<currentIndex, current=i===currentIndex;
        return <View key={x} style={s.timelineStep}><View style={[s.timelineDot,done&&s.timelineDone,current&&s.timelineCurrent]}>{done?<CheckCircle size={15} color="#fff"/>:<Text style={[s.timelineNum,(done||current)&&{color:"#fff"}]}>{i+1}</Text>}</View><Text style={[s.timelineText,current&&s.timelineTextCurrent]}>{pretty(x)}</Text></View>
      })}</View>
    </View>

    <View style={s.panel}>
      <View style={s.aiHead}><Text style={s.panelTitle}>AI assistance</Text><Pressable onPress={reviewRisks}><Text style={s.aiLink}>{aiBusy?"Working…":"Review risks"}</Text></Pressable></View>
      {aiRisks.length?<View style={s.aiRiskList}>{aiRisks.map((r:any,i:number)=><View key={i} style={s.aiRisk}><Text style={s.aiRiskTitle}>{pretty(r.type||"risk")} · {r.severity}</Text><Text style={s.meta}>{r.message}</Text></View>)}</View>:<Text style={s.meta}>Run a quick risk review for due dates, discounts and repeated inspection activity.</Text>}
      <View style={s.aiActions}><Pressable onPress={()=>draftMessage("ready")}><Text style={s.aiLink}>Draft ready message</Text></Pressable><Pressable onPress={()=>draftMessage("delay")}><Text style={s.aiLink}>Draft delay message</Text></Pressable></View>
      {aiDraft?<View style={s.aiDraft}><Text style={s.aiDraftText}>{aiDraft}</Text><Text style={s.aiNote}>Draft only · Staff must review and send manually.</Text></View>:null}
    </View>

    <View style={s.grid}>
      <View style={s.main}>
        <View style={s.panel}>
          <Text style={s.panelTitle}>Services & itemization</Text>
          <View style={s.serviceGrid}>{services.map(x=><Pressable key={x.id} onPress={()=>addService(x)} style={s.serviceBtn}><Text style={s.serviceCat}>{x.category}</Text><Text style={s.serviceName}>{x.name}</Text><Text style={s.servicePrice}>{"$"+x.base_price.toFixed(2)+" / "+(x.unit_label||"item")}</Text><Text style={s.addText}>+ Add</Text></Pressable>)}</View>
          <View style={s.lines}>
            {lines.length===0?<Text style={s.empty}>No services itemized yet.</Text>:lines.map((l,i)=><View key={l.service_id+"-"+i} style={s.line}>
              <View style={{flex:1}}><Text style={s.lineName}>{l.service_name}</Text><Text style={s.meta}>{"$"+l.unit_price.toFixed(2)+" / "+l.unit_label}</Text>{l.barcode_value?<View style={s.barcodeRow}><Code128 value={l.barcode_value} height={36} moduleWidth={1.2}/></View>:null}</View>
              <View style={s.qty}><Pressable onPress={()=>adjust(i,-1)} style={s.iconBtn}><Minus size={15} color={colors.ink}/></Pressable><Text style={s.qtyText}>{l.quantity}</Text><Pressable onPress={()=>adjust(i,1)} style={s.iconBtn}><Plus size={15} color={colors.ink}/></Pressable><Pressable onPress={()=>remove(i)}><Trash size={17} color={colors.danger}/></Pressable></View>
            </View>)}
          </View>
        </View>

        <View style={s.panel}>
          <View style={s.garmentHead}><View><Text style={s.panelTitle}>Garment tracking</Text><Text style={s.meta}>{garments.length} physical garment tag(s) · {garments.filter(g=>g.assembled).length} assembled</Text></View><Pressable onPress={()=>router.push({pathname:"/garment-assembly",params:{id:order.id}})}><Text style={s.aiLink}>Open Assembly</Text></Pressable></View>
          {garments.length?<View style={s.garmentGrid}>{garments.map(g=><View key={g.id} style={[s.garmentCard,g.assembled&&s.garmentDone]}><Text style={s.garmentCode}>{g.garment_code}</Text><Text style={s.meta}>{g.service_name}</Text><Text style={s.garmentStage}>{pretty(g.last_stage)}</Text></View>)}</View>:<Text style={s.meta}>Garment tags will be generated from itemized services.</Text>}
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>Order barcode & label data</Text>
          <Text style={s.meta}>Barcode mode: {pretty(barcodeMode)}</Text>
          {barcodeMode!=="item_only"?<View style={s.labelCard}><Text style={s.labelOrder}>{order.order_number}</Text><Text style={s.labelCustomer}>{order.customer.name}</Text><Text style={s.labelMeta}>Due: {order.due_at||"Not set"}</Text><View style={s.barcodeBig}><Code128 value={order.barcode_value} height={58} moduleWidth={2}/></View></View>:null}
          {barcodeMode!=="order_only"&&lines.length?<View style={s.itemLabels}>{lines.map((l,i)=><View key={(l.barcode_value||l.service_id)+"-label"} style={s.itemLabel}><Text style={s.itemLabelTitle}>{l.service_name}</Text><Text style={s.labelMeta}>Qty: {l.quantity} · {order.customer.name}</Text>{l.barcode_value?<View style={s.barcodeRow}><Code128 value={l.barcode_value} height={42} moduleWidth={1.5}/></View>:null}</View>)}</View>:null}
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>Audit trail</Text>
          {events.length===0?<Text style={s.empty}>No history events recorded yet.</Text>:events.map(e=><View key={e.id} style={s.eventRow}><View style={s.eventDot}/><View style={{flex:1}}><Text style={s.eventTitle}>{pretty(e.event_type)}</Text><Text style={s.meta}>{e.from_value||"—"}{e.to_value?" → "+e.to_value:""}{e.notes?" · "+e.notes:""}</Text><Text style={s.eventTime}>{e.created_at?new Date(e.created_at).toLocaleString():""}</Text></View></View>)}
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>Notes & due date</Text>
          <TextInput style={s.notes} multiline value={notes} onChangeText={setNotes} placeholder="Inspection notes, stains, damage, handling instructions…"/>
          <Text style={s.label}>Due date / time</Text>
          <TextInput style={s.input} value={dueAt} onChangeText={setDueAt} placeholder="2026-10-07T17:00:00+05:30" autoCapitalize="none"/>
        </View>
      </View>

      <View style={s.side}>
        <View style={s.panel}>
          <Text style={s.panelTitle}>Payments & receipt</Text>
          <View style={s.paymentSummary}><View><Text style={s.metricLabel}>Paid</Text><Text style={s.paymentValue}>{"$"+paidTotal.toFixed(2)}</Text></View><View><Text style={s.metricLabel}>Balance</Text><Text style={s.paymentValue}>{"$"+balanceDue.toFixed(2)}</Text></View></View>
          <Text style={s.label}>Amount</Text><TextInput style={s.input} keyboardType="decimal-pad" value={paymentAmount} onChangeText={setPaymentAmount} placeholder="0.00"/>
          <Text style={s.label}>Method</Text><View style={s.chips}>{["cash","card","other"].map(x=><Pressable key={x} onPress={()=>setPaymentMethod(x)} style={[s.chip,paymentMethod===x&&s.chipOn]}><Text style={[s.chipText,paymentMethod===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View>
          <Text style={s.label}>Reference</Text><TextInput style={s.input} value={paymentRef} onChangeText={setPaymentRef} placeholder="Optional reference"/>
          <Text style={s.label}>Notes</Text><TextInput style={s.input} value={paymentNotes} onChangeText={setPaymentNotes} placeholder="Optional payment note"/>
          <View style={s.payActions}><Pressable disabled={paymentBusy} onPress={recordPayment} style={s.payBtn}><Text style={s.payBtnText}>{paymentBusy?"Saving…":"Record Payment"}</Text></Pressable><Pressable disabled={paymentBusy} onPress={recordRefund} style={s.refundBtn}><Text style={s.refundBtnText}>Refund</Text></Pressable></View>
          <Pressable onPress={printReceipt} style={s.receiptBtn}><Printer size={16} color={colors.primary}/><Text style={s.receiptText}>Print Receipt</Text></Pressable>
          {payments.length?<View style={{marginTop:12}}>{payments.map((p:any)=><View key={p.id} style={s.paymentRow}><View style={{flex:1}}><Text style={s.rowStrong}>{pretty(p.transaction_type)} · {pretty(p.payment_method)}</Text><Text style={s.meta}>{p.receipt_number} · {p.staff_name||"Staff"}{p.reference_number?" · "+p.reference_number:""}</Text></View><Text style={s.amount}>{Number(p.amount||0)<0?"-$"+Math.abs(Number(p.amount||0)).toFixed(2):"$"+Number(p.amount||0).toFixed(2)}</Text></View>)}</View>:<Text style={s.meta}>No payment transactions yet.</Text>}
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>Finalize order</Text>
          <Text style={s.label}>Pricing</Text>
          <View style={s.chips}>{["estimated","final"].map(x=><Pressable key={x} onPress={()=>setPricingStatus(x)} style={[s.chip,pricingStatus===x&&s.chipOn]}><Text style={[s.chipText,pricingStatus===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View>
          <Text style={s.label}>Payment</Text>
          <View style={s.chips}>{["unpaid","partial","paid"].map(x=><Pressable key={x} onPress={()=>setPaymentStatus(x)} style={[s.chip,paymentStatus===x&&s.chipOn]}><Text style={[s.chipText,paymentStatus===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View>
          <Text style={s.label}>Status</Text>
          <View style={s.statusList}>{statuses.map(x=><Pressable key={x} onPress={()=>setStatus(x)} style={[s.statusBtn,status===x&&s.statusBtnOn]}><Text style={[s.statusText,status===x&&s.statusTextOn]}>{pretty(x)}</Text></Pressable>)}</View>
          <View style={s.total}><Text style={s.totalLabel}>{pricingStatus==="final"?"Final total":"Estimated total"}</Text><Text style={s.totalValue}>{"$"+total.toFixed(2)}</Text></View>
          {err?<Text style={s.err}>{err}</Text>:null}{ok?<View style={s.okRow}><CheckCircle size={16} color={colors.success}/><Text style={s.ok}>{ok}</Text></View>:null}
          <Pressable onPress={save} disabled={saving||pricingStatus==="final"&&!lines.length} style={[s.saveBtn,(saving||pricingStatus==="final"&&!lines.length)&&{opacity:.45}]}><Text style={s.saveText}>{saving?"Saving…":"Save Order Changes"}</Text></Pressable>
          {pricingStatus==="final"&&!lines.length?<Text style={s.help}>Add at least one service before finalizing pricing.</Text>:null}
        </View>
      </View>
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  loading:{padding:30},page:{padding:20,maxWidth:1180,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"},headerActions:{flexDirection:"row",gap:10,alignItems:"center",justifyContent:"flex-end",flexWrap:"wrap",flexShrink:1},printBtn:{backgroundColor:colors.ink,borderRadius:11,minHeight:42,paddingHorizontal:13,paddingVertical:10,flexDirection:"row",gap:7,alignItems:"center",justifyContent:"center"},printText:{color:"#fff",fontWeight:"900"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5},headerMetric:{alignItems:"flex-end"},metricLabel:{fontSize:10,fontWeight:"900",color:colors.muted,textTransform:"uppercase"},metricValue:{fontSize:28,fontWeight:"900",color:colors.primary,marginTop:3},
  aiHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:12},aiLink:{fontWeight:"900",color:colors.primary},aiRiskList:{gap:8},aiRisk:{backgroundColor:colors.softGold,borderRadius:11,padding:10},aiRiskTitle:{fontWeight:"900",color:colors.ink},aiActions:{flexDirection:"row",gap:14,flexWrap:"wrap",marginTop:10},aiDraft:{backgroundColor:colors.primarySoft,borderRadius:12,padding:12,marginTop:10},aiDraftText:{fontSize:13,lineHeight:20,color:colors.ink},aiNote:{fontSize:11,color:colors.muted,marginTop:6,fontStyle:"italic"},timeline:{flexDirection:"row",flexWrap:"wrap",gap:10},timelineStep:{flexDirection:"row",alignItems:"center",gap:7,minWidth:135},timelineDot:{width:28,height:28,borderRadius:14,borderWidth:1,borderColor:colors.border,alignItems:"center",justifyContent:"center",backgroundColor:"#fff"},timelineDone:{backgroundColor:colors.success,borderColor:colors.success},timelineCurrent:{backgroundColor:colors.primary,borderColor:colors.primary},timelineNum:{fontSize:11,fontWeight:"900",color:colors.muted},timelineText:{fontSize:12,fontWeight:"800",color:colors.muted},timelineTextCurrent:{color:colors.primaryDark},grid:{flexDirection:"row",gap:16,alignItems:"flex-start",flexWrap:"wrap"},main:{flex:1,minWidth:300,gap:16},side:{width:330,maxWidth:"100%",flexShrink:1},panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,padding:18},panelTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginBottom:12},
  serviceGrid:{flexDirection:"row",gap:8,flexWrap:"wrap"},serviceBtn:{width:190,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:11,backgroundColor:colors.soft},serviceCat:{fontSize:9,fontWeight:"900",color:colors.primary,textTransform:"uppercase"},serviceName:{fontWeight:"900",color:colors.ink,marginTop:2},servicePrice:{fontSize:12,color:colors.muted,marginTop:3},addText:{fontWeight:"900",color:colors.primary,marginTop:6},
  lines:{marginTop:14},line:{paddingVertical:10,borderTopWidth:1,borderTopColor:colors.border,flexDirection:"row",alignItems:"center",gap:10},lineName:{fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:2},barcodeRow:{flexDirection:"row",alignItems:"center",gap:5,marginTop:5},barcodeText:{fontSize:11,fontWeight:"800",color:colors.primary},qty:{flexDirection:"row",alignItems:"center",gap:7},iconBtn:{width:29,height:29,borderRadius:8,borderWidth:1,borderColor:colors.border,alignItems:"center",justifyContent:"center"},qtyText:{minWidth:24,textAlign:"center",fontWeight:"900",color:colors.ink},empty:{color:colors.muted,paddingVertical:10},
  garmentHead:{flexDirection:"row",justifyContent:"space-between",gap:10,alignItems:"flex-start",flexWrap:"wrap"},garmentGrid:{flexDirection:"row",gap:8,flexWrap:"wrap"},garmentCard:{minWidth:150,flexGrow:1,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:10,backgroundColor:colors.soft},garmentDone:{backgroundColor:colors.primarySoft,borderColor:"#B8DED7"},garmentCode:{fontSize:14,fontWeight:"900",color:colors.ink},garmentStage:{fontSize:10,fontWeight:"900",color:colors.primary,textTransform:"uppercase",marginTop:5},labelCard:{borderWidth:1,borderColor:colors.border,borderRadius:14,padding:16,backgroundColor:colors.soft,marginTop:10},itemLabels:{gap:8,marginTop:10},itemLabel:{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,backgroundColor:"#fff"},itemLabelTitle:{fontWeight:"900",color:colors.ink},labelOrder:{fontSize:22,fontWeight:"900",color:colors.ink},labelCustomer:{fontSize:16,fontWeight:"800",color:colors.ink,marginTop:4},labelMeta:{fontSize:12,color:colors.muted,marginTop:3},barcodeBig:{flexDirection:"row",alignItems:"center",gap:10,marginTop:12,paddingTop:10,borderTopWidth:1,borderTopColor:colors.border},barcodeBigText:{fontSize:18,fontWeight:"900",letterSpacing:1.2,color:colors.ink},eventRow:{flexDirection:"row",gap:10,paddingVertical:10,borderTopWidth:1,borderTopColor:colors.border},eventDot:{width:9,height:9,borderRadius:5,backgroundColor:colors.primary,marginTop:6},eventTitle:{fontWeight:"900",color:colors.ink},eventTime:{fontSize:11,color:colors.muted,marginTop:3},notes:{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,minHeight:100,textAlignVertical:"top"},label:{fontSize:10,fontWeight:"900",letterSpacing:.8,color:colors.muted,textTransform:"uppercase",marginTop:12,marginBottom:6},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11},
  chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:10,paddingVertical:8},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},statusList:{gap:6},statusBtn:{padding:9,borderRadius:9,backgroundColor:colors.soft,borderWidth:1,borderColor:colors.border},statusBtnOn:{backgroundColor:colors.primarySoft,borderColor:"#B8DED7"},statusText:{fontWeight:"800",fontSize:12,color:colors.muted},statusTextOn:{color:colors.primaryDark},
  amount:{fontSize:16,fontWeight:"900",color:colors.ink},
  paymentSummary:{flexDirection:"row",justifyContent:"space-between",gap:12,backgroundColor:colors.soft,borderRadius:12,padding:12},paymentValue:{fontSize:22,fontWeight:"900",color:colors.ink,marginTop:3},payActions:{flexDirection:"row",gap:8,marginTop:12},payBtn:{backgroundColor:colors.primary,borderRadius:10,paddingHorizontal:14,paddingVertical:11},payBtnText:{color:"#fff",fontWeight:"900"},refundBtn:{borderWidth:1,borderColor:colors.danger,borderRadius:10,paddingHorizontal:14,paddingVertical:11},refundBtnText:{color:colors.danger,fontWeight:"900"},receiptBtn:{marginTop:10,flexDirection:"row",gap:7,alignItems:"center"},receiptText:{fontWeight:"900",color:colors.primary},paymentRow:{flexDirection:"row",gap:10,alignItems:"center",paddingVertical:8,borderTopWidth:1,borderTopColor:colors.border},rowStrong:{fontWeight:"900",color:colors.ink},total:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",paddingVertical:16,marginTop:8},totalLabel:{fontWeight:"800",color:colors.ink},totalValue:{fontSize:24,fontWeight:"900",color:colors.primary},dropInfo:{backgroundColor:colors.softGold,borderRadius:10,padding:10,color:colors.ink,fontSize:12},saveBtn:{backgroundColor:colors.primary,borderRadius:12,padding:14,alignItems:"center",marginTop:14},saveText:{color:"#fff",fontWeight:"900"},err:{color:colors.danger,marginTop:10},okRow:{flexDirection:"row",alignItems:"center",gap:6,marginTop:10},ok:{color:colors.success,fontWeight:"800"},help:{fontSize:12,color:colors.muted,marginTop:7}
});

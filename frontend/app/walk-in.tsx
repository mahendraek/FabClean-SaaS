import { useEffect, useMemo, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, CheckCircle, Minus, Plus, Sparkle, Trash } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";
import { imageForCategory } from "@/src/service-media";
import { downloadRaw, generateTspl, generateZpl, openLabelPrint, profileFromSettings } from "@/src/hardware";
import { printOrderReceipt } from "@/src/receipt";
import { Code128 } from "@/src/Code128";
import { CalendarDatePicker } from "@/src/CalendarDatePicker";

type Service={id:string;name:string;category:string;base_price:number;unit_label:string;description?:string};
type Customer={id:string;name:string;phone:string;email?:string;order_count?:number;lifetime_value?:number;reward_points?:number;referral_code?:string};
type Line={service_id:string;service_name:string;quantity:number;unit_price:number;unit_label:string;modifiers:string[];notes:string};
type Slot={id:string;name:string;day_of_week:number;start_time:string;end_time:string;capacity:number;pickup_enabled:boolean;delivery_enabled:boolean};

function isoDate(offset=0){
  const d=new Date();d.setDate(d.getDate()+offset);
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");
  return y+"-"+m+"-"+day;
}
function addDays(value:string,days:number){
  if(!value)return isoDate(days);
  const d=new Date(value+"T12:00:00");d.setDate(d.getDate()+days);
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");
  return y+"-"+m+"-"+day;
}
export default function WalkIn(){
  const router=useRouter();
  const params=useLocalSearchParams<{customerId?:string}>();
  const [services,setServices]=useState<Service[]>([]);
  const [lines,setLines]=useState<Line[]>([]);
  const [name,setName]=useState("");
  const [phone,setPhone]=useState("");
  const [customerQuery,setCustomerQuery]=useState("");
  const [customerResults,setCustomerResults]=useState<Customer[]>([]);
  const [selectedCustomer,setSelectedCustomer]=useState<Customer|null>(null);
  const [searchingCustomer,setSearchingCustomer]=useState(false);
  const [email,setEmail]=useState("");
  const [notes,setNotes]=useState("");
  const [paymentStatus,setPaymentStatus]=useState("unpaid");
  const [dueAt,setDueAt]=useState("");
  const [category,setCategory]=useState("All");
  const [created,setCreated]=useState<any>(null);
  const [saving,setSaving]=useState(false);
  const [err,setErr]=useState("");
  const [fulfillmentType,setFulfillmentType]=useState("walk_in");
  const [slots,setSlots]=useState<Slot[]>([]);
  const [pickupDate,setPickupDate]=useState("");
  const [pickupSlotId,setPickupSlotId]=useState("");
  const [deliveryDate,setDeliveryDate]=useState("");
  const [deliverySlotId,setDeliverySlotId]=useState("");
  const [promoCode,setPromoCode]=useState("");
  const [promoDiscount,setPromoDiscount]=useState(0);
  const [promoMessage,setPromoMessage]=useState("");
  const [successSettings,setSuccessSettings]=useState<any>({});
  const [capabilities,setCapabilities]=useState<any>({pickup_enabled:false,delivery_enabled:false,offers_enabled:true});
  const [successGarments,setSuccessGarments]=useState<any[]>([]);

  useEffect(()=>{
    Promise.all([
      api.get<{services:Service[]}>("/services"),
      api.get<{slots:Slot[];pickup_enabled?:boolean;delivery_enabled?:boolean}>("/scheduling/availability"),
      api.get<any>("/settings")
    ]).then(([svc,sched,cfg])=>{
      setServices(svc.services);setSlots(sched.slots||[]);
      setCapabilities({
        pickup_enabled:cfg.pickup_enabled??sched.pickup_enabled??false,
        delivery_enabled:cfg.delivery_enabled??sched.delivery_enabled??false,
        offers_enabled:cfg.offers_enabled!==false
      });
    }).catch(()=>{});
  },[]);
  useEffect(()=>{
    const customerId=String(params.customerId||"");
    if(!customerId)return;
    api.get<Customer>("/customers/"+encodeURIComponent(customerId)).then(selectCustomer).catch(()=>{});
  },[params.customerId]);
  const total=useMemo(()=>lines.reduce((a,l)=>a+l.quantity*l.unit_price,0),[lines]);
  const categories=useMemo(()=>["All",...Array.from(new Set(services.map(x=>x.category)))],[services]);
  const visible=category==="All"?services:services.filter(x=>x.category===category);
  const dateDay=(value:string)=>value?new Date(value+"T12:00:00").getDay():null;
  const pickupSlots=slots.filter(x=>x.pickup_enabled&&(dateDay(pickupDate)===null||x.day_of_week===dateDay(pickupDate)));
  const deliverySlots=slots.filter(x=>x.delivery_enabled&&(dateDay(deliveryDate)===null||x.day_of_week===dateDay(deliveryDate)));
  const selectedPickupSlot=slots.find(x=>x.id===pickupSlotId)||null;
  const selectedDeliverySlot=slots.find(x=>x.id===deliverySlotId)||null;
  const needsPickup=fulfillmentType==="pickup_and_delivery"||fulfillmentType==="pickup_only";
  const needsDelivery=fulfillmentType==="pickup_and_delivery"||fulfillmentType==="delivery_only";
  const fulfillmentOptions=[
    ["walk_in","Walk-In","Customer drops off and collects at the store."],
    ...(capabilities.pickup_enabled&&capabilities.delivery_enabled?[["pickup_and_delivery","Pickup & Delivery","Schedule both pickup and return delivery."]]:[]),
    ...(capabilities.pickup_enabled?[["pickup_only","Pickup Only","Schedule pickup; customer collects from the store."]]:[]),
    ...(capabilities.delivery_enabled?[["delivery_only","Delivery Only","Customer drops off at the store; schedule return delivery."]]:[])
  ] as string[][];
  useEffect(()=>{
    const allowed=fulfillmentOptions.some(x=>x[0]===fulfillmentType);
    if(!allowed){setFulfillmentType("walk_in");setPickupDate("");setPickupSlotId("");setDeliveryDate("");setDeliverySlotId("");}
  },[capabilities.pickup_enabled,capabilities.delivery_enabled]);
  const deliveryFee=0;
  const orderTotal=Math.max(0,total-promoDiscount);
  useEffect(()=>{setPromoDiscount(0);setPromoMessage("");},[total,selectedCustomer?.id]);
  useEffect(()=>{
    if(!created?.id){setSuccessSettings({});setSuccessGarments([]);return;}
    Promise.all([
      api.get<any>("/settings"),
      api.get<any>("/orders/"+encodeURIComponent(created.id)+"/garments")
    ]).then(([cfg,g])=>{setSuccessSettings(cfg||{});setSuccessGarments(g.garments||[]);}).catch(()=>{});
  },[created?.id]);

  async function searchCustomers(){
    const raw=customerQuery.trim();
    if(!raw){setCustomerResults([]);return;}
    setSearchingCustomer(true);setErr("");
    try{
      const customerId=raw.toUpperCase().startsWith("CUSTOMER:")?raw.slice("CUSTOMER:".length).trim():raw;
      if(raw.toUpperCase().startsWith("CUSTOMER:")||/^[0-9a-f]{8}-[0-9a-f-]{20,}$/i.test(customerId)){
        try{
          const customer=await api.get<Customer>("/customers/"+encodeURIComponent(customerId));
          selectCustomer(customer);return;
        }catch{
          if(raw.toUpperCase().startsWith("CUSTOMER:"))throw new Error("Customer barcode was not found");
        }
      }
      const x=await api.get<{customers:Customer[]}>("/customers?q="+encodeURIComponent(raw));
      setCustomerResults(x.customers);
      if(!x.customers.length)setErr("No customer found. Enter the details below to create a new customer with this order.");
    }catch(e:any){setErr(e.message||"Could not search customers");}
    finally{setSearchingCustomer(false);}
  }
  function selectCustomer(customer:Customer){
    setSelectedCustomer(customer);
    setName(customer.name);
    setPhone(customer.phone);
    setEmail(customer.email||"");
    setCustomerResults([]);
    setCustomerQuery("");
  }
  function clearCustomer(){
    setSelectedCustomer(null);
    setName("");setPhone("");setEmail("");
  }

  function add(x:Service){
    const found=lines.findIndex(l=>l.service_id===x.id);
    if(found>=0){adjust(found,1);return;}
    setLines(v=>[...v,{service_id:x.id,service_name:x.name,quantity:1,unit_price:x.base_price,unit_label:x.unit_label||"item",modifiers:[],notes:""}]);
  }
  function adjust(index:number,delta:number){setLines(v=>v.map((l,i)=>i===index?{...l,quantity:Math.max(.5,l.quantity+delta)}:l));}
  function remove(index:number){setLines(v=>v.filter((_,i)=>i!==index));}

  async function applyPromo(){
    const code=promoCode.trim();
    if(!code){setPromoDiscount(0);setPromoMessage("");return;}
    setErr("");setPromoMessage("");
    try{
      const result=await api.post<{discount:number;offer:any}>("/offers/validate",{code,subtotal:total,customer_id:selectedCustomer?.id||null});
      setPromoDiscount(Number(result.discount||0));
      setPromoMessage("Applied "+(result.offer?.name||code));
    }catch(e:any){setPromoDiscount(0);setPromoMessage("");setErr(e.message||"Promo code is not valid");}
  }

  async function save(){
    setSaving(true);setErr("");
    try{
      const o=await api.post<any>("/orders",{
        customer_id:selectedCustomer?.id||null,customer_name:name.trim(),customer_phone:phone.trim(),customer_email:email.trim(),
        fulfillment_type:fulfillmentType,items:lines,notes,discount:promoDiscount,tax:0,payment_method:"cash",payment_status:paymentStatus,
        quick_dropoff:false,bag_count:0,due_at:dueAt.trim()||null,pricing_status:"estimated",
        service_area_id:null,service_area_name:"",
        scheduled_slot_id:fulfillmentType==="walk_in"?null:(needsPickup?pickupSlotId:deliverySlotId)||null,
        scheduled_slot_label:fulfillmentType==="walk_in"?"":(needsPickup&&selectedPickupSlot?selectedPickupSlot.name+" · "+selectedPickupSlot.start_time+"-"+selectedPickupSlot.end_time:selectedDeliverySlot?selectedDeliverySlot.name+" · "+selectedDeliverySlot.start_time+"-"+selectedDeliverySlot.end_time:""),
        pickup_date:needsPickup?pickupDate:"",
        pickup_slot_id:needsPickup?pickupSlotId||null:null,
        pickup_slot_label:needsPickup&&selectedPickupSlot?selectedPickupSlot.name+" · "+selectedPickupSlot.start_time+"-"+selectedPickupSlot.end_time:"",
        delivery_date:needsDelivery?deliveryDate:"",
        delivery_slot_id:needsDelivery?deliverySlotId||null:null,
        delivery_slot_label:needsDelivery&&selectedDeliverySlot?selectedDeliverySlot.name+" · "+selectedDeliverySlot.start_time+"-"+selectedDeliverySlot.end_time:"",
        service_address:"",service_postal_code:"",delivery_fee:0,
        promo_code:promoCode.trim().toUpperCase()
      });
      setCreated(o);
    }catch(e:any){setErr(e.message||"Could not create order");}
    finally{setSaving(false);}
  }

  async function printCreatedTags(kind:"order"|"garments"){
    if(!created)return;
    setErr("");
    try{
      const cfg=await api.get<any>("/settings");
      const hardware=profileFromSettings(cfg);
      if(kind==="order"){
        const tag={id:"order",garment_code:created.barcode_value||created.order_number.replace("-",""),garment_index:1,service_name:created.customer.name,last_stage:"tagged",assembled:false,tag_print_count:0};
        if(hardware.printer_mode==="zpl")downloadRaw(created.order_number+"-order-tag.zpl",generateZpl(created,[tag],hardware));
        else if(hardware.printer_mode==="tspl")downloadRaw(created.order_number+"-order-tag.tspl",generateTspl(created,[tag],hardware));
        else openLabelPrint(created.order_number+" order tag",[{code:tag.garment_code,order:created.order_number,line1:created.customer.name,line2:"ORDER TAG"}],hardware);
        return;
      }
      const result=await api.get<any>("/orders/"+encodeURIComponent(created.id)+"/garments");
      const garments=result.garments||[];
      if(!garments.length)throw new Error("No garment tags were generated for this order");
      if(hardware.printer_mode==="zpl")downloadRaw(created.order_number+"-garment-tags.zpl",generateZpl(created,garments,hardware));
      else if(hardware.printer_mode==="tspl")downloadRaw(created.order_number+"-garment-tags.tspl",generateTspl(created,garments,hardware));
      else openLabelPrint(created.order_number+" garment tags",garments.map((g:any)=>({code:g.garment_code,order:created.order_number,line1:g.service_name,line2:"Item "+g.garment_index+" / "+garments.length})),hardware);
      await Promise.all(garments.map((g:any)=>api.post("/orders/"+created.id+"/garments/"+encodeURIComponent(g.garment_code)+"/reprint",{})));
    }catch(e:any){setErr(e.message||"Could not print tags");}
  }

  async function printReceipt(){
    if(!created)return;
    setErr("");
    try{await printOrderReceipt(created.id);}
    catch(e:any){setErr(e.message||"Could not print receipt");}
  }

  if(created)return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.successCard}>
      <View style={s.successIcon}><CheckCircle size={34} color="#fff" weight="fill"/></View>
      <Text style={s.successTitle}>Order created successfully</Text>

      <View style={s.receiptCard}>
        <View style={s.receiptHeader}>
          <Text style={s.receiptBusiness}>{successSettings.business_name||"FabClean"}</Text>
          {successSettings.business_address?<Text style={s.receiptHeaderText}>{successSettings.business_address}</Text>:null}
          {successSettings.business_phone?<Text style={s.receiptHeaderText}>Phone: {successSettings.business_phone}</Text>:null}
        </View>

        <View style={s.orderBarcodeBox}>
          <Text style={s.codeLabel}>ORDER BARCODE</Text>
          <View style={s.barcodeVisual}><Code128 value={created.barcode_value||created.order_number.replace("-","")} height={58} moduleWidth={1.5}/></View>
          <Text style={s.code}>{created.order_number}</Text>
          <Text style={s.barcodeValue}>{created.barcode_value}</Text>
        </View>

        <View style={s.receiptTwoCol}>
          <View style={s.receiptSection}>
            <Text style={s.receiptLabel}>CUSTOMER</Text>
            <Text style={s.receiptStrong}>{created.customer.name}</Text>
            <Text style={s.receiptText}>{created.customer.phone}</Text>
            {created.customer.email?<Text style={s.receiptText}>{created.customer.email}</Text>:null}
          </View>
          <View style={s.receiptSection}>
            <Text style={s.receiptLabel}>ORDER DETAILS</Text>
            <Text style={s.receiptText}>Order: {created.order_number}</Text>
            <Text style={s.receiptText}>Status: {String(created.status||"received").replaceAll("_"," ")}</Text>
            <Text style={s.receiptText}>Payment: {String(created.payment_status||"unpaid").replaceAll("_"," ")}</Text>
            <Text style={s.receiptText}>Fulfillment: {String(created.fulfillment_type||"walk_in").replaceAll("_"," ")}</Text>
            {created.due_at?<Text style={s.receiptText}>Due: {created.due_at}</Text>:null}
          </View>
        </View>

        {created.fulfillment_type!=="walk_in"?<View style={s.receiptSectionFull}>
          <Text style={s.receiptLabel}>PICKUP & DELIVERY</Text>
          <Text style={s.receiptText}>Pickup: {created.fulfillment_type==="delivery_only"?"Walk-In":(created.pickup_date||"—")+(created.pickup_slot_label?" · "+created.pickup_slot_label:"")}</Text>
          <Text style={s.receiptText}>Delivery: {created.fulfillment_type==="pickup_only"?"Walk-In":(created.delivery_date||"—")+(created.delivery_slot_label?" · "+created.delivery_slot_label:"")}</Text>
        </View>:null}

        <View style={s.receiptSectionFull}>
          <Text style={s.receiptLabel}>DETAILED INVENTORY</Text>
          <View style={s.receiptTableHead}><Text style={[s.receiptColItem,s.receiptTableHeadText]}>Item / Service</Text><Text style={[s.receiptColQty,s.receiptTableHeadText]}>Qty</Text><Text style={[s.receiptColMoney,s.receiptTableHeadText]}>Price</Text><Text style={[s.receiptColMoney,s.receiptTableHeadText]}>Amount</Text></View>
          {(created.items||[]).map((item:any,index:number)=><View style={s.receiptRow} key={(item.barcode_value||item.service_id)+"-"+index}>
            <View style={s.receiptColItem}><Text style={s.receiptStrong}>{item.service_name}</Text><Text style={s.receiptTiny}>{item.unit_label||"item"}{item.notes?" · "+item.notes:""}</Text></View>
            <Text style={s.receiptColQty}>{item.quantity}</Text>
            <Text style={s.receiptColMoney}>{"$"+Number(item.unit_price||0).toFixed(2)}</Text>
            <Text style={s.receiptColMoney}>{"$"+(Number(item.unit_price||0)*Number(item.quantity||0)).toFixed(2)}</Text>
          </View>)}
        </View>

        <View style={s.receiptTotals}>
          <View style={s.receiptTotalRow}><Text style={s.receiptText}>Subtotal</Text><Text style={s.receiptStrong}>{"$"+Number(created.subtotal||0).toFixed(2)}</Text></View>
          {Number(created.discount||0)>0?<View style={s.receiptTotalRow}><Text style={s.receiptText}>Discount</Text><Text style={s.receiptStrong}>{"-$"+Number(created.discount||0).toFixed(2)}</Text></View>:null}
          {Number(created.tax||0)>0?<View style={s.receiptTotalRow}><Text style={s.receiptText}>Tax</Text><Text style={s.receiptStrong}>{"$"+Number(created.tax||0).toFixed(2)}</Text></View>:null}
          {Number(created.delivery_fee||0)>0?<View style={s.receiptTotalRow}><Text style={s.receiptText}>Pickup & delivery</Text><Text style={s.receiptStrong}>{"$"+Number(created.delivery_fee||0).toFixed(2)}</Text></View>:null}
          <View style={[s.receiptTotalRow,s.receiptGrandTotal]}><Text style={s.receiptGrandText}>Total</Text><Text style={s.receiptGrandText}>{"$"+Number(created.total||0).toFixed(2)}</Text></View>
        </View>

        {successGarments.length?<View style={s.receiptSectionFull}>
          <Text style={s.receiptLabel}>INDIVIDUAL GARMENT BARCODES ({successGarments.length})</Text>
          <View style={s.garmentReceiptGrid}>{successGarments.map((g:any)=><View style={s.garmentReceiptCard} key={g.id||g.garment_code}>
            <Text style={s.receiptStrong}>{g.service_name}</Text>
            <Text style={s.receiptTiny}>Garment {g.garment_index}</Text>
            <View style={s.garmentBarcodeVisual}><Code128 value={g.garment_code} height={36} moduleWidth={1.1}/></View>
            <Text style={s.receiptTiny}>{g.garment_code}</Text>
          </View>)}</View>
        </View>:null}

        {created.notes?<View style={s.receiptSectionFull}><Text style={s.receiptLabel}>NOTES</Text><Text style={s.receiptText}>{created.notes}</Text></View>:null}
      </View>

      {err?<Text style={s.err}>{err}</Text>:null}
      <View style={s.successActions}>
        <Pressable style={s.primary} onPress={()=>printCreatedTags("order")}><Text style={s.primaryText}>Print Order Tag</Text></Pressable>
        <Pressable style={s.primary} onPress={()=>printCreatedTags("garments")}><Text style={s.primaryText}>Print All Garment Tags</Text></Pressable>
        <Pressable style={s.primary} onPress={printReceipt}><Text style={s.primaryText}>Print Receipt</Text></Pressable>
        <Pressable style={s.secondary} onPress={()=>router.push("/order-detail?id="+encodeURIComponent(created.id))}><Text style={s.secondaryText}>Open Order</Text></Pressable>
        <Pressable style={s.secondary} onPress={()=>{setCreated(null);setLines([]);setSelectedCustomer(null);setCustomerQuery("");setCustomerResults([]);setName("");setPhone("");setEmail("");setNotes("");setDueAt("");setFulfillmentType("walk_in");setPickupDate("");setPickupSlotId("");setDeliveryDate("");setDeliverySlotId("");setPromoCode("");setPromoDiscount(0);setPromoMessage("");}}><Text style={s.secondaryText}>New Order</Text></Pressable>
      </View>
    </View>
  </ScrollView>;

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}><Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View></View>
    <View style={s.header}><Text style={s.kicker}>COUNTER</Text><Text style={s.title}>Create Order</Text><Text style={s.sub}>Find or scan a customer, add garments/services and quantities, then create the order. Order and garment tracking barcodes are generated automatically.</Text></View>

    <View style={s.panel}>
      <Text style={s.panelTitle}>Fulfillment</Text>
      <View style={s.fulfillmentList}>
        {fulfillmentOptions.map(([value,label,help])=><Pressable key={value} onPress={()=>{setFulfillmentType(value);setPickupDate("");setPickupSlotId("");setDeliveryDate("");setDeliverySlotId("");}} style={s.fulfillmentOption}>
          <View style={[s.radioOuter,fulfillmentType===value&&s.radioOuterOn]}>{fulfillmentType===value?<View style={s.radioInner}/>:null}</View>
          <View style={{flex:1}}><Text style={s.fulfillmentLabel}>{label}</Text><Text style={s.fulfillmentHelp}>{help}</Text></View>
        </Pressable>)}
      </View>
      {fulfillmentType!=="walk_in"?<View style={{marginTop:12}}>
        <Text style={s.helper}>{fulfillmentType==="pickup_only"?"Schedule pickup. Return collection will be Walk-In.":fulfillmentType==="delivery_only"?"Pickup is Walk-In. Schedule only the return delivery.":"Schedule both pickup and return delivery. Coverage and slot length are managed by the administrator."}</Text>
        <View style={s.scheduleGrid}>
          {needsPickup?<View style={s.scheduleBox}>
            <Text style={s.smallLabel}>PICKUP DATE</Text>
            <CalendarDatePicker value={pickupDate} min={isoDate(0)} label="Select pickup date" onChange={v=>{setPickupDate(v);setPickupSlotId("");if(deliveryDate&&deliveryDate<=v){setDeliveryDate("");setDeliverySlotId("");}}}/>
            <Text style={s.smallLabel}>PICKUP TIME</Text>
            <View style={s.filters}>{pickupSlots.map(x=><Pressable key={x.id} onPress={()=>setPickupSlotId(x.id)} style={[s.filter,pickupSlotId===x.id&&s.filterOn]}><Text style={[s.filterText,pickupSlotId===x.id&&s.filterTextOn]}>{x.name+" · "+x.start_time+"-"+x.end_time}</Text></Pressable>)}</View>
            {pickupDate&&pickupSlots.length===0?<Text style={s.slotWarning}>No pickup time slots are configured for this date. Add or enable slots in Admin → Pickup & Delivery.</Text>:null}
          </View>:null}
          {needsDelivery?<View style={s.scheduleBox}>
            <Text style={s.smallLabel}>DELIVERY DATE</Text>
            <CalendarDatePicker value={deliveryDate} min={fulfillmentType==="pickup_and_delivery"&&pickupDate?addDays(pickupDate,1):isoDate(1)} label="Select delivery date" onChange={v=>{setDeliveryDate(v);setDeliverySlotId("");}}/>
            <Text style={s.smallLabel}>DELIVERY TIME</Text>
            <View style={s.filters}>{deliverySlots.map(x=><Pressable key={x.id} onPress={()=>setDeliverySlotId(x.id)} style={[s.filter,deliverySlotId===x.id&&s.filterOn]}><Text style={[s.filterText,deliverySlotId===x.id&&s.filterTextOn]}>{x.name+" · "+x.start_time+"-"+x.end_time}</Text></Pressable>)}</View>
            {deliveryDate&&deliverySlots.length===0?<Text style={s.slotWarning}>No delivery time slots are configured for this date. Add or enable slots in Admin → Pickup & Delivery.</Text>:null}
          </View>:null}
        </View>
      </View>:null}
    </View>

    <View style={s.layout}>
      <View style={s.main}>
        <View style={s.panel}>
          <Text style={s.panelTitle}>1. Find customer</Text>
          <View style={s.customerSearchRow}>
            <TextInput style={s.customerSearchInput} placeholder="Customer ID, email, phone, or scan CUSTOMER:<id>" value={customerQuery} onChangeText={setCustomerQuery} onSubmitEditing={searchCustomers} autoCapitalize="none"/>
            <Pressable style={s.searchCustomerBtn} onPress={searchCustomers}><Text style={s.searchCustomerText}>{searchingCustomer?"Searching…":"Search"}</Text></Pressable>
          </View>
          {customerResults.length>0?<View style={s.customerResults}>{customerResults.map(customer=><Pressable key={customer.id} style={s.customerResult} onPress={()=>selectCustomer(customer)}>
            <View><Text style={s.sn}>{customer.name}</Text><Text style={s.lineMeta}>{customer.phone}{customer.email?" · "+customer.email:""}</Text></View>
            <View style={{alignItems:"flex-end"}}><Text style={s.customerMetric}>{customer.order_count||0} orders</Text><Text style={s.lineMeta}>{"$"+(customer.lifetime_value||0).toFixed(2)} lifetime</Text></View>
          </Pressable>)}</View>:null}
          <Text style={s.helper}>Search and select a customer before entering order details. If the customer is new, use the customer details section below.</Text>
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>2. Customer details</Text>
          {selectedCustomer?<View style={s.customerDetailCard}>
            <View><Text style={s.selectedCustomerLabel}>SELECTED CUSTOMER</Text><Text style={s.customerDetailName}>{selectedCustomer.name}</Text><Text style={s.lineMeta}>{selectedCustomer.phone}{selectedCustomer.email?" · "+selectedCustomer.email:""}</Text><Text style={s.lineMeta}>Customer ID: {selectedCustomer.id}</Text></View>
            <Pressable onPress={clearCustomer}><Text style={s.clearCustomer}>Change customer</Text></Pressable>
          </View>:<>
            <Text style={s.helper}>New customer — enter the details below. A customer record will be created with this order.</Text>
            <View style={s.formRow}><TextInput style={s.input} placeholder="Customer name *" value={name} onChangeText={setName}/><TextInput style={s.input} placeholder="Phone *" value={phone} onChangeText={setPhone} keyboardType="phone-pad"/></View>
            <TextInput style={s.fullInput} placeholder="Email (optional)" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none"/>
          </>}
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>3. Add garments / services</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filters}>
            {categories.map(c=><Pressable key={c} onPress={()=>setCategory(c)} style={[s.filter,category===c&&s.filterOn]}><Text style={[s.filterText,category===c&&s.filterTextOn]}>{c}</Text></Pressable>)}
          </ScrollView>
          <View style={s.grid}>{visible.map(x=><Pressable key={x.id} style={s.service} onPress={()=>add(x)}>
            <Image source={{uri:imageForCategory(x.category)}} style={s.serviceImage} resizeMode="cover"/>
            <View style={s.serviceBody}><Text style={s.cat}>{x.category}</Text><Text style={s.sn}>{x.name}</Text><Text style={s.price}>{"$"+x.base_price.toFixed(2)+" / "+(x.unit_label||"item")}</Text><Text style={s.addText}>+ Add</Text></View>
          </Pressable>)}</View>
        </View>

        <View style={s.panel}>
          <Text style={s.panelTitle}>4. Order notes & due date</Text>
          <TextInput style={s.notes} placeholder="Special instructions, stains, existing damage, delicate handling…" value={notes} onChangeText={setNotes} multiline numberOfLines={4}/>
          <Text style={s.smallLabel}>DUE DATE / TIME (OPTIONAL)</Text><TextInput style={s.fullInput} placeholder="2026-10-07T17:00:00+05:30" value={dueAt} onChangeText={setDueAt} autoCapitalize="none"/>
          <Text style={s.helper}>For pickup/mobile orders, barcodes are created now and tags can be printed later when the garments arrive.</Text>
        </View>
      </View>

      <View style={s.sidebar}>
        <View style={s.summary}>
          <Text style={s.panelTitle}>Order summary</Text>
          {lines.length===0?<Text style={s.empty}>No services added yet.</Text>:lines.map((l,i)=><View style={s.line} key={l.service_id}>
            <View style={{flex:1}}><Text style={s.sn}>{l.service_name}</Text><Text style={s.lineMeta}>{"$"+l.unit_price.toFixed(2)+" / "+l.unit_label}</Text></View>
            <View style={s.qty}><Pressable onPress={()=>adjust(i,-1)} style={s.iconBtn}><Minus size={16} color={colors.ink}/></Pressable><Text style={s.qtyText}>{l.quantity}</Text><Pressable onPress={()=>adjust(i,1)} style={s.iconBtn}><Plus size={16} color={colors.ink}/></Pressable><Pressable onPress={()=>remove(i)} style={s.trash}><Trash size={17} color={colors.danger}/></Pressable></View>
          </View>)}
          <View style={s.total}><Text style={s.totalLabel}>Estimated total</Text><Text style={s.totalText}>{"$"+(total+deliveryFee).toFixed(2)}</Text></View>{deliveryFee>0?<Text style={s.helper}>{"Includes $"+deliveryFee.toFixed(2)+" delivery fee."}</Text>:null}
          {capabilities.offers_enabled?<><Text style={s.smallLabel}>PROMO CODE</Text><View style={s.customerSearchRow}><TextInput style={s.customerSearchInput} placeholder="Promo code" value={promoCode} onChangeText={v=>{setPromoCode(v.toUpperCase());setPromoDiscount(0);setPromoMessage("");}} autoCapitalize="characters"/><Pressable style={s.searchCustomerBtn} onPress={applyPromo}><Text style={s.searchCustomerText}>Apply</Text></Pressable></View>{promoMessage?<Text style={s.helper}>{promoMessage+" · -$"+promoDiscount.toFixed(2)}</Text>:null}</>:null}<Text style={s.smallLabel}>PAYMENT STATUS</Text>
          <View style={s.paymentRow}>{["unpaid","partial","paid"].map(p=><Pressable key={p} onPress={()=>setPaymentStatus(p)} style={[s.payChip,paymentStatus===p&&s.payChipOn]}><Text style={[s.payText,paymentStatus===p&&s.payTextOn]}>{p[0].toUpperCase()+p.slice(1)}</Text></Pressable>)}</View>
          {err?<Text style={s.err}>{err}</Text>:null}
          <Pressable disabled={!name.trim()||!phone.trim()||!lines.length||(needsPickup&&(!pickupDate||!pickupSlotId))||(needsDelivery&&(!deliveryDate||!deliverySlotId))||saving} style={[s.saveBtn,(!name.trim()||!phone.trim()||!lines.length||(needsPickup&&(!pickupDate||!pickupSlotId))||(needsDelivery&&(!deliveryDate||!deliverySlotId))||saving)&&{opacity:.4}]} onPress={save}><Text style={s.saveText}>{saving?"Creating…":"Create Order + Garment Barcodes"}</Text></Pressable>
          <Text style={s.helper}>You can update order status and payment details after creation.</Text>
        </View>
      </View>
    </View>
  </ScrollView>
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1180,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"700",color:colors.ink},brand:{flexDirection:"row",alignItems:"center",gap:6},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:24},kicker:{fontSize:11,fontWeight:"900",letterSpacing:1.5,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:6},
  fulfillmentList:{flexDirection:"row",flexWrap:"wrap",gap:8},fulfillmentOption:{flexDirection:"row",alignItems:"flex-start",gap:9,paddingVertical:9,paddingHorizontal:10,borderWidth:1,borderColor:colors.border,borderRadius:12,backgroundColor:colors.soft,flexBasis:"48%",flexGrow:1,minWidth:220},radioOuter:{width:20,height:20,borderRadius:999,borderWidth:2,borderColor:colors.border,alignItems:"center",justifyContent:"center",marginTop:1},radioOuterOn:{borderColor:colors.primary},radioInner:{width:10,height:10,borderRadius:999,backgroundColor:colors.primary},fulfillmentLabel:{fontWeight:"900",color:colors.ink},fulfillmentHelp:{fontSize:12,color:colors.muted,marginTop:2},layout:{flexDirection:"row",flexWrap:"wrap",gap:16,alignItems:"flex-start"},main:{flex:1,minWidth:580,gap:16},sidebar:{width:350,maxWidth:"100%"},panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,padding:20},panelTitle:{fontSize:18,fontWeight:"900",color:colors.ink,marginBottom:14},
  customerSearchRow:{flexDirection:"row",gap:8,marginBottom:10},customerSearchInput:{flex:1,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:13},searchCustomerBtn:{backgroundColor:colors.ink,borderRadius:12,paddingHorizontal:18,justifyContent:"center"},searchCustomerText:{color:"#fff",fontWeight:"900"},customerResults:{borderWidth:1,borderColor:colors.border,borderRadius:12,overflow:"hidden",marginBottom:10},customerResult:{padding:12,flexDirection:"row",justifyContent:"space-between",gap:12,borderBottomWidth:1,borderBottomColor:colors.border,backgroundColor:colors.soft},customerMetric:{fontWeight:"900",fontSize:12,color:colors.primary},selectedCustomer:{backgroundColor:colors.primarySoft,borderRadius:12,padding:12,marginBottom:10,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},selectedCustomerLabel:{fontSize:9,fontWeight:"900",letterSpacing:1,color:colors.primary},clearCustomer:{color:colors.primary,fontWeight:"900"},formRow:{flexDirection:"row",flexWrap:"wrap",gap:10},input:{flex:1,minWidth:220,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:13,backgroundColor:"#fff"},fullInput:{marginTop:10,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:13},
  filters:{gap:8,paddingBottom:14},filter:{paddingHorizontal:13,paddingVertical:9,borderRadius:999,borderWidth:1,borderColor:colors.border,backgroundColor:colors.soft},filterOn:{backgroundColor:colors.primary,borderColor:colors.primary},filterText:{fontWeight:"800",color:colors.ink,fontSize:12},filterTextOn:{color:"#fff"},
  grid:{flexDirection:"row",flexWrap:"wrap",gap:10},service:{width:215,borderWidth:1,borderColor:colors.border,borderRadius:16,backgroundColor:"#fff",overflow:"hidden"},serviceImage:{width:"100%",height:105},serviceBody:{padding:12},cat:{fontSize:9,fontWeight:"900",letterSpacing:1,color:colors.primary,textTransform:"uppercase"},sn:{fontWeight:"900",color:colors.ink,marginTop:3},price:{color:colors.muted,marginTop:5},addText:{fontWeight:"900",color:colors.primary,marginTop:8},
  notes:{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:13,minHeight:105,textAlignVertical:"top"},helper:{fontSize:12,color:colors.muted,lineHeight:18,marginTop:8},slotWarning:{fontSize:12,color:colors.danger,lineHeight:18,marginTop:6},
  summary:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,padding:20,position:"sticky" as any,top:12},empty:{color:colors.muted,paddingVertical:10},line:{paddingVertical:12,borderBottomWidth:1,borderBottomColor:colors.border,flexDirection:"row",alignItems:"center",gap:8},lineMeta:{fontSize:12,color:colors.muted,marginTop:2},qty:{flexDirection:"row",alignItems:"center",gap:7},iconBtn:{width:30,height:30,borderRadius:9,borderWidth:1,borderColor:colors.border,alignItems:"center",justifyContent:"center"},qtyText:{minWidth:24,textAlign:"center",fontWeight:"900",color:colors.ink},trash:{padding:5},
  total:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",paddingVertical:18},totalLabel:{fontWeight:"800",color:colors.ink},totalText:{fontSize:25,fontWeight:"900",color:colors.primary},smallLabel:{fontSize:10,fontWeight:"900",letterSpacing:1.1,color:colors.muted,marginBottom:8},paymentRow:{flexDirection:"row",gap:7},payChip:{flex:1,paddingVertical:9,borderRadius:10,backgroundColor:colors.soft,alignItems:"center",borderWidth:1,borderColor:colors.border},payChipOn:{backgroundColor:colors.primarySoft,borderColor:"#B8DED7"},payText:{fontWeight:"800",fontSize:12,color:colors.muted},payTextOn:{color:colors.primaryDark},err:{color:colors.danger,marginTop:10},saveBtn:{backgroundColor:colors.primary,borderRadius:13,padding:15,alignItems:"center",marginTop:16},saveText:{color:"#fff",fontWeight:"900"},
  successCard:{maxWidth:900,width:"100%",alignSelf:"center",backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:26,padding:24,alignItems:"center",marginTop:24},successIcon:{width:62,height:62,borderRadius:999,backgroundColor:colors.success,alignItems:"center",justifyContent:"center"},successTitle:{fontSize:24,fontWeight:"900",color:colors.ink,marginTop:16},successNo:{fontSize:34,fontWeight:"900",color:colors.primary,marginTop:6},successText:{color:colors.muted,marginTop:4},codeBox:{width:"100%",backgroundColor:colors.soft,borderRadius:16,padding:18,marginTop:20,alignItems:"center"},codeLabel:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.muted},code:{fontSize:22,fontWeight:"900",color:colors.ink,marginTop:5},barcodeValue:{fontSize:11,fontWeight:"800",color:colors.muted,marginTop:2},barcodeVisual:{marginTop:8,maxWidth:"100%",overflow:"hidden"},receiptCard:{width:"100%",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18,marginTop:18,backgroundColor:"#fff"},receiptHeader:{alignItems:"center",paddingBottom:12,borderBottomWidth:1,borderBottomColor:colors.border},receiptBusiness:{fontSize:23,fontWeight:"900",color:colors.ink,textAlign:"center"},receiptHeaderText:{fontSize:12,color:colors.muted,marginTop:3,textAlign:"center"},orderBarcodeBox:{alignItems:"center",paddingVertical:14,borderBottomWidth:1,borderBottomColor:colors.border},receiptTwoCol:{flexDirection:"row",flexWrap:"wrap",gap:16,paddingVertical:14},receiptSection:{flex:1,minWidth:260},receiptSectionFull:{paddingVertical:12,borderTopWidth:1,borderTopColor:colors.border},receiptLabel:{fontSize:10,fontWeight:"900",letterSpacing:1.1,color:colors.muted,marginBottom:7},receiptStrong:{fontWeight:"900",color:colors.ink},receiptText:{fontSize:12,color:colors.ink,marginTop:3},receiptTiny:{fontSize:10,color:colors.muted,marginTop:2},receiptTableHead:{flexDirection:"row",gap:8,paddingVertical:7,borderBottomWidth:1,borderBottomColor:colors.border},receiptTableHeadText:{fontSize:10,fontWeight:"900",color:colors.muted},receiptRow:{flexDirection:"row",gap:8,paddingVertical:9,borderBottomWidth:1,borderBottomColor:colors.border,alignItems:"center"},receiptColItem:{flex:1,minWidth:130},receiptColQty:{width:45,textAlign:"right",fontSize:12,color:colors.ink},receiptColMoney:{width:78,textAlign:"right",fontSize:12,color:colors.ink},scheduleGrid:{flexDirection:"row",flexWrap:"wrap",gap:14},scheduleBox:{flex:1,minWidth:280,backgroundColor:colors.soft,borderRadius:14,padding:12},customerDetailCard:{backgroundColor:colors.primarySoft,borderRadius:14,padding:14,flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"},customerDetailName:{fontSize:18,fontWeight:"900",color:colors.ink,marginTop:3},receiptTotals:{alignSelf:"flex-end",width:320,maxWidth:"100%",paddingTop:12},receiptTotalRow:{flexDirection:"row",justifyContent:"space-between",paddingVertical:4},receiptGrandTotal:{borderTopWidth:1,borderTopColor:colors.ink,marginTop:4,paddingTop:8},receiptGrandText:{fontSize:18,fontWeight:"900",color:colors.ink},garmentReceiptGrid:{flexDirection:"row",flexWrap:"wrap",gap:8},garmentReceiptCard:{minWidth:190,flexGrow:1,borderWidth:1,borderColor:colors.border,borderRadius:10,padding:9,alignItems:"center"},garmentBarcodeVisual:{marginTop:5,maxWidth:"100%",overflow:"hidden"},successActions:{width:"100%",flexDirection:"row",flexWrap:"wrap",gap:10,marginTop:18,justifyContent:"center"},primary:{backgroundColor:colors.primary,borderRadius:13,paddingHorizontal:16,paddingVertical:13,minWidth:180,flexGrow:1,alignItems:"center",justifyContent:"center"},primaryText:{color:"#fff",fontWeight:"900",textAlign:"center"},secondary:{borderWidth:1,borderColor:colors.border,borderRadius:13,paddingHorizontal:16,paddingVertical:13,minWidth:180,flexGrow:1,alignItems:"center",justifyContent:"center"},secondaryText:{color:colors.primary,fontWeight:"900",textAlign:"center"}
});

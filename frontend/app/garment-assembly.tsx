import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Barcode, CheckCircle, Sparkle, WarningCircle } from "phosphor-react-native";
import { api, getStoredStaff } from "@/src/api";
import { colors } from "@/src/theme";

type Garment={id:string;garment_code:string;garment_index:number;service_name:string;last_stage:string;assembled:boolean};
type Order={id:string;order_number:string;customer:{name:string;phone:string};status:string};

export default function GarmentAssembly(){
  const router=useRouter();
  const params=useLocalSearchParams<{id?:string}>();
  const id=String(params.id||"");
  const [order,setOrder]=useState<Order|null>(null);
  const [garments,setGarments]=useState<Garment[]>([]);
  const [scan,setScan]=useState("");
  const [err,setErr]=useState("");
  const [ok,setOk]=useState("");
  const staff=getStoredStaff();
  const canOverride=staff?.role==="owner"||staff?.role==="manager";

  async function load(){
    if(!id)return;
    setErr("");
    try{
      const [o,g]=await Promise.all([api.get<Order>("/orders/"+encodeURIComponent(id)),api.get<any>("/orders/"+encodeURIComponent(id)+"/garments")]);
      setOrder(o);setGarments(g.garments||[]);
    }catch(e:any){setErr(e.message||"Could not load assembly");}
  }
  useEffect(()=>{load();},[id]);

  const assembled=useMemo(()=>garments.filter(g=>g.assembled).length,[garments]);
  const missing=garments.length-assembled;

  async function scanGarment(){
    const code=scan.trim().toUpperCase();if(!code)return;
    setErr("");setOk("");
    try{
      const g=await api.post<Garment>("/orders/"+id+"/garments/"+encodeURIComponent(code)+"/scan",{stage:"assembly"});
      setGarments(v=>v.map(x=>x.id===g.id?g:x));setScan("");setOk(g.garment_code+" assembled");
    }catch(e:any){setErr(e.message||"Garment not found for this order");}
  }
  async function complete(override=false){
    setErr("");setOk("");
    try{
      await api.post("/orders/"+id+"/assembly/complete",{override});
      setOk(override?"Assembly completed with manager override":"Assembly complete. Order is Ready for Pickup.");
      await load();
    }catch(e:any){setErr(e.message||"Could not complete assembly");}
  }

  if(!order)return <View style={s.loading}><Text>{err||"Loading assembly…"}</Text></View>;
  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}><Pressable onPress={()=>router.push("/order-detail?id="+encodeURIComponent(id))} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Order</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Assembly</Text></View></View>
    <View style={s.header}><View><Text style={s.kicker}>GARMENT ASSEMBLY</Text><Text style={s.title}>{order.order_number}</Text><Text style={s.sub}>{order.customer.name} · Scan every garment before completing the order.</Text></View><View style={s.progress}><Text style={s.progressValue}>{assembled} / {garments.length}</Text><Text style={s.progressLabel}>assembled</Text></View></View>

    <View style={s.scanPanel}><View style={s.scanBox}><Barcode size={22} color={colors.primary}/><TextInput autoFocus value={scan} onChangeText={setScan} onSubmitEditing={scanGarment} placeholder="Scan or enter garment code" autoCapitalize="characters" style={s.input}/></View><Pressable onPress={scanGarment} style={s.scanBtn}><Text style={s.scanText}>Scan</Text></Pressable></View>
    {err?<View style={s.alert}><WarningCircle size={17} color={colors.danger}/><Text style={s.err}>{err}</Text></View>:null}{ok?<View style={s.okRow}><CheckCircle size={17} color={colors.success}/><Text style={s.ok}>{ok}</Text></View>:null}

    <View style={s.panel}><View style={s.panelHead}><Text style={s.panelTitle}>Assembly checklist</Text><Text style={s.meta}>{missing} missing</Text></View>
      {garments.map(g=><View key={g.id} style={[s.row,g.assembled&&s.rowDone]}><View style={[s.dot,g.assembled&&s.dotDone]}>{g.assembled?<CheckCircle size={16} color="#fff"/>:<Text style={s.dotText}>{g.garment_index}</Text>}</View><View style={{flex:1}}><Text style={s.code}>{g.garment_code}</Text><Text style={s.meta}>{g.service_name} · {g.last_stage.replaceAll("_"," ")}</Text></View><Text style={[s.state,g.assembled&&s.stateDone]}>{g.assembled?"ASSEMBLED":"MISSING"}</Text></View>)}
    </View>

    <View style={s.actions}><Pressable disabled={missing>0} onPress={()=>complete(false)} style={[s.completeBtn,missing>0&&{opacity:.4}]}><Text style={s.completeText}>Complete Assembly</Text></Pressable>{missing>0&&canOverride?<Pressable onPress={()=>complete(true)} style={s.overrideBtn}><Text style={s.overrideText}>Manager Override ({missing} missing)</Text></Pressable>:null}</View>
    {missing>0?<Text style={s.help}>The order cannot be marked Ready for Pickup until every expected garment is scanned. Owner/Manager may override when necessary.</Text>:null}
  </ScrollView>;
}

const s=StyleSheet.create({
  loading:{padding:30},page:{padding:20,maxWidth:1050,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",gap:16,alignItems:"flex-start",flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink},sub:{color:colors.muted,marginTop:4},progress:{backgroundColor:colors.primarySoft,borderRadius:14,padding:12,minWidth:120,alignItems:"center"},progressValue:{fontSize:26,fontWeight:"900",color:colors.primaryDark},progressLabel:{fontSize:11,fontWeight:"800",color:colors.muted},
  scanPanel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:12,flexDirection:"row",gap:8,alignItems:"center",flexWrap:"wrap"},scanBox:{flex:1,minWidth:260,borderWidth:1,borderColor:colors.border,borderRadius:11,flexDirection:"row",alignItems:"center",paddingHorizontal:10},input:{flex:1,padding:11},scanBtn:{backgroundColor:colors.primary,borderRadius:11,minHeight:44,paddingHorizontal:18,justifyContent:"center"},scanText:{color:"#fff",fontWeight:"900"},
  panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:16},panelHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:8,flexWrap:"wrap"},panelTitle:{fontSize:18,fontWeight:"900",color:colors.ink},row:{flexDirection:"row",gap:10,alignItems:"center",paddingVertical:11,borderTopWidth:1,borderTopColor:colors.border},rowDone:{backgroundColor:colors.primarySoft},dot:{width:30,height:30,borderRadius:15,borderWidth:1,borderColor:colors.border,alignItems:"center",justifyContent:"center"},dotDone:{backgroundColor:colors.success,borderColor:colors.success},dotText:{fontSize:11,fontWeight:"900",color:colors.muted},code:{fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:2},state:{fontSize:10,fontWeight:"900",color:colors.danger},stateDone:{color:colors.success},
  actions:{flexDirection:"row",gap:10,flexWrap:"wrap"},completeBtn:{backgroundColor:colors.primary,borderRadius:12,minHeight:44,paddingHorizontal:18,justifyContent:"center"},completeText:{color:"#fff",fontWeight:"900"},overrideBtn:{borderWidth:1,borderColor:colors.danger,borderRadius:12,minHeight:44,paddingHorizontal:18,justifyContent:"center"},overrideText:{color:colors.danger,fontWeight:"900"},help:{fontSize:12,color:colors.muted},alert:{flexDirection:"row",gap:7,alignItems:"center"},err:{color:colors.danger},okRow:{flexDirection:"row",gap:7,alignItems:"center"},ok:{color:colors.success,fontWeight:"800"}
});
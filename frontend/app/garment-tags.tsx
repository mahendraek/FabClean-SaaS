import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Printer, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { defaultHardwareProfile, downloadRaw, generateTspl, generateZpl, openLabelPrint, profileFromSettings, HardwareProfile } from "@/src/hardware";
import { Code128 } from "@/src/Code128";
import { colors } from "@/src/theme";

type Garment={id:string;garment_code:string;garment_index:number;service_name:string;last_stage:string;assembled:boolean;tag_print_count:number};
type Order={id:string;order_number:string;barcode_value:string;customer:{name:string;phone:string}};

export default function GarmentTags(){
  const router=useRouter();
  const params=useLocalSearchParams<{id?:string}>();
  const id=String(params.id||"");
  const [order,setOrder]=useState<Order|null>(null);
  const [garments,setGarments]=useState<Garment[]>([]);
  const [err,setErr]=useState("");
  const [hardware,setHardware]=useState<HardwareProfile>(defaultHardwareProfile);

  async function load(){
    if(!id)return;
    setErr("");
    try{
      const [o,g,cfg]=await Promise.all([api.get<Order>("/orders/"+encodeURIComponent(id)),api.get<any>("/orders/"+encodeURIComponent(id)+"/garments"),api.get<any>("/settings")]);
      setOrder(o);setGarments(g.garments||[]);setHardware(profileFromSettings(cfg));
    }catch(e:any){setErr(e.message||"Could not load garment tags");}
  }
  useEffect(()=>{load();},[id]);

  async function printAll(){
    if(!order)return;
    openLabelPrint(order.order_number+" garment tags",garments.map(g=>({code:g.garment_code,order:order.order_number,line1:g.service_name,line2:"Item "+g.garment_index+" / "+garments.length})),hardware);
    try{
      await Promise.all(garments.map(g=>api.post("/orders/"+order.id+"/garments/"+encodeURIComponent(g.garment_code)+"/reprint",{})));
      await load();
    }catch(e:any){setErr(e.message||"Could not record tag printing");}
  }

  function printOrderTag(){
    if(!order)return;
    openLabelPrint(order.order_number+" order tag",[{code:order.barcode_value||order.order_number.replace("-",""),order:order.order_number,line1:order.customer.name,line2:"ORDER TAG"}],hardware);
  }

  function exportRaw(){
    if(!order)return;
    if(hardware.printer_mode==="zpl"){
      downloadRaw(order.order_number+"-garment-tags.zpl",generateZpl(order,garments,hardware));
    }else if(hardware.printer_mode==="tspl"){
      downloadRaw(order.order_number+"-garment-tags.tspl",generateTspl(order,garments,hardware));
    }else{
      if(typeof window!=="undefined")window.print();
    }
  }

  async function reprintOne(code:string){
    const g=garments.find(x=>x.garment_code===code);
    if(order&&g)openLabelPrint(code,[{code,order:order.order_number,line1:g.service_name,line2:"Item "+g.garment_index+" / "+garments.length}],hardware);
    try{
      await api.post("/orders/"+id+"/garments/"+encodeURIComponent(code)+"/reprint",{});
      await load();
    }catch(e:any){setErr(e.message||"Could not record tag reprint");}
  }

  if(!order)return <View style={s.loading}><Text>{err||"Loading garment tags…"}</Text></View>;
  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.noPrint}><View style={s.top}><Pressable onPress={()=>router.push("/order-detail?id="+encodeURIComponent(id))} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Order</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Garment Tags</Text></View></View>
      <View style={s.header}><View><Text style={s.kicker}>GARMENT TAGGING</Text><Text style={s.title}>{order.order_number}</Text><Text style={s.sub}>{order.customer.name} · {garments.length} physical garment tag(s) · {hardware.printer_mode.toUpperCase()} profile</Text></View><View style={s.headerActions}><Pressable onPress={printOrderTag} style={s.rawBtn}><Text style={s.rawText}>Print Order Tag</Text></Pressable><Pressable onPress={printAll} style={s.printBtn}><Printer size={17} color="#fff"/><Text style={s.printText}>Print All Garments</Text></Pressable><Pressable onPress={exportRaw} style={s.rawBtn}><Text style={s.rawText}>{hardware.printer_mode==="browser"?"Print / Preview":"Download "+hardware.printer_mode.toUpperCase()}</Text></Pressable></View></View>
      {err?<Text style={s.err}>{err}</Text>:null}
    </View>
    <View style={s.tags}>{garments.map(g=><View key={g.id} style={s.tag}>
      <Text style={s.brandSmall}>FAB CLEAN</Text><Text style={s.order}>{order.order_number}</Text><Text style={s.item}>{g.service_name}</Text><Text style={s.position}>Item {g.garment_index} / {garments.length}</Text><View style={s.barcode}><Code128 value={g.garment_code} height={48} moduleWidth={1.5}/></View><Text style={s.code}>{g.garment_code}</Text>
      <Pressable style={[s.reprint,s.noPrint]} onPress={()=>reprintOne(g.garment_code)}><Text style={s.reprintText}>Reprint · {g.tag_print_count||0}</Text></Pressable>
    </View>)}</View>
  </ScrollView>;
}

const s=StyleSheet.create({
  loading:{padding:30},page:{padding:20,maxWidth:1050,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,padding:20,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:12,flexWrap:"wrap"},headerActions:{flexDirection:"row",gap:8,flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.primary},title:{fontSize:30,fontWeight:"900",color:colors.ink},sub:{color:colors.muted,marginTop:3},printBtn:{backgroundColor:colors.primary,borderRadius:11,minHeight:42,paddingHorizontal:14,flexDirection:"row",gap:7,alignItems:"center",justifyContent:"center"},printText:{color:"#fff",fontWeight:"900"},rawBtn:{borderWidth:1,borderColor:colors.primary,borderRadius:11,minHeight:42,paddingHorizontal:14,alignItems:"center",justifyContent:"center"},rawText:{color:colors.primary,fontWeight:"900"},
  tags:{flexDirection:"row",flexWrap:"wrap",gap:10},tag:{width:230,minHeight:210,backgroundColor:"#fff",borderWidth:1,borderColor:"#222",borderRadius:8,padding:12,alignItems:"center"},brandSmall:{fontSize:11,fontWeight:"900",letterSpacing:1.2},order:{fontSize:20,fontWeight:"900",marginTop:4},item:{fontSize:14,fontWeight:"800",marginTop:3,textAlign:"center"},position:{fontSize:11,color:colors.muted,marginTop:2},barcode:{marginTop:10},code:{fontSize:13,fontWeight:"900",letterSpacing:1,marginTop:5},reprint:{marginTop:8,paddingVertical:5,paddingHorizontal:8},reprintText:{fontSize:11,fontWeight:"800",color:colors.primary},err:{color:colors.danger},noPrint:{}
});
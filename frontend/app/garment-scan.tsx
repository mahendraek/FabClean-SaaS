import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Barcode, CheckCircle, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { defaultHardwareProfile, normalizeScan, profileFromSettings, HardwareProfile } from "@/src/hardware";
import { colors } from "@/src/theme";

const STAGES=["inspection","cleaning","quality_check","assembly"];
const pretty=(x:string)=>x.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());

export default function GarmentScan(){
  const router=useRouter();
  const [stage,setStage]=useState("inspection");
  const [code,setCode]=useState("");
  const [result,setResult]=useState<any>(null);
  const [err,setErr]=useState("");
  const [hardware,setHardware]=useState<HardwareProfile>(defaultHardwareProfile);

  useEffect(()=>{api.get<any>("/settings").then(x=>setHardware(profileFromSettings(x))).catch(()=>{});},[]);

  async function scan(){
    const value=normalizeScan(code,hardware);
    if(!value)return;
    setErr("");setResult(null);
    try{
      const found=await api.get<any>("/garments/"+encodeURIComponent(value));
      const orderId=found.garment.order_id;
      const updated=await api.post<any>("/orders/"+orderId+"/garments/"+encodeURIComponent(value)+"/scan",{stage});
      setResult({garment:updated,order:found.order});
      setCode("");
    }catch(e:any){setErr(e.message||"Garment not found");}
  }

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Garment Scan</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>SCAN STATION</Text><Text style={s.title}>Track every garment</Text><Text style={s.sub}>Choose the processing stage, then scan the garment barcode. USB and Bluetooth scanners work like keyboard input.</Text></View>
    </View>

    <View style={s.panel}>
      <Text style={s.label}>Processing stage</Text>
      <View style={s.chips}>{STAGES.map(x=><Pressable key={x} onPress={()=>setStage(x)} style={[s.chip,stage===x&&s.chipOn]}><Text style={[s.chipText,stage===x&&s.chipTextOn]}>{pretty(x)}</Text></Pressable>)}</View>
      <Text style={s.label}>Garment barcode</Text>
      <View style={s.scanRow}><View style={s.scanBox}><Barcode size={22} color={colors.primary}/><TextInput autoFocus value={code} onChangeText={setCode} onSubmitEditing={scan} placeholder="Scan or enter FC1025-001" autoCapitalize="characters" style={s.input}/></View><Pressable onPress={scan} style={s.scanBtn}><Text style={s.scanText}>Record Scan</Text></Pressable></View>
      {err?<Text style={s.err}>{err}</Text>:null}
    </View>

    {result?<View style={s.result}>
      <View style={s.success}><CheckCircle size={22} color={colors.success}/><View><Text style={s.successTitle}>{result.garment.garment_code} recorded</Text><Text style={s.meta}>{pretty(result.garment.last_stage)}</Text></View></View>
      <View style={s.details}><View><Text style={s.smallLabel}>Order</Text><Text style={s.value}>{result.order?.order_number||"—"}</Text></View><View><Text style={s.smallLabel}>Customer</Text><Text style={s.value}>{result.order?.customer?.name||"—"}</Text></View><View><Text style={s.smallLabel}>Garment</Text><Text style={s.value}>{result.garment.service_name}</Text></View></View>
      <View style={s.actions}><Pressable onPress={()=>router.push({pathname:"/order-detail",params:{id:result.garment.order_id}})} style={s.secondary}><Text style={s.secondaryText}>Open Order</Text></Pressable>{stage==="assembly"?<Pressable onPress={()=>router.push({pathname:"/garment-assembly",params:{id:result.garment.order_id}})} style={s.primary}><Text style={s.primaryText}>Open Assembly</Text></Pressable>:null}</View>
    </View>:null}
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:900,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:3},sub:{color:colors.muted,marginTop:5,maxWidth:720},
  panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},label:{fontSize:10,fontWeight:"900",letterSpacing:.8,color:colors.muted,textTransform:"uppercase",marginBottom:7,marginTop:8},chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:12,paddingVertical:8},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},
  scanRow:{flexDirection:"row",gap:8,alignItems:"center",flexWrap:"wrap"},scanBox:{flex:1,minWidth:280,borderWidth:1,borderColor:colors.border,borderRadius:11,flexDirection:"row",alignItems:"center",paddingHorizontal:10},input:{flex:1,padding:12},scanBtn:{backgroundColor:colors.primary,borderRadius:11,minHeight:46,paddingHorizontal:18,justifyContent:"center"},scanText:{color:"#fff",fontWeight:"900"},err:{color:colors.danger,marginTop:10},
  result:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},success:{flexDirection:"row",gap:9,alignItems:"center"},successTitle:{fontSize:18,fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:2},details:{flexDirection:"row",gap:18,flexWrap:"wrap",marginTop:16},smallLabel:{fontSize:10,fontWeight:"900",color:colors.muted,textTransform:"uppercase"},value:{fontWeight:"800",color:colors.ink,marginTop:3},actions:{flexDirection:"row",gap:8,marginTop:16,flexWrap:"wrap"},secondary:{borderWidth:1,borderColor:colors.primary,borderRadius:11,paddingHorizontal:14,paddingVertical:10},secondaryText:{fontWeight:"900",color:colors.primary},primary:{backgroundColor:colors.primary,borderRadius:11,paddingHorizontal:14,paddingVertical:10},primaryText:{fontWeight:"900",color:"#fff"}
});
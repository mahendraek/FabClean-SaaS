import { themedStyles } from "@/src/theme";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";
import { defaultHardwareProfile, normalizeScan, profileFromSettings, validateProfile, openLabelPrint, HardwareProfile } from "@/src/hardware";

export default function Hardware(){
  const router=useRouter();
  const [profile,setProfile]=useState<HardwareProfile>(defaultHardwareProfile);
  const [testScan,setTestScan]=useState("");
  const [saved,setSaved]=useState("");
  const [err,setErr]=useState("");
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false);

  function load(){setErr("");api.get<any>("/settings").then(x=>{setProfile(profileFromSettings(x));setReady(true);}).catch(e=>setErr(e.message||"Could not load settings"));}
  useEffect(()=>{load();},[]);

  async function save(){
    if(!ready||busy)return;
    setErr("");setSaved("");setBusy(true);
    try{
      validateProfile(profile);
      await api.put("/settings",{hardware_profile:profile});
      setSaved("Hardware profile saved");
    }catch(e:any){setErr(e.message||"Could not save hardware profile");}finally{setBusy(false);}
  }

  if(!ready)return <View style={{padding:24,gap:12}}><Text accessibilityRole={err?"alert":undefined}>{err||"Loading hardware settings…"}</Text>{err?<Pressable accessibilityRole="button" onPress={load}><Text>Retry hardware settings</Text></Pressable>:null}</View>;

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}><Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Admin</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Hardware</Text></View></View>
    <View style={s.header}><View><Text style={s.kicker}>HARDWARE COMPATIBILITY</Text><Text style={s.title}>Scanners & Printers</Text><Text style={s.sub}>Use standard keyboard-mode scanners and choose a printer profile that matches your local hardware.</Text></View></View>

    <View style={s.panel}>
      <Text style={s.section}>Barcode scanner</Text><Text style={s.help}>Recommended mode: USB/Bluetooth HID keyboard. Most scanners type the barcode into the active field and optionally send Enter. This also works well with Bluetooth HID scanners paired to phones and tablets.</Text>
      <View style={s.formRow}><Field label="Strip prefix"><TextInput style={s.input} value={profile.scanner_prefix} onChangeText={v=>setProfile(p=>({...p,scanner_prefix:v}))} placeholder="Optional scanner prefix"/></Field><Field label="Strip suffix"><TextInput style={s.input} value={profile.scanner_suffix} onChangeText={v=>setProfile(p=>({...p,scanner_suffix:v}))} placeholder="Optional text suffix"/></Field></View>
      <View style={s.toggle}><View><Text style={s.toggleTitle}>Convert scans to uppercase</Text><Text style={s.help}>Recommended for FabClean garment IDs.</Text></View><Switch value={profile.scanner_uppercase} onValueChange={v=>setProfile(p=>({...p,scanner_uppercase:v}))}/></View>
      <Text style={s.label}>Scanner test</Text><TextInput style={s.input} value={testScan} onChangeText={setTestScan} placeholder="Scan a barcode here"/><Text style={s.preview}>Normalized: {normalizeScan(testScan,profile)||"—"}</Text>
    </View>

    <View style={s.panel}><Text style={s.section}>Receipt printer</Text><Text style={s.help}>Budget-friendly starting point: an 80 mm thermal receipt printer with a USB connection and a supported Windows/macOS/Linux driver. 58 mm printers use less counter space; A4 works with an existing office printer. FabClean opens the browser print document; select your installed printer.</Text><View style={s.chips}>{(['58mm','80mm','a4'] as const).map(v=><Pressable accessibilityRole="radio" accessibilityLabel={'Receipt paper '+v} accessibilityState={{checked:profile.receipt_paper===v}} key={v} onPress={()=>setProfile(p=>({...p,receipt_paper:v}))} style={[s.chip,profile.receipt_paper===v&&s.chipOn]}><Text style={[s.chipText,profile.receipt_paper===v&&s.chipTextOn]}>{v.toUpperCase()}</Text></Pressable>)}</View></View>
    <View style={s.panel}>
      <Text style={s.section}>Garment tag printer</Text>
      <Text style={s.help}>Browser mode uses the printer installed in Windows/macOS and is the broadest option. Use the phone/tablet web browser for system printing; AirPrint/Mopria availability depends on the printer and device. Native apps can share raw commands but do not open system print dialogs. ZPL and TSPL modes generate raw command files for compatible label printers or local print utilities.</Text>
      <Text style={s.label}>Printing mode</Text><View style={s.chips}>{[["browser","Browser / OS Driver"],["zpl","ZPL"],["tspl","TSPL"]].map(([v,label])=><Pressable accessibilityRole="radio" accessibilityLabel={"Printer mode "+v} accessibilityState={{checked:profile.printer_mode===v}} key={v} onPress={()=>setProfile(p=>({...p,printer_mode:v as HardwareProfile["printer_mode"]}))} style={[s.chip,profile.printer_mode===v&&s.chipOn]}><Text style={[s.chipText,profile.printer_mode===v&&s.chipTextOn]}>{label}</Text></Pressable>)}</View>
      <Text style={s.label}>Printer DPI</Text><View style={s.chips}>{[203,300].map(v=><Pressable key={v} onPress={()=>setProfile(p=>({...p,printer_dpi:v as 203|300}))} style={[s.chip,profile.printer_dpi===v&&s.chipOn]}><Text style={[s.chipText,profile.printer_dpi===v&&s.chipTextOn]}>{v} dpi</Text></Pressable>)}</View>
      <View style={s.formRow}><Field label="Label width (mm)"><TextInput style={s.input} keyboardType="decimal-pad" accessibilityLabel="Label width (mm)" value={String(profile.label_width_mm)} onChangeText={v=>setProfile(p=>({...p,label_width_mm:Number(v)}))}/></Field><Field label="Label height (mm)"><TextInput style={s.input} keyboardType="decimal-pad" accessibilityLabel="Label height (mm)" value={String(profile.label_height_mm)} onChangeText={v=>setProfile(p=>({...p,label_height_mm:Number(v)}))}/></Field><Field label="Gap (mm)"><TextInput style={s.input} keyboardType="decimal-pad" accessibilityLabel="Gap (mm)" value={String(profile.label_gap_mm)} onChangeText={v=>setProfile(p=>({...p,label_gap_mm:Number(v)}))}/></Field></View>
      <View style={s.note}><Text style={s.noteTitle}>Compatibility note</Text><Text style={s.help}>Web browsers normally cannot send unrestricted raw USB printer commands directly. Use Browser/OS Driver for universal printing, or a vendor/local bridge for direct ZPL/TSPL output.</Text></View>
    </View>

    <View style={s.panel}><Text style={s.section}>Calibration and buying guidance</Text><Text style={s.help}>A common economical tag option is a 203 dpi desktop label printer supporting standard ZPL or TSPL, with replaceable media and a local driver. Start with 50 × 25 mm temporary tags; test one label at actual size before a batch. For washing, dry-cleaning or heat-sealing, verify compatible durable media and hardware before buying. Standard thermal paper is not a washable garment tag.</Text><Pressable accessibilityRole="button" style={s.rawTest} onPress={()=>{try{openLabelPrint('FabClean calibration',[{code:'FC-TEST-001',order:'CALIBRATION',line1:profile.label_width_mm+' x '+profile.label_height_mm+' mm',line2:'Check barcode and edges'}],profile);setErr('');}catch(e:any){setErr(e.message);}}}><Text>Preview calibration label</Text></Pressable></View>
    {err?<Text style={s.err}>{err}</Text>:null}{saved?<Text style={s.ok}>{saved}</Text>:null}
    <Pressable accessibilityRole="button" accessibilityState={{disabled:!ready||busy}} disabled={!ready||busy} onPress={save} style={s.saveBtn}><Text style={s.saveText}>{busy?"Saving…":"Save Hardware Profile"}</Text></Pressable>
  </ScrollView>;
}

function Field({label,children}:{label:string;children:any}){return <View style={{flex:1,minWidth:170}}><Text style={s.label}>{label}</Text>{children}</View>}

const s=themedStyles({
  page:{padding:20,maxWidth:980,width:"100%",alignSelf:"center",gap:16},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink},sub:{color:colors.muted,marginTop:5},
  panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},section:{fontSize:20,fontWeight:"900",color:colors.ink},help:{fontSize:12,lineHeight:19,color:colors.muted,marginTop:4},formRow:{flexDirection:"row",gap:10,flexWrap:"wrap"},label:{fontSize:10,fontWeight:"900",letterSpacing:.7,color:colors.muted,textTransform:"uppercase",marginTop:13,marginBottom:6},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11,backgroundColor:"#fff"},toggle:{marginTop:12,backgroundColor:colors.soft,borderRadius:12,padding:12,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},toggleTitle:{fontWeight:"900",color:colors.ink},preview:{fontWeight:"800",color:colors.primary,marginTop:8},
  rawTest:{padding:12,borderWidth:1,borderColor:colors.border,borderRadius:10,marginTop:12},chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:11,paddingVertical:8},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},note:{backgroundColor:colors.softGold,borderRadius:12,padding:12,marginTop:14},noteTitle:{fontWeight:"900",color:colors.ink},saveBtn:{alignSelf:"flex-start",backgroundColor:colors.primary,borderRadius:12,paddingHorizontal:18,paddingVertical:12},saveText:{color:"#fff",fontWeight:"900"},err:{color:colors.danger},ok:{color:colors.success,fontWeight:"800"}
});
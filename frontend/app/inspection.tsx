import { useEffect, useMemo, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { ArrowLeft, Camera, CheckCircle, Sparkle, Trash } from "phosphor-react-native";
import { api, API_BASE } from "@/src/api";
import { colors } from "@/src/theme";

type Line={service_id:string;service_name:string;quantity:number;unit_price:number;unit_label:string;barcode_value?:string|null};
type Order={id:string;order_number:string;customer:{name:string;phone:string};items:Line[]};
type Inspection={order_id:string;item_barcode:string;tags:string[];condition_notes:string;condition_status:string;updated_at?:string};
type Photo={id:string;order_id:string;item_barcode?:string|null;phase:string;filename:string;content_type:string;created_at?:string};

const TAGS=["stain","tear","missing button","loose stitching","existing damage","delicate material","color fading risk","special request"];
const PHASES=["before","inspection","after"];

export default function InspectionScreen(){
  const router=useRouter();
  const params=useLocalSearchParams<{id?:string}>();
  const id=String(params.id||"");
  const [order,setOrder]=useState<Order|null>(null);
  const [inspections,setInspections]=useState<Record<string,Inspection>>({});
  const [photos,setPhotos]=useState<Photo[]>([]);
  const [phase,setPhase]=useState("inspection");
  const [saving,setSaving]=useState("");
  const [err,setErr]=useState("");
  const [ok,setOk]=useState("");
  const [suggestions,setSuggestions]=useState<Record<string,any>>({});

  async function load(){
    if(!id)return;
    setErr("");
    try{
      const [o,i]=await Promise.all([
        api.get<Order>("/orders/"+encodeURIComponent(id)),
        api.get<{items:Inspection[];photos:Photo[]}>("/orders/"+encodeURIComponent(id)+"/inspection")
      ]);
      setOrder(o);
      setPhotos(i.photos||[]);
      const map:Record<string,Inspection>={};
      (i.items||[]).forEach(x=>map[x.item_barcode]=x);
      setInspections(map);
    }catch(e:any){setErr(e.message||"Could not load inspection");}
  }
  useEffect(()=>{load();},[id]);

  const itemRows=useMemo(()=>order?.items||[],[order]);

  function ensure(barcode:string):Inspection{
    return inspections[barcode]||{order_id:id,item_barcode:barcode,tags:[],condition_notes:"",condition_status:"not_inspected"};
  }
  function toggleTag(barcode:string,tag:string){
    const current=ensure(barcode);
    const tags=current.tags.includes(tag)?current.tags.filter(x=>x!==tag):[...current.tags,tag];
    setInspections(v=>({...v,[barcode]:{...current,tags,condition_status:"inspected"}}));
  }
  function setNotes(barcode:string,condition_notes:string){
    const current=ensure(barcode);
    setInspections(v=>({...v,[barcode]:{...current,condition_notes,condition_status:"inspected"}}));
  }
  async function suggest(barcode:string,item:Line){const current=ensure(barcode);setErr("");try{const x=await api.post<any>("/ai/orders/"+id+"/inspection-suggest",{notes:current.condition_notes,service_name:item.service_name});setSuggestions(v=>({...v,[barcode]:x}));}catch(e:any){setErr(e.message||"Could not generate inspection suggestion");}}
  function applySuggestion(barcode:string){const x=suggestions[barcode];if(!x)return;const current=ensure(barcode);const tags=Array.from(new Set([...(current.tags||[]),...(x.suggested_tags||[])]));const extra=(x.handling_suggestions||[]).join(" ");setInspections(v=>({...v,[barcode]:{...current,tags,condition_notes:[current.condition_notes,extra].filter(Boolean).join(" "),condition_status:"inspected"}}));setOk("AI suggestion applied locally. Save Inspection to confirm.");}
  async function saveItem(barcode:string){
    const current=ensure(barcode);setSaving(barcode);setErr("");setOk("");
    try{
      const saved=await api.put<Inspection>("/orders/"+id+"/inspection/"+encodeURIComponent(barcode),current);
      setInspections(v=>({...v,[barcode]:saved}));setOk("Inspection saved");
    }catch(e:any){setErr(e.message||"Could not save inspection");}
    finally{setSaving("");}
  }

  async function addPhoto(itemBarcode?:string|null){
    setErr("");setOk("");
    try{
      const result=await ImagePicker.launchImageLibraryAsync({
        mediaTypes:["images"] as any,
        quality:.75,
        base64:true
      });
      if(result.canceled)return;
      const asset=result.assets[0];
      if(!asset.base64)throw new Error("Could not read selected photo");
      await api.post<Photo>("/orders/"+id+"/photos",{
        item_barcode:itemBarcode||null,
        phase,
        filename:asset.fileName||"inspection-photo.jpg",
        content_type:asset.mimeType||"image/jpeg",
        data_base64:asset.base64
      });
      setOk("Photo added");await load();
    }catch(e:any){setErr(e.message||"Could not add photo");}
  }
  async function removePhoto(photo:Photo){
    setErr("");setOk("");
    try{await api.delete("/orders/"+id+"/photos/"+photo.id);setOk("Photo removed");await load();}
    catch(e:any){setErr(e.message||"Could not remove photo");}
  }

  if(!order)return <View style={s.loading}><Text>{err||"Loading inspection…"}</Text></View>;

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push({pathname:"/order-detail",params:{id}})} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Order</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Inspection</Text></View>
    </View>

    <View style={s.header}>
      <View><Text style={s.kicker}>INSPECTION</Text><Text style={s.title}>{order.order_number}</Text><Text style={s.sub}>{order.customer.name} · {order.customer.phone}</Text></View>
      <View><Text style={s.label}>PHOTO PHASE</Text><View style={s.phaseRow}>{PHASES.map(x=><Pressable key={x} onPress={()=>setPhase(x)} style={[s.phaseChip,phase===x&&s.phaseChipOn]}><Text style={[s.phaseText,phase===x&&s.phaseTextOn]}>{x.toUpperCase()}</Text></Pressable>)}</View></View>
    </View>

    {err?<Text style={s.err}>{err}</Text>:null}{ok?<View style={s.okRow}><CheckCircle size={16} color={colors.success}/><Text style={s.ok}>{ok}</Text></View>:null}

    {itemRows.length===0?<View style={s.panel}><Text style={s.empty}>No itemized services are available yet. Finalize itemization before per-item inspection.</Text><Pressable style={s.photoBtn} onPress={()=>addPhoto(null)}><Camera size={17} color="#fff"/><Text style={s.photoText}>Add Order Photo</Text></Pressable></View>:
    itemRows.map((item,i)=>{
      const barcode=item.barcode_value||("ITEM-"+(i+1));
      const inspection=ensure(barcode);
      const itemPhotos=photos.filter(p=>p.item_barcode===barcode);
      return <View key={barcode} style={s.panel}>
        <View style={s.itemHead}><View><Text style={s.itemName}>{item.service_name}</Text><Text style={s.meta}>{barcode} · Qty {item.quantity}</Text></View><Text style={[s.status,inspection.condition_status==="inspected"&&s.statusDone]}>{inspection.condition_status==="inspected"?"Inspected":"Pending"}</Text></View>
        <Text style={s.label}>Condition tags</Text>
        <View style={s.tags}>{TAGS.map(tag=><Pressable key={tag} onPress={()=>toggleTag(barcode,tag)} style={[s.tag,inspection.tags.includes(tag)&&s.tagOn]}><Text style={[s.tagText,inspection.tags.includes(tag)&&s.tagTextOn]}>{tag}</Text></Pressable>)}</View>
        <Text style={s.label}>Condition notes</Text>
        <TextInput style={s.notes} multiline value={inspection.condition_notes} onChangeText={v=>setNotes(barcode,v)} placeholder="Describe stain location, existing damage, material risk, special handling…"/>
        <View style={s.actions}><Pressable style={s.aiBtn} onPress={()=>suggest(barcode,item)}><Text style={s.aiBtnText}>Suggest with AI</Text></Pressable><Pressable style={s.saveBtn} onPress={()=>saveItem(barcode)} disabled={saving===barcode}><Text style={s.saveText}>{saving===barcode?"Saving…":"Save Inspection"}</Text></Pressable><Pressable style={s.photoBtn} onPress={()=>addPhoto(barcode)}><Camera size={17} color="#fff"/><Text style={s.photoText}>Add {phase} photo</Text></Pressable></View>
        {suggestions[barcode]?<View style={s.aiBox}><Text style={s.aiTitle}>Suggested review</Text><Text style={s.meta}>{(suggestions[barcode].suggested_tags||[]).length?"Tags: "+suggestions[barcode].suggested_tags.join(", "):"No obvious condition tags detected."}</Text>{(suggestions[barcode].handling_suggestions||[]).map((x:string)=><Text key={x} style={s.meta}>• {x}</Text>)}<Pressable onPress={()=>applySuggestion(barcode)}><Text style={s.aiApply}>Apply suggestion</Text></Pressable></View>:null}{itemPhotos.length?<View style={s.photoGrid}>{itemPhotos.map(photo=><View key={photo.id} style={s.photoCard}><Image source={{uri:API_BASE+"/api/orders/"+id+"/photos/"+photo.id}} style={s.photo}/><View style={s.photoFoot}><Text style={s.photoPhase}>{photo.phase}</Text><Pressable onPress={()=>removePhoto(photo)}><Trash size={17} color={colors.danger}/></Pressable></View></View>)}</View>:null}
      </View>
    })}

    {photos.filter(p=>!p.item_barcode).length?<View style={s.panel}><Text style={s.panelTitle}>Order-level photos</Text><View style={s.photoGrid}>{photos.filter(p=>!p.item_barcode).map(photo=><View key={photo.id} style={s.photoCard}><Image source={{uri:API_BASE+"/api/orders/"+id+"/photos/"+photo.id}} style={s.photo}/><View style={s.photoFoot}><Text style={s.photoPhase}>{photo.phase}</Text><Pressable onPress={()=>removePhoto(photo)}><Trash size={17} color={colors.danger}/></Pressable></View></View>)}</View></View>:null}
  </ScrollView>;
}

const s=StyleSheet.create({
  loading:{padding:30},page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"800",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:24,flexDirection:"row",justifyContent:"space-between",gap:20,alignItems:"center",flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",letterSpacing:1.3,color:colors.primary},title:{fontSize:30,fontWeight:"900",color:colors.ink},sub:{color:colors.muted,marginTop:4},
  panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},panelTitle:{fontSize:18,fontWeight:"900",color:colors.ink},itemHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:12},itemName:{fontSize:18,fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:3},status:{fontSize:11,fontWeight:"900",color:colors.accentDark,backgroundColor:colors.softGold,paddingHorizontal:9,paddingVertical:5,borderRadius:999},statusDone:{color:colors.success,backgroundColor:colors.primarySoft},
  label:{fontSize:10,fontWeight:"900",letterSpacing:.8,color:colors.muted,textTransform:"uppercase",marginTop:14,marginBottom:7},tags:{flexDirection:"row",flexWrap:"wrap",gap:7},tag:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:10,paddingVertical:8},tagOn:{backgroundColor:colors.primary,borderColor:colors.primary},tagText:{fontSize:12,fontWeight:"800",color:colors.ink},tagTextOn:{color:"#fff"},notes:{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,minHeight:90,textAlignVertical:"top"},
  phaseRow:{flexDirection:"row",gap:6,flexWrap:"wrap"},phaseChip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:10,paddingVertical:7,backgroundColor:"#fff"},phaseChipOn:{backgroundColor:colors.ink,borderColor:colors.ink},phaseText:{fontSize:10,fontWeight:"900",color:colors.ink},phaseTextOn:{color:"#fff"},
  actions:{flexDirection:"row",gap:9,marginTop:12,flexWrap:"wrap"},aiBtn:{borderWidth:1,borderColor:colors.primary,borderRadius:11,paddingHorizontal:14,paddingVertical:11},aiBtnText:{color:colors.primary,fontWeight:"900"},aiBox:{backgroundColor:colors.primarySoft,borderRadius:12,padding:12,marginTop:12},aiTitle:{fontWeight:"900",color:colors.ink,marginBottom:4},aiApply:{fontWeight:"900",color:colors.primary,marginTop:8},saveBtn:{backgroundColor:colors.primary,borderRadius:11,paddingHorizontal:14,paddingVertical:11},saveText:{color:"#fff",fontWeight:"900"},photoBtn:{backgroundColor:colors.ink,borderRadius:11,paddingHorizontal:14,paddingVertical:11,flexDirection:"row",gap:7,alignItems:"center"},photoText:{color:"#fff",fontWeight:"900"},
  photoGrid:{flexDirection:"row",flexWrap:"wrap",gap:10,marginTop:14},photoCard:{width:190,borderWidth:1,borderColor:colors.border,borderRadius:12,overflow:"hidden",backgroundColor:colors.soft},photo:{width:"100%",height:140},photoFoot:{padding:8,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},photoPhase:{fontSize:10,fontWeight:"900",textTransform:"uppercase",color:colors.primary},empty:{color:colors.muted},err:{color:colors.danger},okRow:{flexDirection:"row",alignItems:"center",gap:6},ok:{color:colors.success,fontWeight:"800"}
});

import { useEffect, useMemo, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Sparkle } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";
import { imageForCategory } from "@/src/service-media";

type Variant={id:string;name:string;price:number;active:boolean};
type Modifier={id:string;name:string;amount:number;amount_type:"flat"|"percent";active:boolean};
type Service={id:string;category:string;name:string;description:string;pricing_type:string;base_price:number;minimum_price?:number;unit_label:string;turnaround_hours?:number;taxable?:boolean;tax_rate?:number;express_enabled?:boolean;express_surcharge_percent?:number;variants?:Variant[];modifiers?:Modifier[]};

export default function Services(){
  const router=useRouter();
  const params=useLocalSearchParams<{category?:string}>();
  const [items,setItems]=useState<Service[]>([]);
  const [active,setActive]=useState(String(params.category||"All"));
  useEffect(()=>{api.get<{services:Service[]}>("/services").then(x=>setItems(x.services)).catch(()=>{});},[]);
  useEffect(()=>{if(params.category)setActive(String(params.category));},[params.category]);
  const categories=useMemo(()=>["All",...Array.from(new Set(items.map(x=>x.category)))],[items]);
  const normalize=(v:string)=>String(v||"").trim().toLowerCase();
  const aliases:Record<string,string[]>={
    "wash & fold":["wash & fold","laundry"],
    "dry cleaning":["dry cleaning"],
    "shoes":["shoes","shoe"],
    "bags":["bags","bag"],
    "curtains":["curtains","curtain"],
    "bedding":["bedding","household"]
  };
  const requested=normalize(active);
  const accepted=requested==="all"?[]:(aliases[requested]||[requested]);
  const visible=active==="All"?items:items.filter(x=>accepted.includes(normalize(x.category)));
  const effectiveVisible=visible.length?visible:(active==="All"?items:items.filter(x=>{
    const text=normalize(x.category+" "+x.name);
    return accepted.some(a=>text.includes(a));
  }));

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean</Text></View>
    </View>

    <View style={s.header}>
      <Text style={s.kicker}>SERVICE CATALOG</Text>
      <Text style={s.title}>Professional care for every item</Text>
      <Text style={s.sub}>Browse services and pricing. Categories and prices are configurable by the laundry administrator.</Text>
    </View>

    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filters}>
      {categories.map(c=><Pressable key={c} onPress={()=>setActive(c)} style={[s.filter,active===c&&s.filterOn]}><Text style={[s.filterText,active===c&&s.filterTextOn]}>{c}</Text></Pressable>)}
    </ScrollView>

    <View style={s.grid}>
      {effectiveVisible.map(x=><View key={x.id} style={s.card}>
        <Image source={{uri:imageForCategory(x.category)}} style={s.image} resizeMode="cover"/>
        <View style={s.body}>
          <Text style={s.cat}>{x.category}</Text>
          <Text style={s.name}>{x.name}</Text>
          <Text style={s.desc}>{x.description}</Text>
          {x.variants?.filter(v=>v.active).length?<View style={s.detailBox}><Text style={s.detailLabel}>Variants</Text>{x.variants.filter(v=>v.active).slice(0,3).map(v=><Text key={v.id} style={s.detailText}>{v.name} · {"$"+v.price.toFixed(2)}</Text>)}</View>:null}
          {x.modifiers?.filter(m=>m.active).length?<View style={s.detailBox}><Text style={s.detailLabel}>Common upcharges</Text>{x.modifiers.filter(m=>m.active).slice(0,3).map(m=><Text key={m.id} style={s.detailText}>{m.name} · {m.amount_type==="percent"?m.amount+"%":"+$"+m.amount.toFixed(2)}</Text>)}</View>:null}
          {(x.minimum_price||x.taxable||x.express_enabled)?<View style={s.flags}>
            {x.minimum_price?<Text style={s.flag}>{"Min $"+x.minimum_price.toFixed(2)}</Text>:null}
            {x.taxable?<Text style={s.flag}>{(x.tax_rate||0).toFixed(2)+"% tax"}</Text>:null}
            {x.express_enabled?<Text style={s.flag}>{"Express +"+(x.express_surcharge_percent||0).toFixed(0)+"%"}</Text>:null}
          </View>:null}
          <View style={s.bottom}>
            <Text style={s.price}>{x.pricing_type==="quote"?"Quote required":"$"+x.base_price.toFixed(2)+(x.unit_label?" / "+x.unit_label:"")}</Text>
            <Text style={s.turn}>{x.turnaround_hours?x.turnaround_hours+"h":"Standard"}</Text>
          </View>
        </View>
      </View>)}
    </View>
    {effectiveVisible.length===0?<View style={s.emptyState}><Text style={s.emptyTitle}>No services found for {active}</Text><Text style={s.emptyCopy}>Choose another category or use All to view the complete service catalog.</Text></View>:null}

    <Pressable style={s.cta} onPress={()=>router.push("/walk-in")}><Text style={s.ctaText}>Create Order →</Text></Pressable>
  </ScrollView>
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1100,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"700",color:colors.ink},brand:{flexDirection:"row",alignItems:"center",gap:6},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:24},kicker:{fontSize:11,fontWeight:"900",letterSpacing:1.5,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:4},sub:{color:colors.muted,marginTop:7,maxWidth:700,lineHeight:21},
  filters:{gap:8,paddingVertical:2},filter:{paddingHorizontal:15,paddingVertical:10,borderRadius:999,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border},filterOn:{backgroundColor:colors.primary,borderColor:colors.primary},filterText:{fontWeight:"800",color:colors.ink},filterTextOn:{color:"#fff"},
  grid:{flexDirection:"row",flexWrap:"wrap",gap:14},card:{width:330,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,overflow:"hidden"},image:{width:"100%",height:180},body:{padding:17},cat:{fontSize:10,fontWeight:"900",letterSpacing:1.2,color:colors.primary,textTransform:"uppercase"},name:{fontSize:20,fontWeight:"900",color:colors.ink,marginTop:3},desc:{color:colors.muted,marginTop:6,lineHeight:20,minHeight:40},detailBox:{backgroundColor:colors.soft,borderRadius:10,padding:10,marginTop:10},detailLabel:{fontSize:9,fontWeight:"900",letterSpacing:.8,color:colors.primary,textTransform:"uppercase",marginBottom:4},detailText:{fontSize:12,color:colors.ink,marginTop:2},flags:{flexDirection:"row",flexWrap:"wrap",gap:6,marginTop:10},flag:{fontSize:10,fontWeight:"800",color:colors.primaryDark,backgroundColor:colors.primarySoft,paddingHorizontal:8,paddingVertical:5,borderRadius:999},bottom:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",marginTop:16},price:{fontWeight:"900",color:colors.primary,fontSize:16},turn:{fontSize:12,fontWeight:"800",color:colors.muted,backgroundColor:colors.soft,paddingHorizontal:9,paddingVertical:5,borderRadius:999},
  emptyState:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:22},emptyTitle:{fontSize:17,fontWeight:"900",color:colors.ink},emptyCopy:{color:colors.muted,marginTop:5},cta:{alignSelf:"flex-start",backgroundColor:colors.primary,paddingHorizontal:20,paddingVertical:14,borderRadius:14,marginTop:4},ctaText:{color:"#fff",fontWeight:"900"}
});

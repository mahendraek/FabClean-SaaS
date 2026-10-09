import { useEffect, useState } from "react";

import { useRouter } from "expo-router";
import { Alert, Image, ScrollView, StyleSheet, Text, Pressable, View } from "react-native";
import { CheckCircle, Clock, Package, Sneaker, Sparkle, Truck } from "phosphor-react-native";
import { colors } from "@/src/theme";
import { api, getStoredStaff, signOut } from "@/src/api";
import { serviceImages } from "@/src/service-media";

const services = [
  {name:"Wash & Fold", image:serviceImages["Wash & Fold"], copy:"Everyday laundry by weight"},
  {name:"Dry Cleaning", image:serviceImages["Dry Cleaning"], copy:"Garments & formal wear"},
  {name:"Shoes", image:serviceImages["Shoes"], copy:"Sneaker & leather care"},
  {name:"Bags", image:serviceImages["Bags"], copy:"Handbags & backpacks"},
  {name:"Curtains", image:serviceImages["Curtains"], copy:"Panels, drapes & sheers"},
  {name:"Bedding", image:serviceImages["Bedding"], copy:"Comforters & linens"}
];

function Nav({settings}:{settings:any}){
  const router=useRouter();
  const staff=getStoredStaff();
  const canAdmin=!!staff&&(["owner","manager"].includes(staff.role)||(staff.assignments||[]).some((a:any)=>["super_admin","brand_admin","store_manager"].includes(a.role)));
  return <View style={s.nav}>
    <Pressable onPress={()=>router.push("/")} style={s.logoWrap}>
      <View style={s.logoMark}><Sparkle size={18} color="#fff" weight="fill"/></View>
      <View><Text style={s.logo}>FabClean</Text><Text style={s.logoSub}>Laundry Operations</Text></View>
    </Pressable>
    <View style={s.navLinks}>
      <Pressable onPress={()=>router.push("/walk-in")}><Text style={s.navText}>Create Order</Text></Pressable><Pressable onPress={()=>router.push("/orders")}><Text style={s.navText}>Find Order</Text></Pressable>
      <Pressable onPress={()=>router.push("/customers")}><Text style={s.navText}>Customers</Text></Pressable>
      {settings.pickup_enabled||settings.delivery_enabled?<Pressable onPress={()=>router.push("/pickup-schedule")}><Text style={s.navText}>Pickup / Delivery Schedule</Text></Pressable>:null}
      <Pressable onPress={()=>router.push("/services")}><Text style={s.navText}>Services</Text></Pressable>
      {canAdmin?<Pressable onPress={()=>router.push("/admin")}><Text style={s.navText}>Admin</Text></Pressable>:null}{staff?<Pressable onPress={()=>{void signOut().then(()=>router.replace("/sign-in")).catch(error=>Alert.alert("Sign out failed",error.message));}}><Text style={s.navText}>{staff.name} · Sign out</Text></Pressable>:<Pressable onPress={()=>router.push("/sign-in")}><Text style={s.navText}>Staff Sign In</Text></Pressable>}
    </View>
  </View>
}

export default function Home() {
  const router = useRouter();
  const [dashboard,setDashboard]=useState<any>(null);
  const [settings,setSettings]=useState<any>({});
  useEffect(()=>{
    api.get<any>("/settings").then(setSettings).catch(()=>{});
    api.get<any>("/dashboard").then(data=>{
      setDashboard(data);
    }).catch(()=>{});
  },[]);
  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <Nav settings={settings}/>
    <View style={s.hero}>
      <View style={s.heroCopy}>
        <View style={s.badge}><CheckCircle size={15} color={colors.primary}/><Text style={s.badgeText}>Built for modern laundry operations</Text></View>
        <Text style={s.eyebrow}>FABRIC CARE, SIMPLIFIED</Text>
        <Text style={s.title}>From drop-off to ready-for-pickup, keep every order moving.</Text>
        <Text style={s.subtitle}>Create an order, identify the customer, add garments, and let FabClean generate tracking barcodes automatically.</Text>
        <View style={s.actions}>
          <Pressable style={s.primary} onPress={() => router.push("/walk-in")}><Text style={s.primaryText}>+ Create Order</Text></Pressable>
          <Pressable style={s.secondary} onPress={() => router.push("/orders")}><Text style={s.secondaryText}>Find Order</Text></Pressable>
        </View>
      </View>
      <View style={s.heroVisual}>
        <Image source={{uri:serviceImages["Wash & Fold"]}} style={s.heroImage} resizeMode="cover"/>
        <View style={s.heroShade}/>
        <View style={s.floatingCard}><Clock size={20} color={colors.primary}/><View><Text style={s.floatTitle}>Fast counter flow</Text><Text style={s.floatCopy}>Create, tag and track orders</Text></View></View>
      </View>
    </View>

    <View style={s.stats}>
      <View style={s.stat}><Package size={22} color={colors.primary}/><Text style={s.statValue}>{dashboard?.total_orders??"—"}</Text><Text style={s.statLabel}>Total orders</Text></View>
      <View style={s.stat}><Clock size={22} color={colors.primary}/><Text style={s.statValue}>{dashboard?.processing??"—"}</Text><Text style={s.statLabel}>In processing</Text></View>
      <View style={s.stat}><CheckCircle size={22} color={colors.success}/><Text style={s.statValue}>{dashboard?.ready_for_pickup??"—"}</Text><Text style={s.statLabel}>Ready for pickup</Text></View>
{settings.pickup_enabled||settings.delivery_enabled?<View style={s.stat}><Truck size={22} color={colors.navy}/><Text style={s.statValue}>{dashboard?.pickup_delivery_orders??"—"}</Text><Text style={s.statLabel}>Pickup / delivery</Text></View>:null}
      <View style={s.stat}><Text style={s.statValue}>{dashboard?"$"+Number(dashboard.revenue||0).toFixed(2):"—"}</Text><Text style={s.statLabel}>Paid revenue</Text></View>
      <View style={s.stat}><Text style={s.statValue}>{dashboard?.payment_pending??"—"}</Text><Text style={s.statLabel}>Payment pending</Text></View>
      <View style={s.stat}><Text style={s.statValue}>{dashboard?"$"+Number(dashboard.average_order_value||0).toFixed(2):"—"}</Text><Text style={s.statLabel}>Average order</Text></View>
    </View>

    <View style={s.sectionHeader}>
      <View><Text style={s.sectionKicker}>SERVICES</Text><Text style={s.section}>Everything your laundry handles</Text></View>
      <Pressable onPress={()=>router.push("/services")}><Text style={s.link}>View pricing →</Text></Pressable>
    </View>
    <View style={s.grid}>
      {services.map(({name,image,copy}) => <Pressable key={name} style={s.card} onPress={() => router.push({pathname:"/services",params:{category:name}})}>
        <Image source={{uri:image}} style={s.cardImage} resizeMode="cover"/>
        <View style={s.cardBody}><Text style={s.cardTitle}>{name}</Text><Text style={s.cardCopy}>{copy}</Text></View>
      </Pressable>)}
    </View>

    {settings.offers_enabled!==false?<View style={s.promo}>
      <View style={{flex:1}}>
        <Text style={s.promoEyebrow}>WELCOME OFFER</Text>
        <Text style={s.promoTitle}>Customer offers available</Text>
        <Text style={s.promoCopy}>Current promotions are managed by the laundry administrator and applied when eligible.</Text>
      </View>
      <View style={s.promoBubble}><Sneaker size={42} color={colors.accentDark}/></View>
    </View>:null}

    <View style={s.workflow}>
      <Text style={s.sectionKicker}>WORKFLOW</Text><Text style={s.section}>A clearer day at the counter</Text>
      <View style={s.workflowRow}>
        {["Receive","Inspect","Clean","Quality Check","Ready","Collected"].map((x,i)=><View key={x} style={s.step}><Text style={s.stepNum}>{String(i+1).padStart(2,"0")}</Text><Text style={s.stepText}>{x}</Text></View>)}
      </View>
    </View>
  </ScrollView>;
}

const s=StyleSheet.create({
  page:{padding:20,maxWidth:1180,width:"100%",alignSelf:"center",gap:20},
  nav:{minHeight:70,flexDirection:"row",alignItems:"center",justifyContent:"space-between",paddingVertical:8,gap:12,flexWrap:"wrap"},
  logoWrap:{flexDirection:"row",alignItems:"center",gap:10},logoMark:{width:40,height:40,borderRadius:12,backgroundColor:colors.primary,alignItems:"center",justifyContent:"center"},
  logo:{fontSize:20,fontWeight:"900",color:colors.ink},logoSub:{fontSize:10,color:colors.muted,letterSpacing:1.1,textTransform:"uppercase"},
  navLinks:{flexDirection:"row",gap:16,flexWrap:"wrap",alignItems:"center"},navText:{fontWeight:"700",color:colors.ink},
  hero:{backgroundColor:colors.surface,borderRadius:28,borderWidth:1,borderColor:colors.border,padding:28,flexDirection:"row",flexWrap:"wrap",gap:24,overflow:"hidden"},
  heroCopy:{flex:1,minWidth:280,justifyContent:"center"},badge:{alignSelf:"flex-start",flexDirection:"row",gap:6,alignItems:"center",backgroundColor:colors.primarySoft,paddingHorizontal:10,paddingVertical:7,borderRadius:999},badgeText:{fontSize:12,fontWeight:"700",color:colors.primaryDark},
  eyebrow:{fontSize:12,fontWeight:"900",letterSpacing:1.8,color:colors.primary,marginTop:24},title:{fontSize:38,lineHeight:45,fontWeight:"900",color:colors.ink,marginTop:8,maxWidth:680},subtitle:{fontSize:17,lineHeight:27,color:colors.muted,marginTop:14,maxWidth:650},
  actions:{flexDirection:"row",flexWrap:"wrap",gap:10,marginTop:24},primary:{backgroundColor:colors.primary,borderRadius:14,paddingVertical:14,paddingHorizontal:20},primaryText:{color:"#fff",fontWeight:"800"},secondary:{backgroundColor:colors.surface,borderWidth:1,borderColor:colors.border,borderRadius:14,paddingVertical:14,paddingHorizontal:20},secondaryText:{color:colors.primary,fontWeight:"800"},
  heroVisual:{width:360,minHeight:300,borderRadius:26,overflow:"hidden",position:"relative",backgroundColor:colors.softBlue},heroImage:{width:"100%",height:"100%",position:"absolute"},heroShade:{position:"absolute",top:0,right:0,bottom:0,left:0,backgroundColor:"rgba(4,36,32,0.08)"},
  floatingCard:{position:"absolute",bottom:18,left:15,right:15,backgroundColor:"rgba(255,255,255,.96)",borderRadius:15,padding:12,flexDirection:"row",gap:10,alignItems:"center",borderWidth:1,borderColor:colors.border},floatTitle:{fontWeight:"800",color:colors.ink},floatCopy:{fontSize:12,color:colors.muted},
  stats:{flexDirection:"row",flexWrap:"wrap",gap:12},stat:{flex:1,minWidth:220,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},statValue:{fontSize:17,fontWeight:"800",color:colors.ink,marginTop:8},statLabel:{color:colors.muted,marginTop:2},
  sectionHeader:{flexDirection:"row",justifyContent:"space-between",alignItems:"flex-end",marginTop:10},sectionKicker:{fontSize:11,fontWeight:"900",letterSpacing:1.5,color:colors.primary},section:{fontSize:26,fontWeight:"900",color:colors.ink,marginTop:3},link:{fontWeight:"800",color:colors.primary},
  grid:{flexDirection:"row",flexWrap:"wrap",gap:14},card:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,flex:1,minWidth:220,maxWidth:280,overflow:"hidden"},cardImage:{width:"100%",height:145},cardBody:{padding:16},cardTitle:{fontWeight:"900",fontSize:17,color:colors.ink},cardCopy:{fontSize:13,lineHeight:19,color:colors.muted,marginTop:5},
  promo:{backgroundColor:colors.softGold,borderRadius:24,padding:26,flexDirection:"row",alignItems:"center",gap:20},promoEyebrow:{fontSize:11,fontWeight:"900",letterSpacing:1.5,color:colors.accentDark},promoTitle:{fontSize:25,fontWeight:"900",color:colors.ink,marginTop:5},promoCopy:{color:colors.muted,marginTop:7,maxWidth:650,lineHeight:21},promoBubble:{width:86,height:86,borderRadius:999,backgroundColor:"#fff",alignItems:"center",justifyContent:"center"},
  workflow:{backgroundColor:"#fff",borderRadius:24,borderWidth:1,borderColor:colors.border,padding:24},workflowRow:{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:18},step:{flex:1,minWidth:130,backgroundColor:colors.soft,borderRadius:14,padding:14},stepNum:{fontSize:11,fontWeight:"900",color:colors.primary},stepText:{fontWeight:"800",color:colors.ink,marginTop:6}
});

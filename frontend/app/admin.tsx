import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, ChartBar, Gear, HardDrives, Plus, Sparkle, Trash, Truck, UsersThree, Wallet } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Variant={id:string;name:string;price:number;active:boolean};
type Modifier={id:string;name:string;amount:number;amount_type:"flat"|"percent";customer_selectable:boolean;active:boolean};
type Category={id:string;name:string;active:boolean;sort_order:number};
type Service={
  id:string;business_id?:string;category:string;name:string;description:string;
  pricing_type:"per_item"|"per_lb"|"per_kg"|"per_pair"|"per_panel"|"flat"|"starting_at"|"quote";
  base_price:number;minimum_price:number;unit_label:string;turnaround_hours:number;taxable:boolean;tax_rate:number;express_enabled:boolean;express_surcharge_percent:number;active:boolean;
  pickup_eligible:boolean;delivery_eligible:boolean;reward_eligible:boolean;subscription_eligible:boolean;
  variants:Variant[];modifiers:Modifier[];
};

const emptyService:Service={
  id:"",business_id:"fabclean",category:"Wash & Fold",name:"",description:"",
  pricing_type:"per_item",base_price:0,minimum_price:0,unit_label:"item",turnaround_hours:48,taxable:false,tax_rate:0,express_enabled:false,express_surcharge_percent:0,active:true,
  pickup_eligible:true,delivery_eligible:true,reward_eligible:true,subscription_eligible:false,
  variants:[],modifiers:[]
};

const pricingOptions=[
  ["per_item","Per item"],["per_lb","Per lb"],["per_kg","Per kg"],["per_pair","Per pair"],
  ["per_panel","Per panel"],["flat","Flat"],["starting_at","Starting at"],["quote","Quote"]
] as const;

const slugify=(v:string)=>v.toLowerCase().trim().replace(/[^a-z0-9]+/g,"-").replace(/(^-|-$)/g,"");

export default function Admin(){
  const router=useRouter();
  const [settings,setSettings]=useState<any>({});
  const [services,setServices]=useState<Service[]>([]);
  const [categories,setCategories]=useState<Category[]>([]);
  const [summary,setSummary]=useState<any>({});
  const [newCategory,setNewCategory]=useState("");
  const [selected,setSelected]=useState<Service|null>(null);
  const [draft,setDraft]=useState<Service>(emptyService);
  const [isNew,setIsNew]=useState(false);
  const [saving,setSaving]=useState(false);
  const [capabilitySaving,setCapabilitySaving]=useState("");
  const [err,setErr]=useState("");
  const [ok,setOk]=useState("");
  const [context,setContext]=useState<any>(null);

  async function load(){
    setErr("");
    try{
      const x=await api.get<{settings:any;services:Service[];categories:Category[];summary:any}>("/admin/overview");
      setSettings(x.settings||{});setServices(x.services||[]);setCategories(x.categories||[]);setSummary(x.summary||{});
    }catch(e:any){setErr(e.message||"Could not load administration data");}
  }
  useEffect(()=>{load();api.get<any>("/context").then(setContext).catch(()=>{});},[]);

  async function toggleSetting(k:string){
    if(capabilitySaving)return;
    const previous=!!settings[k];
    const nextValue=!previous;
    setErr("");setOk("");setCapabilitySaving(k);
    setSettings((v:any)=>({...v,[k]:nextValue}));
    try{
      const saved=await api.put<any>("/settings",{[k]:nextValue});
      setSettings(saved);
      setOk("Business capability updated");
    }catch(e:any){
      setSettings((v:any)=>({...v,[k]:previous}));
      setErr(e.message||"Could not save setting");
    }finally{setCapabilitySaving("");}
  }

  async function saveBusinessDetails(){
    setErr("");setOk("");
    try{
      const saved=await api.put<any>("/settings",{
        business_name:String(settings.business_name||"").trim(),
        business_address:String(settings.business_address||"").trim(),
        business_phone:String(settings.business_phone||"").trim()
      });
      setSettings(saved);setOk("Business details saved");
    }catch(e:any){setErr(e.message||"Could not save business details");}
  }

  function editService(service:Service){
    setSelected(service);setDraft(JSON.parse(JSON.stringify(service)));setIsNew(false);setErr("");setOk("");
  }
  function newService(){
    setSelected(null);setDraft({...emptyService,variants:[],modifiers:[]});setIsNew(true);setErr("");setOk("");
  }
  function setField<K extends keyof Service>(k:K,v:Service[K]){setDraft(d=>({...d,[k]:v}));}

  function addVariant(){setDraft(d=>({...d,variants:[...d.variants,{id:"variant-"+(d.variants.length+1),name:"",price:d.base_price,active:true}]}));}
  function updateVariant(i:number,patch:Partial<Variant>){setDraft(d=>({...d,variants:d.variants.map((x,j)=>j===i?{...x,...patch}:x)}));}
  function removeVariant(i:number){setDraft(d=>({...d,variants:d.variants.filter((_,j)=>j!==i)}));}

  function addModifier(){setDraft(d=>({...d,modifiers:[...d.modifiers,{id:"modifier-"+(d.modifiers.length+1),name:"",amount:0,amount_type:"flat",customer_selectable:true,active:true}]}));}
  function updateModifier(i:number,patch:Partial<Modifier>){setDraft(d=>({...d,modifiers:d.modifiers.map((x,j)=>j===i?{...x,...patch}:x)}));}
  function removeModifier(i:number){setDraft(d=>({...d,modifiers:d.modifiers.filter((_,j)=>j!==i)}));}

  async function save(){
    setSaving(true);setErr("");setOk("");
    try{
      const payload={...draft,id:(draft.id||slugify(draft.name)),base_price:Number(draft.base_price||0),turnaround_hours:Number(draft.turnaround_hours||0)};
      if(!payload.id||!payload.name.trim()||!payload.category.trim())throw new Error("Service ID, category and name are required");
      const saved=isNew
        ? await api.post<Service>("/services",payload)
        : await api.put<Service>("/services/"+encodeURIComponent(payload.id),payload);
      setDraft(saved);setSelected(saved);setIsNew(false);setOk("Service saved");
      await load();
    }catch(e:any){setErr(e.message||"Could not save service");}
    finally{setSaving(false);}
  }

  const categoryNames=useMemo(()=>categories.filter(x=>x.active).map(x=>x.name),[categories]);

  async function addCategory(){
    const name=newCategory.trim();
    if(!name)return;
    setErr("");setOk("");
    try{
      await api.post<Category>("/admin/categories",{name,active:true,sort_order:categories.length+1});
      setNewCategory("");setOk("Category added");await load();
    }catch(e:any){setErr(e.message||"Could not add category");}
  }
  async function toggleCategory(category:Category){
    setErr("");setOk("");
    try{await api.put<Category>("/admin/categories/"+category.id,{...category,active:!category.active});setOk("Category updated");await load();}
    catch(e:any){setErr(e.message||"Could not update category");}
  }
  async function renameCategory(category:Category,name:string){
    const next=name.trim();
    if(!next||next===category.name)return;
    setErr("");setOk("");
    try{await api.put<Category>("/admin/categories/"+category.id,{...category,name:next});setOk("Category renamed");await load();}
    catch(e:any){setErr(e.message||"Could not rename category");}
  }
  async function duplicateService(){
    if(!selected)return;
    setErr("");setOk("");
    try{await api.post<Service>("/services/"+selected.id+"/duplicate",{});setOk("Inactive copy created");await load();}
    catch(e:any){setErr(e.message||"Could not duplicate service");}
  }

  return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
    <View style={s.top}>
      <Pressable onPress={()=>router.push("/")} style={s.back}><ArrowLeft size={18} color={colors.ink}/><Text style={s.backText}>Home</Text></Pressable>
      <View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.brandText}>FabClean Admin</Text></View>
    </View>

    <View style={s.header}>
      <View style={{flex:1}}><Text style={s.kicker}>ADMINISTRATION</Text><Text style={s.title}>Business & Operations</Text><Text style={s.sub}>Manage the essentials here. Open specialized sections only when you need them.</Text>{context?.active_brand?<Text style={s.help}>Context: {context.active_brand.name}{context.active_store?" · "+context.active_store.name:""}</Text>:null}</View>
      <Pressable style={s.primaryAction} onPress={newService}><Plus size={18} color="#fff"/><Text style={s.primaryActionText}>New Service</Text></Pressable>
    </View>

    <View style={s.adminGrid}>
      {context?.is_super_admin?<AdminCard icon={<Sparkle size={21} color={colors.primary}/>} title="Platform & Brands" text="SuperAdmin tenant management" onPress={()=>router.push("/platform-admin")}/>:null}
      {context?.assignments?.some((a:any)=>a.role==="brand_admin")||context?.is_super_admin?<AdminCard icon={<Sparkle size={21} color={colors.primary}/>} title="Brand & Stores" text="Stores, hierarchy and locations" onPress={()=>router.push("/brand-stores")}/>:null}
      <AdminCard icon={<Truck size={21} color={colors.primary}/>} title="Pickup & Delivery" text="Coverage, slots and schedules" onPress={()=>router.push("/scheduling")}/>
      <AdminCard icon={<UsersThree size={21} color={colors.primary}/>} title="Staff & Roles" text="Access and staff permissions" onPress={()=>router.push("/staff")}/>
      <AdminCard icon={<Wallet size={21} color={colors.primary}/>} title="Financial" text="Payments and financial activity" onPress={()=>router.push("/financial")}/>
      <AdminCard icon={<ChartBar size={21} color={colors.primary}/>} title="Reports" text="Operational reporting" onPress={()=>router.push("/reports")}/>
      <AdminCard icon={<HardDrives size={21} color={colors.primary}/>} title="Hardware" text="Printers, labels and devices" onPress={()=>router.push("/hardware")}/>
      <AdminCard icon={<Gear size={21} color={colors.primary}/>} title="More Settings" text="Offers, subscriptions and login history" onPress={()=>router.push("/retention")}/>
    </View>

    <View style={s.metrics}>
      <Metric label="Services" value={summary.total||0}/>
      <Metric label="Active" value={summary.active||0}/>
      <Metric label="Inactive" value={summary.inactive||0}/>
      <Metric label="Categories" value={summary.categories||categories.length}/>
    </View>

    <View style={s.settingsPanel}>
      <Text style={s.sectionTitle}>Business details</Text>
      <Text style={s.help}>Used on printed receipts and customer-facing documents.</Text>
      <View style={s.formRow}>
        <Field label="Laundry / Business name"><TextInput style={s.input} value={settings.business_name||""} onChangeText={v=>setSettings({...settings,business_name:v})} placeholder="FabClean Laundry"/></Field>
        <Field label="Phone"><TextInput style={s.input} value={settings.business_phone||""} onChangeText={v=>setSettings({...settings,business_phone:v})} placeholder="+1 555 123 4567" keyboardType="phone-pad"/></Field>
      </View>
      <Field label="Address"><TextInput style={s.input} value={settings.business_address||""} onChangeText={v=>setSettings({...settings,business_address:v})} placeholder="123 Main St, City, State ZIP"/></Field>
      <Pressable style={[s.newBtn,{alignSelf:"flex-start",marginTop:10}]} onPress={saveBusinessDetails}><Text style={s.newText}>Save Business Details</Text></Pressable>
    </View>

    <View style={s.settingsPanel}>
      <Text style={s.sectionTitle}>Business capabilities</Text>
      <View style={s.settingsGrid}>
        {[
          ["pickup_enabled","Pickup"],["delivery_enabled","Delivery"],["rewards_enabled","Rewards"],
          ["offers_enabled","Offers"],["referrals_enabled","Referrals"],["subscriptions_enabled","Subscriptions"],["ai_assistance_enabled","AI Assistance"]
        ].map(([k,label])=><View key={k} style={s.setting}>
          <View><Text style={s.settingName}>{label}</Text><Text style={s.help}>Enable or disable independently</Text></View>
          <Switch disabled={!!capabilitySaving} value={!!settings[k]} onValueChange={()=>toggleSetting(k)}/>
        </View>)}
      </View>
    </View>

    <View style={s.settingsPanel}>
      <View style={s.catalogHeader}><Text style={s.sectionTitle}>Service categories</Text><Text style={s.help}>Rename, activate/deactivate, or add categories.</Text></View>
      <View style={s.categoryAdd}><TextInput style={s.input} placeholder="New category name" value={newCategory} onChangeText={setNewCategory} onSubmitEditing={addCategory}/><Pressable style={s.addCategoryBtn} onPress={addCategory}><Text style={s.addCategoryText}>Add Category</Text></Pressable></View>
      <View style={s.categoryGrid}>{categories.map(cat=><View key={cat.id} style={s.categoryCard}><TextInput style={[s.input,{flex:1}]} defaultValue={cat.name} onSubmitEditing={e=>renameCategory(cat,e.nativeEvent.text)}/><Switch value={cat.active} onValueChange={()=>toggleCategory(cat)}/></View>)}</View>
    </View>

    <View style={s.layout}>
      <View style={s.catalog}>
        <View style={s.catalogHeader}><Text style={s.sectionTitle}>Service catalog</Text><Text style={s.help}>{services.length} configured</Text></View>
        {services.map(service=><Pressable key={service.id} onPress={()=>editService(service)} style={[s.serviceRow,selected?.id===service.id&&s.serviceRowOn]}>
          <View style={{flex:1}}><Text style={s.serviceCat}>{service.category}</Text><Text style={s.serviceName}>{service.name}</Text><Text style={s.help}>{service.id}</Text></View>
          <View style={{alignItems:"flex-end"}}><Text style={s.price}>{service.pricing_type==="quote"?"Quote":"$"+service.base_price.toFixed(2)}</Text><Text style={[s.status,service.active?s.active:s.inactive]}>{service.active?"Active":"Inactive"}</Text></View>
        </Pressable>)}
      </View>

      <View style={s.editor}>
        {!selected&&!isNew?<View style={s.empty}><Text style={s.emptyTitle}>Select a service</Text><Text style={s.help}>Choose an existing service or create a new one.</Text></View>:
        <>
          <View style={s.editorHead}><View><Text style={s.sectionTitle}>{isNew?"Create service":"Edit service"}</Text><Text style={s.help}>{draft.id||"New ID generated from name"}</Text></View>{!isNew&&selected?<Pressable onPress={duplicateService} style={s.duplicateBtn}><Text style={s.duplicateText}>Duplicate</Text></Pressable>:null}</View>

          <View style={s.formRow}>
            <Field label="Service name"><TextInput style={s.input} value={draft.name} onChangeText={v=>setField("name",v)} placeholder="Wash & Fold"/></Field>
            <Field label="Category"><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>{categoryNames.map(cat=><Pressable key={cat} onPress={()=>setField("category",cat)} style={[s.chip,draft.category===cat&&s.chipOn]}><Text style={[s.chipText,draft.category===cat&&s.chipTextOn]}>{cat}</Text></Pressable>)}</ScrollView></Field>
          </View>
          <Field label="Service ID"><TextInput editable={isNew} style={[s.input,!isNew&&s.disabled]} value={draft.id} onChangeText={v=>setField("id",slugify(v))} placeholder="wash-fold"/></Field>
          <Field label="Description"><TextInput style={[s.input,s.multi]} multiline value={draft.description} onChangeText={v=>setField("description",v)} placeholder="Describe what is included"/></Field>

          <Text style={s.label}>Pricing type</Text>
          <View style={s.chips}>{pricingOptions.map(([value,label])=><Pressable key={value} onPress={()=>setField("pricing_type",value)} style={[s.chip,draft.pricing_type===value&&s.chipOn]}><Text style={[s.chipText,draft.pricing_type===value&&s.chipTextOn]}>{label}</Text></Pressable>)}</View>

          <View style={s.formRow}>
            <Field label="Base price"><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.base_price)} onChangeText={v=>setField("base_price",Number(v)||0)}/></Field><Field label="Minimum price"><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.minimum_price||0)} onChangeText={v=>setField("minimum_price",Number(v)||0)}/></Field>
            <Field label="Unit label"><TextInput style={s.input} value={draft.unit_label} onChangeText={v=>setField("unit_label",v)} placeholder="item, lb, pair"/></Field>
            <Field label="Turnaround hours"><TextInput style={s.input} keyboardType="number-pad" value={String(draft.turnaround_hours)} onChangeText={v=>setField("turnaround_hours",Number(v)||0)}/></Field>
          </View>
          <View style={s.formRow}><Field label="Tax rate %"><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.tax_rate||0)} onChangeText={v=>setField("tax_rate",Number(v)||0)}/></Field><Field label="Express surcharge %"><TextInput style={s.input} keyboardType="decimal-pad" value={String(draft.express_surcharge_percent||0)} onChangeText={v=>setField("express_surcharge_percent",Number(v)||0)}/></Field></View>

          <Text style={s.label}>Availability & eligibility</Text>
          <View style={s.toggleGrid}>
            <Toggle label="Active" value={draft.active} onChange={v=>setField("active",v)}/>
            <Toggle label="Pickup eligible" value={draft.pickup_eligible} onChange={v=>setField("pickup_eligible",v)}/>
            <Toggle label="Delivery eligible" value={draft.delivery_eligible} onChange={v=>setField("delivery_eligible",v)}/>
            <Toggle label="Reward eligible" value={draft.reward_eligible} onChange={v=>setField("reward_eligible",v)}/>
            <Toggle label="Subscription eligible" value={draft.subscription_eligible} onChange={v=>setField("subscription_eligible",v)}/><Toggle label="Taxable" value={draft.taxable} onChange={v=>setField("taxable",v)}/><Toggle label="Express service" value={draft.express_enabled} onChange={v=>setField("express_enabled",v)}/>
          </View>

          <View style={s.subHead}><Text style={s.sectionTitle}>Variants</Text><Pressable onPress={addVariant} style={s.addSmall}><Plus size={15} color={colors.primary}/><Text style={s.addSmallText}>Add variant</Text></Pressable></View>
          {draft.variants.length===0?<Text style={s.help}>Optional sizes, garment types or service levels with their own price.</Text>:draft.variants.map((v,i)=><View key={i} style={s.repeatRow}>
            <TextInput style={[s.input,{flex:1}]} placeholder="Variant name" value={v.name} onChangeText={x=>updateVariant(i,{name:x,id:slugify(x)||v.id})}/>
            <TextInput style={[s.input,{width:110}]} keyboardType="decimal-pad" value={String(v.price)} onChangeText={x=>updateVariant(i,{price:Number(x)||0})}/>
            <Switch value={v.active} onValueChange={x=>updateVariant(i,{active:x})}/>
            <Pressable onPress={()=>removeVariant(i)}><Trash size={18} color={colors.danger}/></Pressable>
          </View>)}

          <View style={s.subHead}><Text style={s.sectionTitle}>Modifiers & upcharges</Text><Pressable onPress={addModifier} style={s.addSmall}><Plus size={15} color={colors.primary}/><Text style={s.addSmallText}>Add modifier</Text></Pressable></View>
          {draft.modifiers.length===0?<Text style={s.help}>Optional stain treatment, delicate material, express service and similar upcharges.</Text>:draft.modifiers.map((m,i)=><View key={i} style={s.modifierCard}>
            <View style={s.repeatRow}>
              <TextInput style={[s.input,{flex:1}]} placeholder="Modifier name" value={m.name} onChangeText={x=>updateModifier(i,{name:x,id:slugify(x)||m.id})}/>
              <TextInput style={[s.input,{width:100}]} keyboardType="decimal-pad" value={String(m.amount)} onChangeText={x=>updateModifier(i,{amount:Number(x)||0})}/>
              <Pressable onPress={()=>updateModifier(i,{amount_type:m.amount_type==="flat"?"percent":"flat"})} style={s.typeBtn}><Text style={s.typeBtnText}>{m.amount_type==="flat"?"$":"%"}</Text></Pressable>
              <Pressable onPress={()=>removeModifier(i)}><Trash size={18} color={colors.danger}/></Pressable>
            </View>
            <View style={s.toggleGrid}>
              <Toggle label="Active" value={m.active} onChange={x=>updateModifier(i,{active:x})}/>
              <Toggle label="Customer selectable" value={m.customer_selectable} onChange={x=>updateModifier(i,{customer_selectable:x})}/>
            </View>
          </View>)}

          {err?<Text style={s.err}>{err}</Text>:null}{ok?<Text style={s.ok}>{ok}</Text>:null}
          <Pressable disabled={saving} onPress={save} style={[s.saveBtn,saving&&{opacity:.5}]}><Text style={s.saveText}>{saving?"Saving…":"Save Service"}</Text></Pressable>
        </>}
      </View>
    </View>
  </ScrollView>;
}

function AdminCard({icon,title,text,onPress}:{icon:any;title:string;text:string;onPress:()=>void}){return <Pressable style={s.adminCard} onPress={onPress}><View style={s.adminIcon}>{icon}</View><View style={{flex:1}}><Text style={s.adminCardTitle}>{title}</Text><Text style={s.adminCardText}>{text}</Text></View></Pressable>}

function Metric({label,value}:{label:string;value:any}){return <View style={s.metric}><Text style={s.metricValue}>{value}</Text><Text style={s.metricLabel}>{label}</Text></View>}
function Field({label,children}:{label:string;children:any}){return <View style={{flex:1,minWidth:180}}><Text style={s.label}>{label}</Text>{children}</View>}
function Toggle({label,value,onChange}:{label:string;value:boolean;onChange:(v:boolean)=>void}){return <View style={s.toggle}><Text style={s.toggleText}>{label}</Text><Switch value={value} onValueChange={onChange}/></View>}

const s=StyleSheet.create({
  loading:{padding:30},page:{padding:20,maxWidth:1240,width:"100%",alignSelf:"center",gap:16},
  top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:7,alignItems:"center"},backText:{fontWeight:"700",color:colors.ink},brand:{flexDirection:"row",gap:6,alignItems:"center"},brandText:{fontWeight:"900",color:colors.ink},
  header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:22,padding:22,flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start",gap:18,flexWrap:"wrap"},kicker:{fontSize:11,fontWeight:"900",letterSpacing:1.4,color:colors.primary},title:{fontSize:32,fontWeight:"900",color:colors.ink,marginTop:2},sub:{color:colors.muted,marginTop:5,maxWidth:760},adminGrid:{flexDirection:"row",flexWrap:"wrap",gap:10},adminCard:{flexBasis:"31%",flexGrow:1,minWidth:220,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:14,flexDirection:"row",gap:10,alignItems:"center"},adminIcon:{width:38,height:38,borderRadius:12,backgroundColor:colors.primarySoft,alignItems:"center",justifyContent:"center"},adminCardTitle:{fontWeight:"900",color:colors.ink},adminCardText:{fontSize:12,color:colors.muted,marginTop:2},primaryAction:{backgroundColor:colors.primary,borderRadius:12,paddingHorizontal:16,paddingVertical:12,flexDirection:"row",gap:7,alignItems:"center"},primaryActionText:{color:"#fff",fontWeight:"900"},headerActions:{flex:1,minWidth:280,flexDirection:"row",justifyContent:"flex-end",gap:8,flexWrap:"wrap"},newBtn:{backgroundColor:colors.primary,borderRadius:12,minHeight:42,paddingHorizontal:14,paddingVertical:10,flexDirection:"row",gap:7,alignItems:"center",justifyContent:"center",flexShrink:0},newText:{color:"#fff",fontWeight:"900"},
  metrics:{flexDirection:"row",gap:10,flexWrap:"wrap"},metric:{flex:1,minWidth:150,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:16,padding:16},metricValue:{fontSize:25,fontWeight:"900",color:colors.ink},metricLabel:{color:colors.muted,marginTop:2},
  settingsPanel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18},settingsGrid:{flexDirection:"row",flexWrap:"wrap",gap:10,marginTop:10},setting:{minWidth:220,flex:1,backgroundColor:colors.soft,borderRadius:12,padding:12,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},settingName:{fontWeight:"900",color:colors.ink},help:{fontSize:12,color:colors.muted,marginTop:3},categoryAdd:{flexDirection:"row",gap:8,marginTop:10,flexWrap:"wrap"},addCategoryBtn:{backgroundColor:colors.ink,borderRadius:11,paddingHorizontal:14,justifyContent:"center"},addCategoryText:{color:"#fff",fontWeight:"900"},categoryGrid:{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:10},categoryCard:{minWidth:240,flex:1,flexDirection:"row",gap:8,alignItems:"center",backgroundColor:colors.soft,borderRadius:12,padding:8},
  layout:{flexDirection:"row",gap:16,alignItems:"flex-start",flexWrap:"wrap"},catalog:{width:340,maxWidth:"100%",flexShrink:1,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,overflow:"hidden"},catalogHeader:{padding:16,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},serviceRow:{padding:14,borderTopWidth:1,borderTopColor:colors.border,flexDirection:"row",gap:12},serviceRowOn:{backgroundColor:colors.primarySoft},serviceCat:{fontSize:9,fontWeight:"900",letterSpacing:1,color:colors.primary,textTransform:"uppercase"},serviceName:{fontWeight:"900",fontSize:15,color:colors.ink,marginTop:2},price:{fontWeight:"900",color:colors.ink},status:{fontSize:11,fontWeight:"900",marginTop:5},active:{color:colors.success},inactive:{color:colors.danger},
  editor:{flex:2,minWidth:300,backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:20},empty:{padding:40,alignItems:"center"},emptyTitle:{fontSize:20,fontWeight:"900",color:colors.ink},editorHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",marginBottom:14},duplicateBtn:{borderWidth:1,borderColor:colors.border,borderRadius:10,paddingHorizontal:12,paddingVertical:8},duplicateText:{fontWeight:"900",color:colors.primary},sectionTitle:{fontSize:18,fontWeight:"900",color:colors.ink},label:{fontSize:10,fontWeight:"900",letterSpacing:.8,color:colors.muted,textTransform:"uppercase",marginBottom:6,marginTop:10},formRow:{flexDirection:"row",gap:10,flexWrap:"wrap"},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,padding:11,backgroundColor:"#fff"},disabled:{backgroundColor:colors.soft,color:colors.muted},multi:{minHeight:78,textAlignVertical:"top"},
  chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,paddingHorizontal:10,paddingVertical:8,borderRadius:999},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontWeight:"800",fontSize:12,color:colors.ink},chipTextOn:{color:"#fff"},
  toggleGrid:{flexDirection:"row",gap:8,flexWrap:"wrap"},toggle:{minWidth:160,backgroundColor:colors.soft,borderRadius:10,padding:9,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},toggleText:{fontSize:12,fontWeight:"800",color:colors.ink},
  subHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",marginTop:20,marginBottom:4},addSmall:{flexDirection:"row",gap:5,alignItems:"center"},addSmallText:{fontWeight:"900",color:colors.primary,fontSize:12},repeatRow:{flexDirection:"row",gap:8,alignItems:"center",marginTop:8,flexWrap:"wrap"},modifierCard:{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:10,marginTop:8},typeBtn:{width:42,height:42,borderWidth:1,borderColor:colors.border,borderRadius:10,alignItems:"center",justifyContent:"center"},typeBtnText:{fontWeight:"900",color:colors.primary},
  err:{color:colors.danger,marginTop:14},ok:{color:colors.success,marginTop:14},saveBtn:{alignSelf:"flex-start",backgroundColor:colors.primary,borderRadius:12,paddingHorizontal:22,paddingVertical:13,marginTop:16},saveText:{color:"#fff",fontWeight:"900"}
});

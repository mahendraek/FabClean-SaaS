import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Plus, Sparkle, Trash } from "phosphor-react-native";
import { api } from "@/src/api";
import { colors } from "@/src/theme";

type Staff={id:string;name:string;email:string;role:string;active:boolean;business_id?:string;location_id?:string};
type Assignment={id?:string;role:string;scope_type:"platform"|"brand"|"store";brand_id?:string|null;store_id?:string|null;active?:boolean};
type Ctx={brands:any[];stores:any[];active_brand:any;active_store:any;is_super_admin:boolean;assignments:Assignment[]};
const LEGACY=["owner","manager","counter","processing","driver"];
const STORE_ROLES=["store_manager","counter","processing","driver"];

export default function StaffAdmin(){
 const router=useRouter();
 const [items,setItems]=useState<Staff[]>([]),[editing,setEditing]=useState<Staff|null>(null),[form,setForm]=useState<any>({name:"",email:"",password:"",role:"counter",active:true,location_id:"main"}),[assignments,setAssignments]=useState<Assignment[]>([]),[ctx,setCtx]=useState<Ctx|null>(null),[selectedBrand,setSelectedBrand]=useState(""),[selectedStore,setSelectedStore]=useState(""),[err,setErr]=useState(""),[ok,setOk]=useState(""),[saving,setSaving]=useState(false);
 async function load(){try{const [s,c]=await Promise.all([api.get<{staff:Staff[]}>("/admin/staff?include_inactive=true"),api.get<Ctx>("/context")]);setItems(s.staff||[]);setCtx(c);const bid=selectedBrand||c.active_brand?.id||c.brands?.[0]?.id||"";setSelectedBrand(bid);const first=(c.stores||[]).find(x=>x.brand_id===bid);setSelectedStore(selectedStore||c.active_store?.id||first?.id||"")}catch(e:any){setErr(e.message||"Could not load staff")}}
 useEffect(()=>{load()},[]);
 const brandStores=useMemo(()=>ctx?.stores?.filter(x=>x.brand_id===selectedBrand)||[],[ctx,selectedBrand]);
 function startNew(){setEditing({id:"",name:"",email:"",role:"counter",active:true});setForm({name:"",email:"",password:"",role:"counter",active:true,location_id:selectedStore||"main"});setAssignments([]);setErr("");setOk("")}
 async function startEdit(x:Staff){setEditing(x);setForm({name:x.name,email:x.email,password:"",role:x.role,active:x.active,location_id:x.location_id||selectedStore||"main"});setErr("");setOk("");try{const r=await api.get<{assignments:Assignment[]}>("/admin/staff/"+x.id+"/roles");setAssignments(r.assignments||[])}catch(e:any){setErr(e.message||"Could not load role assignments")}}
 function addAssignment(role:string){
  const scope_type=role==="super_admin"?"platform":role==="brand_admin"?"brand":"store";
  const a:Assignment={role,scope_type,brand_id:scope_type==="platform"?null:selectedBrand||null,store_id:scope_type==="store"?(selectedStore||null):null,active:true};
  if(scope_type==="brand"&&!a.brand_id){setErr("Select a brand");return}
  if(scope_type==="store"&&(!a.brand_id||!a.store_id)){setErr("Select a brand and store");return}
  if(assignments.some(x=>x.role===a.role&&x.scope_type===a.scope_type&&x.brand_id===a.brand_id&&x.store_id===a.store_id))return;
  setAssignments(v=>[...v,a]);
 }
 async function save(){
  if(!form.name.trim()||!form.email.trim()){setErr("Name and email are required");return}
  if(!editing?.id&&form.password.length<8){setErr("Password must be at least 8 characters");return}
  setSaving(true);setErr("");setOk("");
  try{
    const staffPayload={...form,business_id:selectedBrand||ctx?.active_brand?.id,location_id:selectedStore||ctx?.active_store?.id||form.location_id};const saved:any=editing?.id?await api.put("/admin/staff/"+editing.id,staffPayload):await api.post("/admin/staff",staffPayload);
    await api.put("/admin/staff/"+saved.id+"/roles",{assignments});
    setEditing(null);setAssignments([]);setOk("Staff user and role assignments saved");await load();
  }catch(e:any){setErr(e.message||"Could not save staff")}finally{setSaving(false)}
 }
 return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
  <View style={s.top}><Pressable onPress={()=>router.push("/admin")} style={s.back}><ArrowLeft size={18}/><Text>Admin</Text></Pressable><View style={s.brand}><Sparkle size={16} color={colors.primary}/><Text style={s.bold}>Staff & Roles</Text></View></View>
  <View style={s.header}><View style={{flex:1}}><Text style={s.kicker}>MULTI-ROLE ACCESS</Text><Text style={s.title}>Staff & Roles</Text><Text style={s.meta}>One person can hold multiple platform, brand and store roles. Permissions are additive within each scope.</Text></View><Pressable style={s.primary} onPress={startNew}><Plus size={16} color="#fff"/><Text style={s.primaryText}>New Staff</Text></Pressable></View>
  {err?<Text style={s.err}>{err}</Text>:null}{ok?<Text style={s.ok}>{ok}</Text>:null}
  {editing?<View style={s.panel}>
    <Text style={s.section}>{editing.id?"Edit staff":"New staff"}</Text>
    <View style={s.row}><Field label="Name"><TextInput style={s.input} value={form.name} onChangeText={v=>setForm({...form,name:v})}/></Field><Field label="Email"><TextInput style={s.input} value={form.email} autoCapitalize="none" keyboardType="email-address" onChangeText={v=>setForm({...form,email:v})}/></Field><Field label={editing.id?"New password (optional)":"Password"}><TextInput style={s.input} value={form.password} secureTextEntry onChangeText={v=>setForm({...form,password:v})}/></Field></View>
    <Text style={s.label}>Legacy operational role</Text><View style={s.chips}>{LEGACY.map(x=><Pressable key={x} style={[s.chip,form.role===x&&s.chipOn]} onPress={()=>setForm({...form,role:x})}><Text style={[s.chipText,form.role===x&&s.chipTextOn]}>{x}</Text></Pressable>)}</View>
    <Text style={s.label}>Role assignment scope</Text>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>{ctx?.brands?.map(b=><Pressable key={b.id} style={[s.chip,selectedBrand===b.id&&s.chipOn]} onPress={()=>{setSelectedBrand(b.id);const st=(ctx?.stores||[]).find(x=>x.brand_id===b.id);setSelectedStore(st?.id||"")}}><Text style={[s.chipText,selectedBrand===b.id&&s.chipTextOn]}>{b.name}</Text></Pressable>)}</ScrollView>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>{brandStores.map(st=><Pressable key={st.id} style={[s.chip,selectedStore===st.id&&s.chipOn]} onPress={()=>setSelectedStore(st.id)}><Text style={[s.chipText,selectedStore===st.id&&s.chipTextOn]}>{st.name}</Text></Pressable>)}</ScrollView>
    <View style={s.assignmentActions}>{ctx?.is_super_admin?<Pressable style={s.smallBtn} onPress={()=>addAssignment("super_admin")}><Text style={s.smallBtnText}>+ SuperAdmin</Text></Pressable>:null}<Pressable style={s.smallBtn} onPress={()=>addAssignment("brand_admin")}><Text style={s.smallBtnText}>+ Brand Admin</Text></Pressable>{STORE_ROLES.map(role=><Pressable key={role} style={s.smallBtn} onPress={()=>addAssignment(role)}><Text style={s.smallBtnText}>+ {role.replaceAll("_"," ")}</Text></Pressable>)}</View>
    <View style={s.assignmentList}>{assignments.length===0?<Text style={s.meta}>No scoped assignments yet.</Text>:assignments.map((a,i)=>{const b=ctx?.brands?.find(x=>x.id===a.brand_id),st=ctx?.stores?.find(x=>x.id===a.store_id);return <View key={i} style={s.assignment}><View style={{flex:1}}><Text style={s.bold}>{a.role.replaceAll("_"," ")}</Text><Text style={s.meta}>{a.scope_type==="platform"?"Platform":a.scope_type==="brand"?(b?.name||a.brand_id):(b?.name||a.brand_id)+" · "+(st?.name||a.store_id)}</Text></View><Pressable onPress={()=>setAssignments(v=>v.filter((_,j)=>j!==i))}><Trash size={18} color={colors.danger}/></Pressable></View>})}</View>
    <View style={s.toggle}><Text style={s.bold}>Active user</Text><Switch value={form.active} onValueChange={v=>setForm({...form,active:v})}/></View>
    <View style={s.actions}><Pressable style={s.primary} disabled={saving} onPress={save}><Text style={s.primaryText}>{saving?"Saving…":"Save Staff & Roles"}</Text></Pressable><Pressable onPress={()=>setEditing(null)}><Text style={s.link}>Cancel</Text></Pressable></View>
  </View>:null}
  <View style={s.list}>{items.length===0?<Text style={s.meta}>No staff users configured.</Text>:items.map(x=><Pressable key={x.id} style={s.staffRow} onPress={()=>startEdit(x)}><View style={{flex:1}}><Text style={s.bold}>{x.name}</Text><Text style={s.meta}>{x.email} · legacy {x.role}</Text></View><Text style={{fontWeight:"900",color:x.active?colors.success:colors.danger}}>{x.active?"Active":"Inactive"}</Text></Pressable>)}</View>
 </ScrollView>
}
function Field({label,children}:{label:string;children:any}){return <View style={s.field}><Text style={s.label}>{label}</Text>{children}</View>}
const s=StyleSheet.create({page:{padding:18,maxWidth:1050,width:"100%",alignSelf:"center",gap:14},top:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:10,flexWrap:"wrap"},back:{flexDirection:"row",gap:6,alignItems:"center"},brand:{flexDirection:"row",gap:6,alignItems:"center"},header:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:20,padding:20,flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"},kicker:{fontSize:10,fontWeight:"900",color:colors.primary},title:{fontSize:30,fontWeight:"900",color:colors.ink},meta:{fontSize:12,color:colors.muted,marginTop:3},bold:{fontWeight:"900",color:colors.ink},primary:{backgroundColor:colors.primary,borderRadius:12,minHeight:44,paddingHorizontal:15,paddingVertical:11,alignItems:"center",justifyContent:"center",flexDirection:"row",gap:6},primaryText:{color:"#fff",fontWeight:"900"},panel:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,padding:18,gap:10},section:{fontSize:18,fontWeight:"900",color:colors.ink},row:{flexDirection:"row",gap:10,flexWrap:"wrap"},field:{flex:1,minWidth:220},label:{fontSize:10,fontWeight:"900",color:colors.muted,textTransform:"uppercase",marginTop:5,marginBottom:5},input:{borderWidth:1,borderColor:colors.border,borderRadius:11,minHeight:44,paddingHorizontal:12,paddingVertical:10},chips:{flexDirection:"row",gap:7,flexWrap:"wrap"},chip:{borderWidth:1,borderColor:colors.border,borderRadius:999,paddingHorizontal:11,paddingVertical:8},chipOn:{backgroundColor:colors.primary,borderColor:colors.primary},chipText:{fontSize:12,fontWeight:"800",color:colors.ink},chipTextOn:{color:"#fff"},assignmentActions:{flexDirection:"row",gap:7,flexWrap:"wrap"},smallBtn:{borderWidth:1,borderColor:colors.primary,borderRadius:10,paddingHorizontal:10,paddingVertical:8},smallBtnText:{fontSize:12,fontWeight:"900",color:colors.primary,textTransform:"capitalize"},assignmentList:{gap:7},assignment:{backgroundColor:colors.soft,borderRadius:11,padding:10,flexDirection:"row",alignItems:"center",gap:8},toggle:{backgroundColor:colors.soft,borderRadius:11,padding:10,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},actions:{flexDirection:"row",gap:12,alignItems:"center",flexWrap:"wrap"},link:{fontWeight:"900",color:colors.primary},list:{backgroundColor:"#fff",borderWidth:1,borderColor:colors.border,borderRadius:18,overflow:"hidden"},staffRow:{padding:15,borderBottomWidth:1,borderBottomColor:colors.border,flexDirection:"row",alignItems:"center",gap:10},err:{color:colors.danger},ok:{color:colors.success,fontWeight:"800"}});
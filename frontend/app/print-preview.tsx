import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, ScrollView, Share, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@/src/api';
import { receiptHtml } from '@/src/receipt';
import { downloadRaw, generateLabelCommands, labelHtml, openPrintDocument, PrintLabel } from '@/src/hardware';
import { colors, themedStyles } from '@/src/theme';

type Garment={garment_code:string;service_name:string;garment_index:number;tag_print_count:number};
export default function PrintPreview(){
 const {id,kind='receipt',code}=useLocalSearchParams<{id:string;kind?:string;code?:string}>(),router=useRouter();
 const [data,setData]=useState<any>(null),[selected,setSelected]=useState<string[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[prepared,setPrepared]=useState(false),[confirmed,setConfirmed]=useState(false);
 const requestId=useRef(''),loadId=useRef(0),mounted=useRef(true);
 const document=kind==='garments'?'garment_tags':kind==='order'?'order_tag':'receipt';
 useEffect(()=>{const seq=++loadId.current;mounted.current=true;setData(null);setError('');setPrepared(false);setConfirmed(false);
  api.get<any>('/orders/'+encodeURIComponent(id||'')+'/print-preview').then(d=>{if(!mounted.current||seq!==loadId.current)return;setData(d);setSelected(code?[code]:d.garments.slice(0,100).map((g:Garment)=>g.garment_code));}).catch(e=>{if(mounted.current&&seq===loadId.current)setError(e.message);});
  return()=>{mounted.current=false;loadId.current++;};
 },[id,kind,code]);
 if(!data)return <View style={{padding:24}}><Text accessibilityRole={error?'alert':undefined}>{error||'Loading print preview…'}</Text><Pressable accessibilityRole="button" onPress={()=>router.back()}><Text>Back</Text></Pressable></View>;
 const order=data.receipt.order,garments:Garment[]=data.garments;
 const labels:PrintLabel[]=document==='order_tag'?[{code:order.barcode_value,order:order.order_number,line1:'ORDER TAG'}]:garments.filter(g=>selected.includes(g.garment_code)).map(g=>({code:g.garment_code,order:order.order_number,line1:g.service_name,line2:`Item ${g.garment_index} / ${garments.length}`}));
 const raw=document!=='receipt'&&data.profile.printer_mode!=='browser';
 function changeSelection(value:string){setSelected(s=>s.includes(value)?s.filter(v=>v!==value):s.length<100?[...s,value]:s);setPrepared(false);setConfirmed(false);setError('');}
 async function prepare(){
  setError('');setPrepared(false);setConfirmed(false);setBusy(true);
  try{
   if(raw){
    const output=generateLabelCommands(labels,data.profile,data.profile.printer_mode);
    if(Platform.OS==='web')downloadRaw(order.order_number+'.'+data.profile.printer_mode,output);
    else {const result=await Share.share({message:output,title:order.order_number+' printer commands'});if(result.action!==Share.sharedAction)return;}
   }else openPrintDocument(document==='receipt'?receiptHtml(data):labelHtml(order.order_number,labels,data.profile));
   if(!mounted.current)return;
   requestId.current='print-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,14).padEnd(12,'0');setPrepared(true);
  }catch(e:any){if(mounted.current)setError(e.message||'Could not prepare print output');}
  finally{if(mounted.current)setBusy(false);}
 }
 async function confirm(){
  if(!prepared||busy||confirmed)return;setBusy(true);setError('');
  try{
   await api.post('/orders/'+encodeURIComponent(id)+'/print-confirmations',{request_id:requestId.current,document,garment_codes:document==='garment_tags'?selected:[]});
   if(mounted.current){setConfirmed(true);setPrepared(false);}
  }catch(e:any){if(mounted.current)setError(e.message||'Could not save confirmation; retry safely');}
  finally{if(mounted.current)setBusy(false);}
 }
 const currency=order.currency||order.tax_snapshot?.currency||'UNSPECIFIED';
 return <ScrollView style={{backgroundColor:colors.soft}} contentContainerStyle={s.page}>
  <Pressable accessibilityRole="button" onPress={()=>router.back()}><Text style={s.link}>Back</Text></Pressable>
  <View style={s.panel}><Text style={s.title}>Print preview</Text><Text style={s.heading}>{order.order_number} · {document.replaceAll('_',' ')}</Text><Text>{data.business.business_name}</Text><Text style={s.help}>Snapshot: {new Date(data.generated_at).toLocaleString()}. Reload the preview after changing the order or payments.</Text><Text style={s.help}>Check the preview, print or download, then confirm only after checking the physical output. Opening a preview, cancelling a print dialog or downloading a file does not count as a completed print.</Text></View>
  {document==='receipt'?<View style={s.panel}><Text style={s.heading}>Receipt · {data.profile.receipt_paper.toUpperCase()}</Text><Text>{order.customer.name}</Text>{order.items.map((item:any,i:number)=><Text key={i}>{item.service_name} × {item.quantity} · {currency} {(Number(item.quantity)*Number(item.unit_price)).toFixed(2)}</Text>)}<Text style={s.heading}>Total: {currency} {Number(order.total).toFixed(2)}</Text><Text>Paid: {currency} {Number(data.receipt.paid_total).toFixed(2)}</Text><Text>Balance: {currency} {Number(data.receipt.balance_due).toFixed(2)}</Text>{order.pricing_status==='estimated'?<Text style={s.help}>Estimated pricing — final total may change.</Text>:null}</View>:<View style={s.panel}><Text style={s.heading}>Labels · {data.profile.label_width_mm} × {data.profile.label_height_mm} mm · {data.profile.printer_mode.toUpperCase()}</Text>{document==='garment_tags'?<><Text style={s.help}>Select up to 100 tags per batch. {selected.length} selected.</Text>{garments.map(g=><Pressable key={g.garment_code} accessibilityRole="checkbox" accessibilityLabel={'Select tag '+g.garment_code} accessibilityState={{checked:selected.includes(g.garment_code),disabled:busy}} disabled={busy} onPress={()=>changeSelection(g.garment_code)} style={s.row}><Text>{selected.includes(g.garment_code)?'☑':'☐'} {g.garment_code} · {g.service_name}</Text><Text style={s.help}>Recorded print count: {g.tag_print_count||0}</Text></Pressable>)}</>:<Text>{order.barcode_value}</Text>}</View>}
  {error?<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>:null}
  {confirmed?<Text accessibilityRole="alert" style={{color:colors.success}}>Physical print confirmation saved.</Text>:null}
  <View style={s.panel}><Text style={s.help}>{raw?'Use the downloaded command file with your compatible printer utility. Raw text is ASCII; customer names are omitted from tags.':'Open the print document and use its Print button. Select the matching paper size and actual size / 100% scale. System printing requires a web browser; native apps can share raw ZPL/TSPL commands.'}</Text><Button disabled={busy||(document!=='receipt'&&!labels.length)} title={raw?(Platform.OS==='web'?'Download printer file':'Share printer commands'):'Open print document'} onPress={()=>void prepare()}/>{prepared?<><Text style={s.help}>Did the physical output print successfully? Confirming records your statement; FabClean cannot verify printer delivery.</Text><Button disabled={busy} title="Confirm physical print" onPress={()=>void confirm()}/><Button disabled={busy} title="Cancel confirmation" onPress={()=>{setPrepared(false);setError('');}}/></>:null}</View>
 </ScrollView>;
}
function Button({title,disabled,onPress}:{title:string;disabled:boolean;onPress:()=>void}){return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={[s.button,disabled&&{opacity:.5}]}><Text style={{color:'#fff',fontWeight:'800'}}>{title}</Text></Pressable>}
const s=themedStyles({page:{padding:20,gap:16,maxWidth:900,width:'100%',alignSelf:'center'},panel:{backgroundColor:'#fff',borderWidth:1,borderColor:colors.border,padding:18,borderRadius:14,gap:10,flexShrink:0},title:{fontSize:28,fontWeight:'900',color:colors.ink},heading:{fontSize:17,fontWeight:'800',color:colors.ink},help:{fontSize:13,lineHeight:20,color:colors.muted},row:{paddingVertical:10,borderBottomWidth:1,borderBottomColor:colors.border,gap:4},button:{backgroundColor:colors.primary,padding:13,borderRadius:10,alignSelf:'flex-start'},link:{color:colors.primary,fontWeight:'800'}});

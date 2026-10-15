import { useState } from "react";
import { Linking, Platform, Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { api } from "./api";
import { colors } from "./theme";
import { whatsappReceiptURL } from "./whatsapp";

type Preview = {phone:string;message:string;fingerprint:string};
export function WhatsAppReceipt({orderId,customerId}:{orderId:string;customerId?:string}) {
  const router=useRouter();const [preview,setPreview]=useState<Preview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  async function prepare(){setBusy(true);setError('');setNotice('');setPreview(null);try{setPreview(await api.get<Preview>('/orders/'+encodeURIComponent(orderId)+'/whatsapp-receipt'));}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  async function open(){if(!preview||busy)return;setBusy(true);setError('');setNotice('');let popup:Window|null=null;
    try{
      if(Platform.OS==='web') {popup=window.open('about:blank','_blank');if(!popup)throw new Error('Allow pop-ups to open WhatsApp.');popup.opener=null;}
      const confirmed=await api.post<Preview>('/orders/'+encodeURIComponent(orderId)+'/whatsapp-receipt',{fingerprint:preview.fingerprint});
      const url=whatsappReceiptURL(confirmed.phone,confirmed.message);
      if(popup)popup.location.replace(url);else await Linking.openURL(url);
      setPreview(null);setNotice('WhatsApp opened. Check the recipient and tap Send there. Sending and delivery are not tracked by FabClean.');
    }catch(e:any){popup?.close();setPreview(null);setError(e.message||'Could not open WhatsApp.');}finally{setBusy(false);}
  }
  return <View style={{gap:10,marginTop:14}}><Text style={{fontWeight:'700'}}>WhatsApp receipt</Text><Text>Share manually using WhatsApp on your phone or WhatsApp Web. No provider API key is needed. You choose when to send.</Text>
    <Button label="Preview WhatsApp receipt" disabled={busy} onPress={()=>void prepare()}/>
    {customerId&&<Button label="Manage customer consent" disabled={busy} onPress={()=>router.push({pathname:'/customer-profile',params:{id:customerId}})}/>}
    {preview&&<View style={{gap:10,padding:12,borderWidth:1,borderColor:colors.border,borderRadius:10}}><Text style={{fontWeight:'700'}}>Review WhatsApp receipt</Text><Text>Recipient: {preview.phone}</Text><Text selectable>{preview.message}</Text><Text>Confirm this is the customer's WhatsApp number. Opening WhatsApp prepares a message; you must tap Send in WhatsApp.</Text><Button label="Cancel WhatsApp sharing" disabled={busy} onPress={()=>setPreview(null)}/><Button label="Open WhatsApp" disabled={busy} onPress={()=>void open()}/></View>}
    {!!error&&<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>}{!!notice&&<Text accessibilityLiveRegion="polite">{notice}</Text>}
  </View>;
}
function Button({label,onPress,disabled}:{label:string;onPress:()=>void;disabled:boolean}){return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={{padding:10,borderWidth:1,borderColor:colors.border,borderRadius:8,opacity:disabled?0.5:1}}><Text style={{color:colors.primary,fontWeight:'700'}}>{label}</Text></Pressable>}

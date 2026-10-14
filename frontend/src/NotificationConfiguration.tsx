import { useEffect, useState } from "react";
import { Pressable, Switch, Text, TextInput, View } from "react-native";
import { colors } from "./theme";

const kinds=["order_received","ready_for_pickup","delivery_scheduled","order_receipt","payment_receipt"];
export function NotificationConfiguration({values,busy,onSave}:{values:Record<string,any>;busy:boolean;onSave:(key:string,value:any)=>void}) {
  const [email,setEmail]=useState(""),[sms,setSms]=useState(""),[templates,setTemplates]=useState<Record<string,string>>({});
  useEffect(()=>{setEmail(values.notification_email_sender||"");setSms(values.notification_sms_sender||"");setTemplates(values.notification_templates||{});},[values]);
  return <View style={{gap:12}}><Text style={{fontSize:18,fontWeight:"700"}}>Notification senders & templates</Text><Text>Set brand defaults or store overrides. Senders must be verified with the configured provider. Blank senders use the server's verified defaults. Customers must explicitly opt in; queued messages are processed by the notification worker or reviewed in the delivery queue.</Text>
    <View style={{flexDirection:"row",gap:12,alignItems:"center"}}><Text style={{flex:1}}>Enable customer notifications</Text><Switch accessibilityLabel="Customer notifications enabled" disabled={busy} value={!!values.notifications_enabled} onValueChange={v=>onSave('notifications_enabled',v)}/></View>
    <TextInput accessibilityLabel="Notification email sender" placeholder="Verified sender email" value={email} onChangeText={setEmail} style={{borderWidth:1,borderColor:colors.border,padding:10}}/>
    <Button label="Save notification email sender" disabled={busy} onPress={()=>onSave('notification_email_sender',email)}/>
    <TextInput accessibilityLabel="Notification SMS sender" placeholder="Verified E.164 SMS number" value={sms} onChangeText={setSms} style={{borderWidth:1,borderColor:colors.border,padding:10}}/>
    <Button label="Save notification SMS sender" disabled={busy} onPress={()=>onSave('notification_sms_sender',sms)}/>
    <Text>Templates support {'{name}'}, {'{business_name}'} and {'{order_number}'}. Blank templates use branded defaults. Receipt totals and tax details are added automatically.</Text>
    {kinds.map(kind=><View key={kind} style={{gap:5}}><Text>{kind.replaceAll('_',' ')}</Text><TextInput accessibilityLabel={'Template '+kind} value={templates[kind]||''} multiline onChangeText={text=>setTemplates({...templates,[kind]:text})} style={{borderWidth:1,borderColor:colors.border,padding:10}}/></View>)}
    <Button label="Save notification templates" disabled={busy} onPress={()=>onSave('notification_templates',Object.fromEntries(Object.entries(templates).filter(([,v])=>v.trim())))}/>
  </View>;
}
function Button({label,disabled,onPress}:{label:string;disabled:boolean;onPress:()=>void}){return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={{padding:10}}><Text style={{color:colors.primary,fontWeight:'700'}}>{label}</Text></Pressable>}

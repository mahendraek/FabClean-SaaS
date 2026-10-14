import { useEffect, useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { api } from "./api";
import { colors } from "./theme";

export function TaxProviderLookup({onImported}:{onImported:()=>Promise<void>}) {
  const [status,setStatus]=useState<any>(null),[quote,setQuote]=useState<any>(null);
  const [jurisdiction,setJurisdiction]=useState(false),[taxability,setTaxability]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{api.get('/taxes/provider').then(setStatus).catch(e=>setError(e.message));},[]);
  async function lookup(){setBusy(true);setError('');setQuote(null);setJurisdiction(false);setTaxability(false);try{setQuote(await api.post('/taxes/provider/lookup'));}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  async function apply(){setBusy(true);setError('');try{await api.post('/taxes/provider/'+quote.id+'/import',{jurisdiction_verified:jurisdiction,service_taxability_verified:taxability});setQuote(null);await onImported();}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  return <View style={{gap:10}}><Text style={{fontSize:18,fontWeight:'700'}}>Tax rate provider</Text><Text>{status?.coverage}</Text><Text>{status?.billing_note}</Text><Text>{status?.configured?'Provider key configured':'Provider key is not configured. Enter it securely in server/environment settings.'}</Text>
    <Pressable accessibilityRole="button" disabled={busy||!status?.configured} onPress={()=>void lookup()}><Text style={{color:colors.primary,fontWeight:'700'}}>Look up store tax rate</Text></Pressable>
    {quote&&<><Text>{quote.provider}: {quote.jurisdiction} · {quote.rate}%</Text><Text>{quote.note}</Text><Text>Retrieved: {quote.retrieved_at} · Expires: {quote.expires_at}</Text><View style={{flexDirection:'row',gap:10}}><Text style={{flex:1}}>I verified the exact store jurisdiction</Text><Switch accessibilityLabel="Verify tax jurisdiction" value={jurisdiction} onValueChange={setJurisdiction}/></View><View style={{flexDirection:'row',gap:10}}><Text style={{flex:1}}>I verified the services' tax treatment</Text><Switch accessibilityLabel="Verify service taxability" value={taxability} onValueChange={setTaxability}/></View><Pressable accessibilityRole="button" disabled={busy||!jurisdiction||!taxability} onPress={()=>void apply()}><Text style={{color:colors.primary,fontWeight:'700'}}>Import verified location rate</Text></Pressable></>}
    {!!error&&<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>}
  </View>;
}

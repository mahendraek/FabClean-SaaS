import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import { api } from './api';
import { coordinate, MapPoint } from './coverage-map';
import { CoverageMap } from './CoverageMap';
import { colors } from './theme';

export type AddressPin={address:string;latitude:number;longitude:number;result:any};
export function CoverageAddress({fulfillment,onChange}:{fulfillment:string;onChange:(v:AddressPin|null)=>void}) {
  const [data,setData]=useState<any>(null),[address,setAddress]=useState(''),[lat,setLat]=useState(''),[lon,setLon]=useState(''),[result,setResult]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const sequence=useRef(0);
  useEffect(()=>{let alive=true;api.get<any>('/coverage').then(v=>{if(alive)setData(v);}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[]);
  useEffect(()=>{sequence.current++;setResult(null);setBusy(false);onChange(null);return()=>{sequence.current++;};},[address,lat,lon,fulfillment]);
  let selected:MapPoint|null=null;try{selected={latitude:coordinate(lat),longitude:coordinate(lon,false)};}catch{}
  const origin=data?.location?.latitude!=null&&data?.location?.longitude!=null?{latitude:Number(data.location.latitude),longitude:Number(data.location.longitude)}:null;
  function pick(p:MapPoint){setLat(p.latitude.toFixed(6));setLon(p.longitude.toFixed(6));}
  async function check(){const version=++sequence.current;setError('');setResult(null);onChange(null);setBusy(true);try{const pin={latitude:coordinate(lat),longitude:coordinate(lon,false),address};const response=await api.post<any>('/coverage/check',{...pin,fulfillment_type:fulfillment});if(version===sequence.current){setResult(response);onChange({...pin,result:response});}}catch(e:any){if(version===sequence.current){setError(e.message);onChange(null);}}finally{if(version===sequence.current)setBusy(false);}}
  const input={borderWidth:1,borderColor:colors.border,padding:10,borderRadius:8} as const;
  return <View style={{gap:10}}><Text style={{fontWeight:'700'}}>Service address & coverage</Text><TextInput accessibilityLabel="Service address" style={input} value={address} onChangeText={setAddress} placeholder="Enter the pickup/delivery address"/><Text>Tap the map or enter coordinates. Confirm the pin corresponds to this address.</Text>
    <View style={{flexDirection:'row',flexWrap:'wrap',gap:8}}><TextInput accessibilityLabel="Address latitude" style={[input,{flexGrow:1}]} value={lat} onChangeText={setLat} placeholder="Latitude" keyboardType="numbers-and-punctuation"/><TextInput accessibilityLabel="Address longitude" style={[input,{flexGrow:1}]} value={lon} onChangeText={setLon} placeholder="Longitude" keyboardType="numbers-and-punctuation"/></View>
    <CoverageMap origin={origin} selected={selected} policy={data?.payload} onSelect={busy?undefined:pick}/>
    <Pressable accessibilityRole="button" accessibilityLabel="Confirm address pin and check coverage" disabled={busy} onPress={()=>void check()} style={{padding:12,borderRadius:8,backgroundColor:colors.primary,opacity:busy?0.5:1}}><Text style={{color:'white'}}>{busy?'Checking…':'Confirm address pin and check coverage'}</Text></Pressable>
    {error&&<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>}{result&&<Text accessibilityLiveRegion="polite" style={{color:result.eligible===false?colors.danger:colors.primary}}>{result.reason}{result.distance!=null?' · '+result.distance+' '+result.unit:''}</Text>}
  </View>;
}

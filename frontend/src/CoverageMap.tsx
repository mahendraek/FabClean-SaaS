import { themedStyles } from "./theme";
import { useEffect, useState } from 'react';
import { Image, Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Polygon } from 'react-native-svg';
import { circle, CoveragePolicy, CoverageZone, MapPoint, project, radiusKm, unproject } from './coverage-map';
import { colors } from './theme';

export function CoverageMap({origin,selected,policy,draft=[],onSelect}:{origin:MapPoint|null;selected?:MapPoint|null;policy?:CoveragePolicy|null;draft?:MapPoint[];onSelect?:(p:MapPoint)=>void}) {
  const [center,setCenter]=useState<MapPoint>(origin||{latitude:0,longitude:0}),[zoom,setZoom]=useState(origin?11:2),[width,setWidth]=useState(320),[tileError,setTileError]=useState(false);
  const height=300;
  useEffect(()=>{if(origin){setCenter(origin);setZoom(11);}},[origin?.latitude,origin?.longitude]);
  const c=project(center,zoom),left=c.x-width/2,top=c.y-height/2,n=2**zoom;
  const tiles=[];
  for(let x=Math.floor(left/256);x<=Math.floor((left+width)/256);x++)for(let y=Math.floor(top/256);y<=Math.floor((top+height)/256);y++){
    if(y<0||y>=n)continue;const tx=(x%n+n)%n;
    const uri='https://tile.openstreetmap.org/'+zoom+'/'+tx+'/'+y+'.png';
    tiles.push(<View key={zoom+'-'+x+'-'+y} pointerEvents="none" style={{position:'absolute',left:x*256-left,top:y*256-top,width:256,height:256}}><Image source={Platform.OS==='web'?{uri}:{uri,headers:{'User-Agent':'FabClean-SaaS/1.0 (+https://github.com/mahendraek/FabClean-SaaS)'}}} style={{width:256,height:256}} onError={()=>setTileError(true)}/></View>);
  }
  function screen(p:MapPoint){const v=project(p,zoom),size=256*n;return {x:c.x+((v.x-c.x+size/2)%size+size)%size-size/2-left,y:v.y-top};}
  function vertices(points:MapPoint[]){return points.map(p=>{const v=screen(p);return v.x+','+v.y;}).join(' ');}
  function pan(dx:number,dy:number){setCenter(unproject(c.x+dx,c.y+dy,zoom));}
  const zones:CoverageZone[]=policy?.mode==='zones'?policy.zones.filter(z=>z.active):[];
  return <View style={s.wrap}>
    <View style={s.controls}>{[['Zoom in',()=>setZoom(z=>Math.min(18,z+1))],['Zoom out',()=>setZoom(z=>Math.max(2,z-1))],['Pan west',()=>pan(-width/3,0)],['Pan east',()=>pan(width/3,0)],['Pan north',()=>pan(0,-100)],['Pan south',()=>pan(0,100)],['Center store',()=>{if(origin){setCenter(origin);setZoom(11);}}]].map(([label,action])=><Pressable key={String(label)} accessibilityRole="button" accessibilityLabel={String(label)} style={s.button} onPress={action as ()=>void}><Text>{String(label)}</Text></Pressable>)}</View>
    <Pressable accessibilityRole="button" accessibilityLabel="Coverage map; tap to select address or zone vertex" onLayout={e=>setWidth(Math.max(240,e.nativeEvent.layout.width))} onPress={e=>{if(onSelect){const {locationX,locationY}=e.nativeEvent;onSelect(unproject(left+locationX,top+locationY,zoom));}}} style={{height,overflow:'hidden',backgroundColor:'#eef3f5',borderRadius:10,borderWidth:1,borderColor:colors.border}}>
      {tiles}<Svg pointerEvents="none" width={width} height={height} style={StyleSheet.absoluteFill}>
        {policy?.mode==='radius'&&origin&&<Polygon points={vertices(circle(origin,radiusKm(policy)))} fill="rgba(0,128,110,.15)" stroke="#00806e" strokeWidth={2}/>}
        {zones.map(z=><Polygon key={z.id} points={vertices(z.vertices)} fill="rgba(0,128,110,.15)" stroke="#00806e" strokeWidth={2}/>)}
        {draft.length>0&&<Polygon points={vertices(draft)} fill="rgba(242,155,30,.15)" stroke="#be6700" strokeWidth={2}/>}
        {draft.map((p,i)=>{const v=screen(p);return <Circle key={i} cx={v.x} cy={v.y} r={4} fill="#be6700"/>;})}
        {origin&&<Circle cx={screen(origin).x} cy={screen(origin).y} r={7} fill="#00806e" stroke="white" strokeWidth={2}/>}
        {selected&&<Circle cx={screen(selected).x} cy={screen(selected).y} r={7} fill="#be3030" stroke="white" strokeWidth={2}/>}
      </Svg>
    </Pressable>
    <View style={s.controls}><Text>Green: store / coverage · Red: selected address</Text><Pressable accessibilityRole="link" onPress={()=>void Linking.openURL('https://www.openstreetmap.org/copyright')}><Text style={{color:colors.primary}}>© OpenStreetMap contributors · ODbL</Text></Pressable></View>
    {tileError&&<Text>Map tiles unavailable. Coordinate entry and coverage checks still work.</Text>}
    <Text>Maps load visible tiles from OpenStreetMap. No addresses are sent to a geocoder. A selected pin must be confirmed against the entered address.</Text>
  </View>;
}
const s=themedStyles({wrap:{gap:8},controls:{flexDirection:'row',flexWrap:'wrap',gap:8,alignItems:'center'},button:{borderWidth:1,borderColor:colors.border,borderRadius:7,padding:8,backgroundColor:'white'}});

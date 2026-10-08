import React from "react";
import Svg, { Rect } from "react-native-svg";
import { View, Text, StyleSheet } from "react-native";

const PATTERNS=[
"212222","222122","222221","121223","121322","131222","122213","122312","132212","221213","221312","231212",
"112232","122132","122231","113222","123122","123221","223211","221132","221231","213212","223112","312131",
"311222","321122","321221","312212","322112","322211","212123","212321","232121","111323","131123","131321",
"112313","132113","132311","211313","231113","231311","112133","112331","132131","113123","113321","133121",
"313121","211331","231131","213113","213311","213131","311123","311321","331121","312113","312311","332111",
"314111","221411","431111","111224","111422","121124","121421","141122","141221","112214","112412","122114",
"122411","142112","142211","241211","221114","413111","241112","134111","111242","121142","121241","114212",
"124112","124211","411212","421112","421211","212141","214121","412121","111143","111341","131141","114113",
"114311","411113","411311","113141","114131","311141","411131","211412","211214","211232","2331112"
];

function encodeCode128B(value:string){
  const safe=(value||"").replace(/[^\x20-\x7E]/g,"?");
  const codes=[104,...Array.from(safe).map(ch=>ch.charCodeAt(0)-32)];
  let checksum=104;
  for(let i=1;i<codes.length;i++) checksum+=codes[i]*i;
  codes.push(checksum%103,106);
  return {safe,codes};
}

export function Code128({value,height=52,moduleWidth=2,showText=true}:{value:string;height?:number;moduleWidth?:number;showText?:boolean}){
  const {safe,codes}=encodeCode128B(value);
  const widths:number[]=[];
  codes.forEach(code=>PATTERNS[code].split("").forEach(n=>widths.push(Number(n))));
  const quiet=10;
  const totalModules=quiet*2+widths.reduce((a,b)=>a+b,0);
  const width=totalModules*moduleWidth;
  let x=quiet*moduleWidth;
  let bar=true;
  const bars:React.ReactNode[]=[];
  widths.forEach((w,i)=>{
    const px=w*moduleWidth;
    if(bar) bars.push(<Rect key={i} x={x} y={0} width={px} height={height} fill="#111"/>);
    x+=px;bar=!bar;
  });
  return <View style={styles.wrap}>
    <Svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>{bars}</Svg>
    {showText?<Text selectable style={styles.text}>{safe}</Text>:null}
  </View>;
}

const styles=StyleSheet.create({
  wrap:{alignItems:"flex-start"},
  text:{fontSize:11,fontWeight:"700",letterSpacing:1,color:"#111",marginTop:4}
});

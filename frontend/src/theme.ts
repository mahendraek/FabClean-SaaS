export const colors = {
  ink: "#10231E",
  muted: "#66766F",
  surface: "#FFFFFF",
  soft: "#F4F8F6",
  softBlue: "#EEF7FA",
  softGold: "#FFF7E8",
  border: "#DDE8E3",
  primary: "#0D766E",
  primaryDark: "#075850",
  primarySoft: "#DDF3EF",
  accent: "#D6A341",
  accentDark: "#9D7425",
  danger: "#B54747",
  success: "#247A4A",
  navy: "#18364A"
};

export const fonts = { display: "System", text: "System" };

import { useSyncExternalStore } from 'react';
import { StyleSheet } from 'react-native';
const defaultColors={...colors};
export const brandThemes={
  teal:{name:'Classic Teal',primary:'#0D766E',primaryDark:'#075850',primarySoft:'#DDF3EF',accent:'#D6A341'},
  ocean:{name:'Ocean Blue',primary:'#1D4ED8',primaryDark:'#1E3A8A',primarySoft:'#DBEAFE',accent:'#D6A341'},
  plum:{name:'Royal Plum',primary:'#7E22CE',primaryDark:'#581C87',primarySoft:'#F3E8FF',accent:'#D6A341'},
  forest:{name:'Forest Green',primary:'#166534',primaryDark:'#14532D',primarySoft:'#DCFCE7',accent:'#D6A341'},
  sunset:{name:'Warm Sunset',primary:'#9A3412',primaryDark:'#7C2D12',primarySoft:'#FFEDD5',accent:'#D6A341'}
};
let themeName='teal',version=0;const listeners=new Set<()=>void>();
export function applyBrandTheme(value:string){const name=Object.hasOwn(brandThemes,value)?value:'teal';if(name===themeName)return;themeName=name;const selected=brandThemes[name as keyof typeof brandThemes];Object.assign(colors,defaultColors,{primary:selected.primary,primaryDark:selected.primaryDark,primarySoft:selected.primarySoft,accent:selected.accent});version++;listeners.forEach(fn=>fn());}
export function useBrandTheme(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn);};},()=>version,()=>0);}
export const themedStyles:typeof StyleSheet.create=(styles:any)=>{
  const baseline={...colors};let cacheVersion=-1,cache:any={};
  function convert(value:any):any{if(Array.isArray(value))return value.map(convert);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,convert(v)]));if(typeof value==='string'){const key=Object.keys(baseline).find(k=>baseline[k as keyof typeof baseline]===value);if(key)return colors[key as keyof typeof colors];}return value;}
  return new Proxy(styles,{get(target,key){if(cacheVersion!==version){cache=convert(target);cacheVersion=version;}return cache[key];}});
};

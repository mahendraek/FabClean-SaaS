import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { CaretLeft, CaretRight, CalendarBlank } from "phosphor-react-native";
import { colors } from "@/src/theme";

const WEEK=["Su","Mo","Tu","We","Th","Fr","Sa"];

function parseIso(value:string){
  if(!value)return new Date();
  const [y,m,d]=value.split("-").map(Number);
  return new Date(y,m-1,d||1,12,0,0);
}
function iso(d:Date){
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");
  return y+"-"+m+"-"+day;
}
function monthLabel(d:Date){
  return d.toLocaleDateString(undefined,{month:"long",year:"numeric"});
}

export function CalendarDatePicker({value,onChange,min,label}:{value:string;onChange:(value:string)=>void;min?:string;label?:string}){
  const [open,setOpen]=useState(false);
  const [cursor,setCursor]=useState(()=>parseIso(value||min||""));
  const minValue=min||"";

  const days=useMemo(()=>{
    const y=cursor.getFullYear(),m=cursor.getMonth();
    const first=new Date(y,m,1,12).getDay();
    const count=new Date(y,m+1,0,12).getDate();
    const cells:(Date|null)[]=[];
    for(let i=0;i<first;i++)cells.push(null);
    for(let d=1;d<=count;d++)cells.push(new Date(y,m,d,12));
    while(cells.length%7)cells.push(null);
    return cells;
  },[cursor]);

  function moveMonth(delta:number){
    setCursor(x=>new Date(x.getFullYear(),x.getMonth()+delta,1,12));
  }

  return <View style={s.wrap}>
    <Pressable style={s.field} onPress={()=>setOpen(v=>!v)}>
      <CalendarBlank size={18} color={colors.primary}/>
      <Text style={[s.value,!value&&s.placeholder]}>{value||label||"Select date"}</Text>
    </Pressable>
    {open?<View style={s.calendar}>
      <View style={s.header}>
        <Pressable style={s.nav} onPress={()=>moveMonth(-1)}><CaretLeft size={18} color={colors.ink}/></Pressable>
        <Text style={s.month}>{monthLabel(cursor)}</Text>
        <Pressable style={s.nav} onPress={()=>moveMonth(1)}><CaretRight size={18} color={colors.ink}/></Pressable>
      </View>
      <View style={s.grid}>{WEEK.map(x=><View key={x} style={s.cell}><Text style={s.week}>{x}</Text></View>)}</View>
      <View style={s.grid}>{days.map((d,i)=>{
        if(!d)return <View key={"e"+i} style={s.cell}/>;
        const v=iso(d),disabled=!!minValue&&v<minValue,selected=v===value;
        return <Pressable key={v} disabled={disabled} style={[s.cell,s.day,selected&&s.selected,disabled&&s.disabled]} onPress={()=>{onChange(v);setOpen(false);setCursor(d);}}>
          <Text style={[s.dayText,selected&&s.selectedText,disabled&&s.disabledText]}>{d.getDate()}</Text>
        </Pressable>;
      })}</View>
    </View>:null}
  </View>;
}

const s=StyleSheet.create({
  wrap:{marginTop:6,width:"100%"},field:{minHeight:45,borderWidth:1,borderColor:colors.border,borderRadius:12,paddingHorizontal:12,flexDirection:"row",alignItems:"center",gap:9,backgroundColor:"#fff"},value:{fontWeight:"700",color:colors.ink},placeholder:{color:colors.muted,fontWeight:"500"},
  calendar:{marginTop:7,borderWidth:1,borderColor:colors.border,borderRadius:14,padding:10,backgroundColor:"#fff",maxWidth:330},header:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:8},nav:{width:34,height:34,borderWidth:1,borderColor:colors.border,borderRadius:9,alignItems:"center",justifyContent:"center"},month:{fontWeight:"900",color:colors.ink},
  grid:{flexDirection:"row",flexWrap:"wrap"},cell:{width:"14.2857%",aspectRatio:1,alignItems:"center",justifyContent:"center"},week:{fontSize:10,fontWeight:"900",color:colors.muted},day:{borderRadius:999},selected:{backgroundColor:colors.primary},disabled:{opacity:.3},dayText:{fontSize:12,fontWeight:"800",color:colors.ink},selectedText:{color:"#fff"},disabledText:{color:colors.muted}
});
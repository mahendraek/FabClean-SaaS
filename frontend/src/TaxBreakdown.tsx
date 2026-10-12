import { Text, View } from "react-native";
import { colors } from "./theme";
export function TaxBreakdown({snapshot,tax=0}:{snapshot?:any;tax?:number}) {
  if(!snapshot)return <Text>Recorded tax: ${Number(tax||0).toFixed(2)}</Text>;
  const loc=snapshot.location||{};
  return <View style={{gap:5,marginVertical:8}}><Text style={{fontWeight:"700",color:colors.ink}}>Tax breakdown</Text><Text style={{color:colors.muted}}>Service store: {[loc.city,loc.state,loc.country].filter(Boolean).join(", ")} · {snapshot.service_date}</Text>
    {(snapshot.breakdown||[]).map((row:any,i:number)=><Text key={i}>{row.jurisdiction} · {row.rate}% · ${Number(row.amount||0).toFixed(2)}</Text>)}
    <Text>Tax: ${Number(tax||0).toFixed(2)}</Text>{snapshot.lines?.some((l:any)=>!l.taxable)&&<Text style={{color:colors.muted}}>Exempt services excluded from taxable amounts.</Text>}
  </View>;
}

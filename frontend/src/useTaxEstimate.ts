import { useEffect, useRef, useState } from "react";
import { api } from "./api";
export function useTaxEstimate(input:Record<string,any>|null){
  const [result,setResult]=useState<any>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);const sequence=useRef(0);const key=input?JSON.stringify(input):"";
  useEffect(()=>{const version=++sequence.current;setResult(null);setError("");if(!key){setBusy(false);return;}setBusy(true);const timer=setTimeout(()=>{api.post<any>("/taxes/estimate",JSON.parse(key)).then(value=>{if(version===sequence.current){setResult({key,...value});setBusy(false);}}).catch(e=>{if(version===sequence.current){setError(e.message);setBusy(false);}});},250);return()=>{clearTimeout(timer);sequence.current++;};},[key]);
  return {result:result?.key===key?result:null,error,busy:busy||!!key&&result?.key!==key&&!error};
}

export type HardwareProfile={
  scanner_mode:"hid_keyboard";
  scanner_prefix:string;
  scanner_suffix:string;
  scanner_uppercase:boolean;
  printer_mode:"browser"|"zpl"|"tspl";
  printer_dpi:203|300;
  label_width_mm:number;
  label_height_mm:number;
  label_gap_mm:number;
};

export const defaultHardwareProfile:HardwareProfile={
  scanner_mode:"hid_keyboard",
  scanner_prefix:"",
  scanner_suffix:"",
  scanner_uppercase:true,
  printer_mode:"browser",
  printer_dpi:203,
  label_width_mm:50,
  label_height_mm:25,
  label_gap_mm:2,
};

export function profileFromSettings(settings:any):HardwareProfile{
  return {...defaultHardwareProfile,...(settings?.hardware_profile||{})};
}

export function normalizeScan(raw:string,profile:HardwareProfile){
  let value=String(raw||"").trim();
  if(profile.scanner_prefix&&value.startsWith(profile.scanner_prefix)) value=value.slice(profile.scanner_prefix.length);
  if(profile.scanner_suffix&&value.endsWith(profile.scanner_suffix)) value=value.slice(0,-profile.scanner_suffix.length);
  value=value.trim();
  return profile.scanner_uppercase?value.toUpperCase():value;
}

const dots=(mm:number,dpi:number)=>Math.max(1,Math.round(mm*dpi/25.4));
const safe=(v:string)=>String(v||"").replace(/[\^~]/g," ");

export function generateZpl(order:any,garments:any[],profile:HardwareProfile){
  const width=dots(profile.label_width_mm,profile.printer_dpi);
  const height=dots(profile.label_height_mm,profile.printer_dpi);
  return garments.map((g:any)=>{
    const code=safe(g.garment_code);
    const service=safe(g.service_name).slice(0,28);
    const orderNo=safe(order?.order_number||"");
    return [
      "^XA",
      "^PW"+width,
      "^LL"+height,
      "^CI28",
      "^FO20,15^A0N,28,28^FDFAB CLEAN^FS",
      "^FO20,48^A0N,24,24^FD"+orderNo+"  "+service+"^FS",
      "^FO20,78^BY2,2,55^BCN,55,Y,N,N^FD"+code+"^FS",
      "^XZ"
    ].join("\n");
  }).join("\n");
}

export function generateTspl(order:any,garments:any[],profile:HardwareProfile){
  const w=Math.max(20,Number(profile.label_width_mm||50));
  const h=Math.max(15,Number(profile.label_height_mm||25));
  const gap=Math.max(0,Number(profile.label_gap_mm||2));
  return garments.map((g:any)=>{
    const code=String(g.garment_code||"").replace(/"/g,"'");
    const service=String(g.service_name||"Garment").replace(/"/g,"'").slice(0,28);
    const orderNo=String(order?.order_number||"").replace(/"/g,"'");
    return [
      "SIZE "+w+" mm,"+h+" mm",
      "GAP "+gap+" mm,0 mm",
      "DIRECTION 1",
      "CLS",
      'TEXT 20,15,"0",0,1,1,"FAB CLEAN"',
      'TEXT 20,45,"0",0,1,1,"'+orderNo+' '+service+'"',
      'BARCODE 20,75,"128",55,1,0,2,2,"'+code+'"',
      "PRINT 1"
    ].join("\n");
  }).join("\n");
}

export function downloadRaw(filename:string,content:string){
  if(typeof window==="undefined") return;
  const blob=new Blob([content],{type:"text/plain;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=url;a.download=filename;a.click();
  URL.revokeObjectURL(url);
}

const CODE128_PATTERNS=[
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

export function code128Svg(value:string,height=54,moduleWidth=2){
  const safe=String(value||"").replace(/[^\x20-\x7E]/g,"?");
  const codes=[104,...Array.from(safe).map(ch=>ch.charCodeAt(0)-32)];
  let checksum=104;
  for(let i=1;i<codes.length;i++)checksum+=codes[i]*i;
  codes.push(checksum%103,106);
  const widths:number[]=[];
  codes.forEach(code=>CODE128_PATTERNS[code].split("").forEach(n=>widths.push(Number(n))));
  const quiet=10,totalModules=quiet*2+widths.reduce((a,b)=>a+b,0),width=totalModules*moduleWidth;
  let x=quiet*moduleWidth,bar=true;
  const rects:string[]=[];
  widths.forEach(w=>{const px=w*moduleWidth;if(bar)rects.push('<rect x="'+x+'" y="0" width="'+px+'" height="'+height+'" fill="#111"/>');x+=px;bar=!bar;});
  return '<svg xmlns="http://www.w3.org/2000/svg" width="'+width+'" height="'+height+'" viewBox="0 0 '+width+' '+height+'">'+rects.join("")+'</svg>';
}

export function openLabelPrint(title:string,labels:Array<{code:string;order:string;line1:string;line2?:string}>,profile:HardwareProfile){
  if(typeof window==="undefined")return;
  const w=window.open("","_blank");
  if(!w)return;
  const width=Math.max(30,Number(profile.label_width_mm||50));
  const height=Math.max(18,Number(profile.label_height_mm||25));
  const cards=labels.map(x=>'<div class="label"><div class="brand">FAB CLEAN</div><div class="order">'+escapeHtml(x.order)+'</div><div class="line">'+escapeHtml(x.line1)+'</div><div class="sub">'+escapeHtml(x.line2||"")+'</div><div class="barcode">'+code128Svg(x.code,48,1.5)+'</div><div class="code">'+escapeHtml(x.code)+'</div></div>').join("");
  w.document.write('<html><head><title>'+escapeHtml(title)+'</title><meta name="viewport" content="width=device-width,initial-scale=1"/><style>@page{margin:0}body{font-family:Arial,sans-serif;margin:0;padding:4mm;display:flex;gap:2mm;flex-wrap:wrap}.label{box-sizing:border-box;width:'+width+'mm;height:'+height+'mm;border:1px solid #222;padding:2mm;overflow:hidden;display:flex;flex-direction:column;align-items:center;justify-content:center;page-break-inside:avoid}.brand{font-size:9pt;font-weight:700;letter-spacing:1px}.order{font-size:13pt;font-weight:800}.line{font-size:9pt;font-weight:700;text-align:center}.sub{font-size:7pt}.barcode{margin-top:1mm;transform:scale(.78);transform-origin:center}.code{font-size:8pt;font-weight:700;letter-spacing:.6px}@media print{body{padding:0;gap:0}.label{border:0}}</style></head><body>'+cards+'<script>window.onload=function(){setTimeout(function(){window.print()},150)}</script></body></html>');
  w.document.close();
}

function escapeHtml(v:string){
  return String(v||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

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
  receipt_paper:"58mm"|"80mm"|"a4";
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
  receipt_paper:"80mm",
};

export function validateProfile(p:HardwareProfile){
  if(!['browser','zpl','tspl'].includes(p.printer_mode)||![203,300].includes(p.printer_dpi)||!['58mm','80mm','a4'].includes(p.receipt_paper))throw new Error('Select a supported printer mode, DPI and receipt size.');
  for(const [key,min,max] of [['label_width_mm',30,110],['label_height_mm',25,150],['label_gap_mm',0,10]] as const){
    if(typeof p[key]!=='number'||!Number.isFinite(p[key])||p[key]<min||p[key]>max)throw new Error(`${key} must be between ${min} and ${max}.`);
  }
  if(p.scanner_mode!=='hid_keyboard'||typeof p.scanner_uppercase!=='boolean'||[p.scanner_prefix,p.scanner_suffix].some(v=>typeof v!=='string'||v.length>40||/[\x00-\x1f]/.test(v)))throw new Error('Invalid scanner profile.');
  return p;
}
export function profileFromSettings(settings:any):HardwareProfile{
  const p={...defaultHardwareProfile};
  for(const [key,value] of Object.entries(settings?.hardware_profile||{})){
    if(!Object.prototype.hasOwnProperty.call(defaultHardwareProfile,key))continue;
    const candidate={...p,[key]:value};
    try{validateProfile(candidate);Object.assign(p,candidate);}catch{/* Legacy invalid values use safe defaults. */}
  }
  return p;
}

export function normalizeScan(raw:string,profile:HardwareProfile){
  let value=String(raw||"").trim();
  if(profile.scanner_prefix&&value.startsWith(profile.scanner_prefix)) value=value.slice(profile.scanner_prefix.length);
  if(profile.scanner_suffix&&value.endsWith(profile.scanner_suffix)) value=value.slice(0,-profile.scanner_suffix.length);
  value=value.trim();
  return profile.scanner_uppercase?value.toUpperCase():value;
}

const dots=(mm:number,dpi:number)=>Math.max(1,Math.round(mm*dpi/25.4));
const printerText=(v:any)=>String(v??'').replace(/[^a-zA-Z0-9 .,:/()_-]/g,' ').slice(0,32);
export type PrintLabel={code:string;order:string;line1:string;line2?:string};
export function labelGeometry(code:string,profile:HardwareProfile){
  validateProfile(profile);
  if(!/^[A-Za-z0-9-]{1,64}$/.test(code))throw new Error('Barcode must contain only letters, digits and hyphens; identifiers are never changed for printing.');
  const width=dots(profile.label_width_mm,profile.printer_dpi),height=dots(profile.label_height_mm,profile.printer_dpi);
  const modules=(code.length+2)*11+13+20;
  const moduleWidth=Math.floor((width-16)/modules);
  if(moduleWidth<1)throw new Error('Barcode does not fit this label. Select a wider label.');
  const barHeight=Math.floor(height*.27),barcodeWidth=modules*moduleWidth;
  return {width,height,moduleWidth,barHeight,x:Math.floor((width-barcodeWidth)/2)+10*moduleWidth,y:Math.floor(height*.48)};
}
export function generateLabelCommands(labels:PrintLabel[],profile:HardwareProfile,mode:'zpl'|'tspl'){
  if(!labels.length||labels.length>100)throw new Error('Select between 1 and 100 labels.');
  return labels.map(label=>{
    const g=labelGeometry(label.code,profile),font=Math.max(12,Math.floor(g.height*.095));
    const lines=[printerText(label.order),printerText(label.line1),printerText(label.line2||'')];
    if(mode==='zpl')return ['^XA','^PW'+g.width,'^LL'+g.height,'^LH0,0',...lines.map((text,i)=>`^FO8,${8+i*(font+2)}^A0N,${font},${font}^FD${text}^FS`),`^FO${g.x},${g.y}^BY${g.moduleWidth},2,${g.barHeight}^BCN,${g.barHeight},N,N,N^FD${label.code}^FS`,`^FO8,${g.y+g.barHeight+4}^A0N,${font},${font}^FD${label.code}^FS`,'^XZ'].join('\n');
    return [`SIZE ${profile.label_width_mm} mm,${profile.label_height_mm} mm`,`GAP ${profile.label_gap_mm} mm,0 mm`,'DIRECTION 1','CLS',...lines.map((text,i)=>`TEXT 8,${8+i*20},"0",0,1,1,"${text}"`),`BARCODE ${g.x},${g.y},"128",${g.barHeight},0,0,${g.moduleWidth},${g.moduleWidth},"${label.code}"`,`TEXT 8,${g.y+g.barHeight+4},"0",0,1,1,"${label.code}"`,'PRINT 1'].join('\n');
  }).join('\n');
}
export function generateZpl(order:any,garments:any[],profile:HardwareProfile){return generateLabelCommands(garments.map(g=>({code:g.garment_code,order:order.order_number,line1:g.service_name})),profile,'zpl');}
export function generateTspl(order:any,garments:any[],profile:HardwareProfile){return generateLabelCommands(garments.map(g=>({code:g.garment_code,order:order.order_number,line1:g.service_name})),profile,'tspl');}
export function downloadRaw(filename:string,content:string){
  if(typeof window==='undefined'||typeof document==='undefined')throw new Error('Open FabClean in a browser to download print files.');
  const blob=new Blob([content],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename.replace(/[^a-zA-Z0-9_.-]/g,'_');a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
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
  const safe=String(value||"");
  if(!/^[\x20-\x7E]{1,64}$/.test(safe))throw new Error("Barcode identifier cannot be printed without changing its value.");
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

export function labelHtml(title:string,labels:PrintLabel[],profile:HardwareProfile){
  if(!labels.length||labels.length>100)throw new Error('Select between 1 and 100 labels.');
  labels.forEach(l=>labelGeometry(l.code,profile));
  const cards=labels.map(x=>'<section class="label"><div class="order">'+escapeHtml(x.order)+'</div><div class="line">'+escapeHtml(x.line1)+'</div><div class="sub">'+escapeHtml(x.line2||'')+'</div><div class="barcode">'+code128Svg(x.code,40,1)+'</div><div class="code">'+escapeHtml(x.code)+'</div></section>').join('');
  return '<!doctype html><html><head><title>'+escapeHtml(title)+'</title><meta name="viewport" content="width=device-width,initial-scale=1"/><style>@page{size:'+profile.label_width_mm+'mm '+profile.label_height_mm+'mm;margin:0}*{box-sizing:border-box}body{font-family:Arial,sans-serif;margin:0}.label{width:'+profile.label_width_mm+'mm;height:'+profile.label_height_mm+'mm;padding:1mm;display:flex;flex-direction:column;align-items:center;justify-content:center;break-after:page;overflow:hidden}.label:last-child{break-after:auto}.order{font-size:9pt;font-weight:bold}.line{font-size:7pt;max-width:100%;white-space:nowrap;overflow:hidden}.sub{font-size:6pt}.barcode{width:100%;text-align:center;margin-top:1mm}.barcode svg{max-width:100%;height:8mm}.code{font-size:6pt}nav{padding:12px;background:#eee}@media print{nav{display:none}}</style></head><body><nav><button onclick="window.print()">Print labels</button><p>Use actual size / 100% scale, zero margins and matching label media. Confirm the physical print in FabClean after checking the result.</p></nav>'+cards+'</body></html>';
}
export function openPrintDocument(html:string){
  if(typeof window==='undefined'||typeof window.open!=='function')throw new Error('System printing is available in the browser. Open FabClean in your phone or tablet browser.');
  const popup=window.open('','_blank');
  if(!popup)throw new Error('Pop-up blocked. Allow pop-ups for FabClean and retry.');
  popup.opener=null;popup.document.write(html);popup.document.close();
}
export function openLabelPrint(title:string,labels:PrintLabel[],profile:HardwareProfile){openPrintDocument(labelHtml(title,labels,profile));}

function escapeHtml(v:string){
  return String(v||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

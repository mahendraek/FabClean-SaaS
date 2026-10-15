const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
function moduleFrom(file,extra={}){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/'+file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,...extra});return exports;}
const hardware=moduleFrom('hardware.ts'),receipt=moduleFrom('receipt.ts',{require:name=>{assert.equal(name,'@/src/hardware');return hardware;}});
const profile=hardware.defaultHardwareProfile;
const labels=[{code:'FC-1001-G001',order:'FC-1001',line1:'Wash "\nPRINT 999\n^XZ~RESET<script>',line2:'Item 1'}];
test('hardware profiles validate sizes, finite DPI and enum values; legacy invalid fields fall back',()=>{
 for(const override of [{label_width_mm:NaN},{label_height_mm:1},{printer_dpi:600},{printer_mode:'usb'},{receipt_paper:'evil'},{scanner_uppercase:'yes'}])assert.throws(()=>hardware.validateProfile({...profile,...override}));
 assert.equal(hardware.profileFromSettings({hardware_profile:{label_width_mm:1,printer_mode:'tspl'}}).label_width_mm,50);
 assert.equal(hardware.profileFromSettings({hardware_profile:{receipt_paper:'58mm'}}).receipt_paper,'58mm');
});
test('ZPL/TSPL reject changed barcodes and prevent data from adding commands',()=>{
 for(const code of ['FC^XZ','A\nPRINT 999','élève','A'.repeat(65),''])assert.throws(()=>hardware.generateLabelCommands([{...labels[0],code}],profile,'zpl'));
 const zpl=hardware.generateLabelCommands(labels,profile,'zpl'),tspl=hardware.generateLabelCommands(labels,profile,'tspl');
 assert.equal(zpl.match(/\^XA/g).length,1);assert.equal(zpl.match(/\^XZ/g).length,1);assert.doesNotMatch(zpl,/~RESET/);
 assert.equal(tspl.split('\n').filter(v=>v.startsWith('PRINT')).length,1);assert.doesNotMatch(tspl,/^PRINT 999$/m);
 assert.match(zpl,/FC-1001-G001/);assert.match(tspl,/FC-1001-G001/);
 assert.throws(()=>hardware.generateLabelCommands([],profile,'zpl'));assert.throws(()=>hardware.generateLabelCommands(Array(101).fill(labels[0]),profile,'tspl'));
});
test('barcodes fit selected label geometry at 203 and 300 DPI or fail explicitly',()=>{
 for(const dpi of [203,300]){const p={...profile,printer_dpi:dpi},g=hardware.labelGeometry(labels[0].code,p);assert.ok(g.moduleWidth>=1);assert.ok(g.y+g.barHeight+4<g.height);assert.ok(g.width===Math.round(50*dpi/25.4));}
 assert.throws(()=>hardware.labelGeometry('A'.repeat(64),{...profile,label_width_mm:30}));
 assert.throws(()=>hardware.code128Svg('AB\nCD'));
 const html=hardware.labelHtml('Tags',labels,profile);assert.match(html,/size:50mm 25mm/);assert.match(html,/quiet|viewBox/);assert.doesNotMatch(html,/<script>/);assert.match(html,/&lt;script&gt;/);
});
test('blocked popups and native system printing fail explicitly',()=>{
 assert.throws(()=>hardware.openPrintDocument('<p>Test</p>'),/browser/);
 const blocked=moduleFrom('hardware.ts',{window:{open:()=>null}});assert.throws(()=>blocked.openPrintDocument('<p>Test</p>'),/Pop-up blocked/);
});
function data(){return {profile,business:{business_name:'Laundry <script>bad()</script>'},garments:[],receipt:{paid_total:4,balance_due:6,order:{order_number:'FC-1001',barcode_value:'FC1001',currency:'INR',customer:{name:'A & B'},items:[{quantity:2,unit_price:5,service_name:'Wash'}],subtotal:10,total:10,pricing_status:'estimated'}}};}
test('receipt output preserves saved currency, ledger values, paper width, historical tax and HTML escaping',()=>{
 for(const paper of ['58mm','80mm','a4']){const d=data();d.profile={...profile,receipt_paper:paper};const html=receipt.receiptHtml(d);assert.match(html,/INR 10.00/);assert.match(html,/INR 4.00/);assert.match(html,/INR 6.00/);assert.doesNotMatch(html,/\$|<script>/);assert.match(html,/&lt;script&gt;/);assert.match(html,/Estimated pricing/);if(paper!=='a4')assert.match(html,new RegExp('max-width:'+(paper==='58mm'?54:76)+'mm'));}
 const legacy=data();delete legacy.receipt.order.currency;assert.match(receipt.receiptHtml(legacy),/UNSPECIFIED 10.00/);
 legacy.receipt.order.tax_snapshot={currency:'USD'};legacy.receipt.order.tax=1;assert.match(receipt.receiptHtml(legacy),/Recorded tax/);assert.match(receipt.receiptHtml(legacy),/USD 1.00/);
 const invalid=data();invalid.receipt.order.total='invalid';assert.throws(()=>receipt.receiptHtml(invalid),/financial data/);
});

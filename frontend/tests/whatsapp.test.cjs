const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const api={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/whatsapp.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:api});
test('WhatsApp receipt links safely encode totals, Unicode and query delimiters',()=>{
 const message='Laundry & care\nSubtotal: USD 10.50\nTotal: USD 10.50\nThanks, Zoë! #receipt';
 const url=new URL(api.whatsappReceiptURL('+15550102030',message));
 assert.equal(url.origin,'https://wa.me');assert.equal(url.pathname,'/15550102030');assert.equal(url.searchParams.get('text'),message);assert.equal([...url.searchParams.keys()].length,1);
});
test('WhatsApp links reject guessed country codes, extensions and hostile phone paths',()=>{
 for(const value of ['5550102030','+0123456789','+15550102030/other','+15550102030?text=other','+15550102030 ext 2','+1555'])assert.throws(()=>api.whatsappReceiptURL(value,'Receipt'));
});
test('WhatsApp sharing refuses empty or oversized messages without truncating receipt contents',()=>{
 assert.throws(()=>api.whatsappReceiptURL('+15550102030',' '));
 assert.throws(()=>api.whatsappReceiptURL('+15550102030','a'.repeat(6001)));
 assert.throws(()=>api.whatsappReceiptURL('+15550102030','😀'.repeat(1501)));
 assert.ok(api.whatsappReceiptURL('+15550102030','😀'.repeat(1500)));
});

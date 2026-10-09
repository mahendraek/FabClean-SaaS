// Run against a local exported app; API traffic is mocked and no production data is used.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(__dirname, '../dist');
const server = http.createServer((req,res) => {
 let file=path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));
 if (!file.startsWith(root+'/') && file!==root) {res.writeHead(403);return res.end();}
 if(fs.existsSync(file) && fs.statSync(file).isDirectory())file=path.join(file,'index.html');
 if(!fs.existsSync(file))file+='.html';
 if(!fs.existsSync(file)){res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');
 fs.createReadStream(file).pipe(res);
});
(async () => {
 const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath:process.env.CHROMIUM_EXECUTABLE} : {}), args:['--no-sandbox']});
 try {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  for(const mobile of [false,true]) {
   const session = await browser.newContext({viewport:mobile ? {width:390,height:844} : {width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   const page=await session.newPage(), errors=[]; page.on('pageerror',e=>{errors.push(e.message);console.error('page error:',e.message)});
   let active='s1', puts=0;
   const ctx=()=>({staff:{id:'u1',name:'Owner',role:'owner'},active_brand:{id:'b1',name:'Brand One'},active_store:{id:active,brand_id:'b1',name:active==='s1'?'Store One':'Store Two'},brands:[{id:'b1',name:'Brand One'},{id:'b2',name:'Empty Brand'}],stores:[{id:'s1',brand_id:'b1',name:'Store One',store_code:'ONE'},{id:'s2',brand_id:'b1',name:'Store Two',store_code:'TWO'}]});
   await page.addInitScript(()=>{if(!localStorage.getItem('fixture_initialized')){localStorage.setItem('fixture_initialized','yes');localStorage.setItem('fabclean_staff',JSON.stringify({id:'u1',name:'Owner',role:'owner'}));localStorage.setItem('fabclean_session','fixture-token');}});
   await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname; let body={};
    if(path==='/api/context'){if(req.method()==='PUT'){const selection=req.postDataJSON();assert.equal(selection.brand_id,'b1');assert.ok(['s1','s2'].includes(selection.store_id));active=selection.store_id;puts++}body=ctx();}
    else if(path==='/api/auth/sign-in'){active='s1';body={staff:{id:'u1',name:'Owner',role:'owner'},token:'new-fixture-token'};}
    else if(path==='/api/auth/status')body={staff_count:1,bootstrap_required:false};
    else if(path==='/api/settings')body={business_name:active==='s1'?'Store One Settings':'Store Two Settings'};
    else if(path==='/api/orders')body={orders:[]};
    await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(body)});
   });
   const base=`http://127.0.0.1:${server.address().port}`;
   await page.goto(base+'/orders');await page.getByText('Switch store',{exact:true}).click();
   await page.getByText('Empty Brand',{exact:true}).click();await page.getByText('No accessible stores for this brand.',{exact:true}).waitFor();
   await page.getByText('Brand One',{exact:true}).click();await page.getByText('Store Two · TWO',{exact:true}).click();
   await page.getByText('Cancel',{exact:true}).click();assert.equal(puts,0);
   await page.getByText('Switch store',{exact:true}).click();await page.getByText('Store Two · TWO',{exact:true}).click();await page.getByText('Confirm switch',{exact:true}).click();
   await page.getByText('Brand One · Store Two',{exact:true}).waitFor();await page.waitForURL(base+'/');assert.equal(puts,1);
   await page.reload();await page.getByText('Brand One · Store Two',{exact:true}).waitFor();
   assert.deepEqual(JSON.parse(await page.evaluate(()=>localStorage.getItem('fabclean_context_u1'))),{brand_id:'b1',store_id:'s2'});
   await page.getByText('Owner · Sign out',{exact:true}).click();await page.waitForURL(base+'/sign-in');
   await page.locator('input').nth(0).fill('owner@example.com');await page.locator('input').nth(1).fill('test-password');
   await page.getByText('Sign In',{exact:true}).click();await page.getByText('Brand One · Store Two',{exact:true}).waitFor();assert.equal(puts,2);
   assert.deepEqual(errors,[]);console.log(`${mobile?'mobile web':'desktop'}: cancel, empty brand, switch, screen reset, refresh and relogin passed`);
   await session.close();
  }
 } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});

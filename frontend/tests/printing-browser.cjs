const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.env.PRINTING_TEST_FIXTURES,'utf8'));
const api=process.env.PRINTING_TEST_API||'http://127.0.0.1:8005';
if(!['127.0.0.1','localhost'].includes(new URL(api).hostname))throw new Error('Disposable local API required');
const root=path.resolve(__dirname,'../dist');
const server=http.createServer((req,res)=>{let file=path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));if(!file.startsWith(root+'/')){res.writeHead(403);return res.end();}if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');if(!fs.existsSync(file))file+='.html';if(!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});try{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 for(const mobile of [false,true]){
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile});const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(f=>{localStorage.setItem('fabclean_session',f.token);localStorage.setItem('fabclean_staff',JSON.stringify({id:f.user,name:'Printing Manager',role:'manager'}));},fixture);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url()),response=await route.fetch({url:api+u.pathname+u.search});await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*'}});});
  async function call(method,route,data,token=fixture.token){return page.request.fetch(api+'/api'+route,{method,headers:{'X-Session-Token':token},...(data?{data}:{})});}
  const getCounts=async()=>Object.fromEntries((await (await call('GET','/orders/'+fixture.order+'/garments')).json()).garments.map(g=>[g.garment_code,g.tag_print_count]));
  const before=await getCounts();
  await page.goto(base+'/order-detail?id='+fixture.order);await page.getByRole('button',{name:'Print Receipt',exact:true}).click();
  await page.getByText('Total: INR 10.00',{exact:true}).waitFor();
  const popupEvent=page.waitForEvent('popup');await page.getByRole('button',{name:'Open print document',exact:true}).click();
  const popup=await popupEvent;await popup.locator('.sumrow.total').getByText('INR 10.00',{exact:true}).waitFor();assert.doesNotMatch(await popup.locator('body').innerText(),/\$/);
  await popup.emulateMedia({media:'print'});assert.ok(await popup.locator('.receipt').evaluate(el=>el.getBoundingClientRect().width)<300);
  await popup.screenshot({path:'/tmp/printing-receipt-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});await popup.close();
  await page.getByRole('button',{name:'Cancel confirmation',exact:true}).click();assert.deepEqual(await getCounts(),before);
  // Popup rejection must leave no confirmation or fabricated success.
  await page.evaluate(()=>{window.savedOpen=window.open;window.open=()=>null;});await page.getByRole('button',{name:'Open print document',exact:true}).click();await page.getByText('Pop-up blocked. Allow pop-ups for FabClean and retry.',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Confirm physical print',exact:true}).count(),0);await page.evaluate(()=>{window.open=window.savedOpen;});
  await page.goto(base+'/print-preview?id='+fixture.order+'&kind=garments');await page.getByRole('checkbox').first().waitFor();
  const labelPopup=page.waitForEvent('popup');await page.getByRole('button',{name:'Open print document',exact:true}).click();const labels=await labelPopup;
  await labels.locator('.label').first().waitFor();await labels.emulateMedia({media:'print'});
  assert.equal(await labels.locator('.label').count(),Object.keys(before).length);
  const pdf=await labels.pdf({preferCSSPageSize:true,path:'/tmp/printing-tags-'+(mobile?'mobile':'desktop')+'.pdf'});assert.equal((pdf.toString('latin1').match(/\/Type \/Page\b/g)||[]).length,Object.keys(before).length);
  await labels.screenshot({path:'/tmp/printing-tags-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});await labels.close();assert.deepEqual(await getCounts(),before);
  await page.getByRole('button',{name:'Confirm physical print',exact:true}).click();await page.getByText('Physical print confirmation saved.',{exact:true}).waitFor();
  const after=await getCounts();assert.deepEqual(after,Object.fromEntries(Object.entries(before).map(([k,v])=>[k,v+1])));
  // Settings persist store-locally, invalid dimensions fail visibly, then raw export works.
  await page.goto(base+'/hardware');await page.getByRole('button',{name:'Save Hardware Profile',exact:true}).waitFor();
  await page.getByLabel('Label width (mm)',{exact:true}).fill('1');await page.getByRole('button',{name:'Save Hardware Profile',exact:true}).click();await page.getByText('label_width_mm must be between 30 and 110.',{exact:true}).waitFor();
  await page.getByLabel('Label width (mm)',{exact:true}).fill('50');await page.getByRole('radio',{name:'Printer mode zpl',exact:true}).click();await page.getByRole('radio',{name:'Receipt paper 58mm',exact:true}).click();await page.getByRole('button',{name:'Save Hardware Profile',exact:true}).click();await page.getByText('Hardware profile saved',{exact:true}).waitFor();
  await page.goto(base+'/print-preview?id='+fixture.order+'&kind=garments');const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download printer file',exact:true}).click();const file=await download;const raw=fs.readFileSync(await file.path(),'utf8');assert.equal((raw.match(/\^XA/g)||[]).length,Object.keys(before).length);assert.deepEqual(await getCounts(),after);
  await page.getByRole('button',{name:'Cancel confirmation',exact:true}).click();
  const foreign=await call('GET','/orders/'+fixture.order+'/print-preview',undefined,fixture.foreign_token);assert.equal(foreign.status(),404);
  // Restore defaults for the next viewport; no physical output is sent.
  await call('PUT','/settings',{hardware_profile:{receipt_paper:'80mm',printer_mode:'browser',label_width_mm:50}});
  assert.deepEqual(errors,[]);console.log((mobile?'mobile web':'desktop')+': INR receipt, popup/cancel, exact label PDF pages, confirmation counts, invalid profile, raw export and foreign denial passed');
  await context.close();
 }
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.env.NOTIFICATION_TEST_FIXTURES,'utf8'));
const api=process.env.NOTIFICATION_TEST_API||'http://127.0.0.1:8005';
if(!['127.0.0.1','localhost'].includes(new URL(api).hostname))throw new Error('Disposable local API required');
const root=path.resolve(__dirname,'../dist');
const server=http.createServer((req,res)=>{let file=path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));if(!file.startsWith(root+'/')){res.writeHead(403);return res.end();}if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');if(!fs.existsSync(file))file+='.html';if(!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});try{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 for(const mobile of [false,true]){
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile});const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(f=>{localStorage.setItem('fabclean_session',f.token);localStorage.setItem('fabclean_staff',JSON.stringify({id:f.user,name:'Receipt Manager',role:'manager'}));},fixture);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url()),response=await route.fetch({url:api+u.pathname+u.search});await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*'}});});
  async function call(method,route,data,token=fixture.token){return page.request.fetch(api+'/api'+route,{method,headers:{'X-Session-Token':token},...(data?{data}:{})});}
  const prefs='/customers/'+fixture.customer+'/communication-preferences';
  assert.equal((await call('PUT',prefs,{email_opt_in:false,sms_opt_in:false,receipts:false,status_updates:false})).status(),200);
  await page.goto(base+'/customer-profile?id='+fixture.customer);
  await page.getByLabel('Email consent',{exact:true}).waitFor();await page.getByLabel('Email consent',{exact:true}).click();await page.getByLabel('Order and payment receipts',{exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Save communication preferences',exact:true}).isDisabled(),false,'Draft consent should enable save');
  let saving=page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+prefs&&r.request().method()==='PUT');await page.getByRole('button',{name:'Save communication preferences',exact:true}).click();assert.equal((await saving).status(),400);
  await page.getByText('Record how the customer gave consent before opting in',{exact:true}).waitFor();
  await page.getByLabel('Customer consent note',{exact:true}).fill('Synthetic browser fixture consent');saving=page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+prefs&&r.request().method()==='PUT');await page.getByRole('button',{name:'Save communication preferences',exact:true}).click();assert.equal((await saving).status(),200);
  await page.getByText('Communication preferences saved',{exact:true}).waitFor();
  await page.goto(base+'/order-detail?id='+fixture.order);
  await page.getByRole('button',{name:'Queue email/SMS receipt',exact:true}).click();
  await page.getByText('Receipts & notifications',{exact:true}).waitFor();
  const rows=(await (await call('GET','/notifications/outbox')).json()).notifications;
  const row=rows.find(r=>r.order_id===fixture.order&&r.channel==='email'&&r.status==='queued');assert.ok(row);assert.equal(row.delivery.receipt.tax,.5);assert.equal(row.delivery.receipt.total,10.5);assert.match(row.message,/Fixture Illinois \(5%\)/);
  await page.getByRole('button',{name:'Review delivery '+row.id,exact:true}).click();await page.getByRole('button',{name:'Cancel delivery',exact:true}).click();assert.equal((await (await call('GET','/notifications/outbox')).json()).notifications.find(r=>r.id===row.id).status,'queued');
  await page.getByRole('button',{name:'Review delivery '+row.id,exact:true}).click();
  assert.equal((await call('PUT',prefs,{email_opt_in:false})).status(),200);
  const send=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/outbox/'+row.id+'/dispatch');await page.getByRole('button',{name:'Confirm delivery',exact:true}).click();assert.equal((await send).status(),200);
  assert.equal((await (await call('GET','/notifications/outbox')).json()).notifications.find(r=>r.id===row.id).status,'suppressed');
  assert.equal((await call('POST','/notifications/outbox/'+row.id+'/dispatch',undefined,fixture.foreign_token)).status(),404);
  await page.goto(base+'/configuration');await page.getByLabel('Notification email sender',{exact:true}).waitFor();await page.getByLabel('Notification email sender',{exact:true}).fill('sender@example.com');saving=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/configuration/store'&&r.request().method()==='PUT');await page.getByRole('button',{name:'Save notification email sender',exact:true}).click();assert.equal((await saving).status(),200);
  await page.getByLabel('Template order_receipt',{exact:true}).fill('Thank you {name} from {business_name}');saving=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/configuration/store'&&r.request().method()==='PUT');await page.getByRole('button',{name:'Save notification templates',exact:true}).click();assert.equal((await saving).status(),200);
  await page.goto(base+'/taxes');await page.getByText('Tax rate provider',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Look up store tax rate',exact:true}).isDisabled(),true);
  // Mock only provider preview/import UI; backend adapter/import semantics have real PostgreSQL tests.
  await page.route('**/api/taxes/provider',route=>route.fulfill({json:{provider:'Fixture provider',configured:true,coverage:'Synthetic US lookup',billing_note:'Fixture only'}}));
  await page.route('**/api/taxes/provider/lookup',route=>route.fulfill({json:{id:'fixture-quote',provider:'Fixture provider',jurisdiction:'Fixture Chicago',rate:'5',note:'Synthetic rate; verify location and services',retrieved_at:'2026-01-01',expires_at:'2026-01-02'}}));
  await page.route('**/api/taxes/provider/fixture-quote/import',route=>{assert.deepEqual(route.request().postDataJSON(),{jurisdiction_verified:true,service_taxability_verified:true});return route.fulfill({json:{id:'fixture-rate'}});});
  await page.reload();await page.getByRole('button',{name:'Look up store tax rate',exact:true}).click();await page.getByText('Fixture provider: Fixture Chicago · 5%',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Import verified location rate',exact:true}).isDisabled(),true);
  await page.getByLabel('Verify tax jurisdiction',{exact:true}).click();await page.getByLabel('Verify service taxability',{exact:true}).click();await page.getByRole('button',{name:'Import verified location rate',exact:true}).click();
  await page.screenshot({path:'/tmp/pr11-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});assert.deepEqual(errors,[]);
  console.log((mobile?'mobile web':'desktop')+': real API consent, receipt tax totals, cancel/opt-out, foreign denial, sender/templates and controlled provider review UI passed');await context.close();
 }
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

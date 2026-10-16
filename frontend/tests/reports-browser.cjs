const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.env.REPORTING_TEST_FIXTURES,'utf8'));
const api=process.env.REPORTING_TEST_API||'http://127.0.0.1:8005';
if(!['127.0.0.1','localhost'].includes(new URL(api).hostname))throw new Error('Disposable local API required');
const root=path.resolve(__dirname,'../dist');
const server=http.createServer((req,res)=>{let file=path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));if(!file.startsWith(root+'/')){res.writeHead(403);return res.end();}if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');if(!fs.existsSync(file))file+='.html';if(!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});try{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 for(const mobile of [false,true]){
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile});const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(f=>{localStorage.setItem('fabclean_session',f.token);localStorage.setItem('fabclean_staff',JSON.stringify({id:f.user,name:'Reports Admin',role:'manager'}));},fixture);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url()),response=await route.fetch({url:api+u.pathname+u.search});await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*'}});});
  async function call(method,route,data,token=fixture.token){return page.request.fetch(api+'/api'+route,{method,headers:{'X-Session-Token':token},...(data?{data}:{})});}
  await page.goto(base+'/reports');
  await page.getByRole('button',{name:'Apply filters',exact:true}).waitFor();
  await page.getByLabel('Report from date',{exact:true}).fill('2026-03-08');
  await page.getByLabel('Report to date',{exact:true}).fill('2026-03-08');
  await page.getByRole('combobox',{name:'Report store',exact:true}).click();
  await page.getByRole('button',{name:'Report store: All brand stores',exact:true}).click();
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await page.getByText('28 matching orders. Showing 1–25. CSV contains all matching orders, up to 5,000.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Next page',exact:true}).click();
  await page.getByText('28 matching orders. Showing 26–28. CSV contains all matching orders, up to 5,000.',{exact:true}).waitFor();
  await page.screenshot({path:'/tmp/reports-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV',exact:true}).click();
  const downloaded=await download;const csv=fs.readFileSync(await downloaded.path(),'utf8');
  assert.match(csv,/Market Reports Store/);assert.match(csv,/Central Reports Store/);assert.doesNotMatch(csv,/Foreign Reports Store|Customer/);
  assert.equal(csv.trim().split('\n').length,29);
  const summaryDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Export summary CSV',exact:true}).click();
  const summary=fs.readFileSync(await (await summaryDownload).path(),'utf8');assert.match(summary,/Selected stores/);assert.match(summary,/Net collected/);
  await page.getByRole('combobox',{name:'Report status',exact:true}).click();await page.getByRole('button',{name:'Report status: cancelled',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Export CSV',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByText('No orders in this period.',{exact:true}).waitFor();
  await page.getByLabel('Report from date',{exact:true}).fill('bad-date');await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await page.getByText('Use YYYY-MM-DD dates in order, covering at most 366 days',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Export CSV',exact:true}).isDisabled(),true);
  await page.getByLabel('Report from date',{exact:true}).fill('2026-03-08');
  await page.getByRole('combobox',{name:'Report status',exact:true}).click();await page.getByRole('button',{name:'Report status: All statuses',exact:true}).click();
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByText('28 matching orders. Showing 1–25. CSV contains all matching orders, up to 5,000.',{exact:true}).waitFor();
  // A failed report must not leave stale numbers or a usable export behind.
  await page.route('**/api/reports/summary?**',route=>route.fulfill({status:503,headers:{'access-control-allow-origin':'*'},contentType:'application/json',body:JSON.stringify({detail:'Controlled reporting outage'})}));
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByText('Controlled reporting outage',{exact:true}).waitFor();
  assert.equal(await page.getByText('Order value and collections',{exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Export CSV',exact:true}).isDisabled(),true);
  await page.unroute('**/api/reports/summary?**');
  for(const endpoint of ['summary','orders','export']){
   assert.equal((await call('GET','/reports/'+endpoint+'?scope=brand',undefined,fixture.manager_token)).status(),403);
   assert.equal((await call('GET','/reports/'+endpoint+'?scope=brand&store_id='+fixture.stores[2])).status(),404);
  }
  await page.screenshot({path:'/tmp/reports-error-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log((mobile?'mobile web':'desktop')+': brand filters, actual pagination, CSV downloads, empty/invalid/error recovery and authorization passed');
  await context.close();
 }
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

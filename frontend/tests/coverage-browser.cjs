const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.env.COVERAGE_TEST_FIXTURES,'utf8')),api=process.env.COVERAGE_TEST_API||'http://127.0.0.1:8005';
if(!['localhost','127.0.0.1'].includes(new URL(api).hostname))throw new Error('Disposable local API required');
const root=path.resolve(__dirname,'../dist'),server=http.createServer((req,res)=>{let file=path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));if(!file.startsWith(root+'/')){res.writeHead(403);return res.end();}if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');if(!fs.existsSync(file))file+='.html';if(!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{}),args:['--no-sandbox']});try{await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
for(const mobile of [false,true]){
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(f=>{localStorage.setItem('fabclean_session',f.token);localStorage.setItem('fabclean_staff',JSON.stringify({id:f.user,name:'Coverage Manager',role:'manager'}));},fixture);
 // Provider availability is checked independently; deterministic tiles/offline mode
 // isolate geometry and real API behaviour from third-party network variability.
 await page.route('https://tile.openstreetmap.org/**',route=>mobile?route.abort('blockedbyclient'):route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jED8AAAAASUVORK5CYII=','base64')}));
 await page.route('**/api/**',async route=>{const u=new URL(route.request().url()),response=await route.fetch({url:api+u.pathname+u.search});await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*'}});});
 async function request(method,route,data,token=fixture.token){return page.request.fetch(api+'/api'+route,{method,headers:{'X-Session-Token':token},...(data?{data}:{})});}
 async function call(method,route,data,token){const r=await request(method,route,data,token);assert.equal(r.status(),200,await r.text());return r.json();}
 let doc=await call('GET','/coverage');await call('PUT','/coverage',{revision:doc.revision,payload:{enabled:false,mode:'radius',unit:'km',radius:10,zones:[]}});
 await page.goto(base+'/coverage');await page.getByRole('button',{name:'Save store coverage',exact:true}).waitFor();await page.getByRole('switch',{name:'Enforce store coverage',exact:true}).click();
 await page.getByLabel('Coverage radius',{exact:true}).fill('10');
 async function save(status=200){const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/coverage'&&r.request().method()==='PUT');await page.getByRole('button',{name:'Save store coverage',exact:true}).click();assert.equal((await response).status(),status);}
 await save();await page.getByText('Store coverage saved',{exact:true}).waitFor();
 const copyright=page.getByRole('link',{name:'© OpenStreetMap contributors · ODbL',exact:true});assert.ok(await copyright.count()>=1);
 if(mobile)await page.getByText('Map tiles unavailable. Coordinate entry and coverage checks still work.',{exact:true}).first().waitFor();
 async function check(lat,lon){await page.getByLabel('Service address',{exact:true}).fill('10 Coverage Street');await page.getByLabel('Address latitude',{exact:true}).fill(String(lat));await page.getByLabel('Address longitude',{exact:true}).fill(String(lon));const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/coverage/check');await page.getByRole('button',{name:'Confirm address pin and check coverage',exact:true}).click();const r=await response;assert.equal(r.status(),200);return r.json();}
 assert.equal((await check(41.5,-87.5)).eligible,true);assert.equal((await check(40,-87.5)).eligible,false);
 await page.getByRole('button',{name:'Miles',exact:true}).click();await save();doc=await call('GET','/coverage');assert.equal(doc.payload.unit,'mi');assert.ok(Math.abs(doc.payload.radius*1.609344-10)<.00001);
 await page.getByLabel('Coverage radius',{exact:true}).fill('-1');await save(400);await page.getByRole('alert').waitFor();await page.getByLabel('Coverage radius',{exact:true}).fill('6.213712');
 doc=await call('GET','/coverage');await call('PUT','/coverage',{revision:doc.revision,payload:doc.payload});await save(409);await page.getByRole('button',{name:'Refresh coverage',exact:true}).click();await page.getByRole('button',{name:'Polygon zones',exact:true}).click();
 await page.getByLabel('Coverage zone name',{exact:true}).fill('Central Zone');
 for(const [lat,lon] of [[41,-88],[42,-88],[42,-87],[41,-87]]){await page.getByLabel('Vertex latitude',{exact:true}).fill(String(lat));await page.getByLabel('Vertex longitude',{exact:true}).fill(String(lon));await page.getByRole('button',{name:'Add zone vertex',exact:true}).click();}
 await page.getByRole('button',{name:'Add coverage zone',exact:true}).click();await save();assert.equal((await check(41.5,-87.5)).eligible,true);assert.equal((await check(40,-87.5)).eligible,false);
 await page.getByRole('button',{name:'Remove zone Central Zone',exact:true}).click();await page.getByRole('button',{name:'Cancel zone removal',exact:true}).click();assert.equal((await call('GET','/coverage')).payload.zones.length,1);
 const foreign=await call('GET','/coverage',null,fixture.foreign_token);assert.equal(foreign.payload,null);
 const bad=await request('POST','/coverage/check',{latitude:41.5,longitude:-87.5,address:'Test',fulfillment_type:'pickup_only',store_id:'forged'});assert.equal(bad.status(),400);
 // Counter flow checks use the real address component and reject changed pins.
 await page.goto(base+'/walk-in');await page.getByText('Pickup Only',{exact:true}).click();
 assert.equal((await check(40,-87.5)).eligible,false);await page.getByLabel('Address latitude',{exact:true}).fill('41.5');assert.equal(await page.getByText(/Address pin is outside/).count(),0);assert.equal((await check(41.5,-87.5)).eligible,true);
 const map=page.getByRole('button',{name:'Coverage map; tap to select address or zone vertex',exact:true});await map.click({position:{x:120,y:130}});assert.notEqual(await page.getByLabel('Address latitude',{exact:true}).inputValue(),'41.5');
 assert.equal((await check(41.5,-87.5)).eligible,true);
 await page.getByText('Wash',{exact:true}).click();await page.getByPlaceholder('Customer name *',{exact:true}).fill('Counter Coverage '+Date.now());await page.getByPlaceholder('Phone *',{exact:true}).fill('555'+Date.now());
 await page.getByText('Select pickup date',{exact:true}).click();await page.getByText(String(new Date().getDate()),{exact:true}).click();await page.getByText('Slot 0 · 09:00-11:00',{exact:true}).click();
 await page.getByText('Tax: $0.00',{exact:true}).waitFor();
 const created=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/orders'&&r.request().method()==='POST');await page.getByText('Create Order + Garment Barcodes',{exact:true}).click();const createdResponse=await created;assert.equal(createdResponse.status(),200);assert.equal((await createdResponse.json()).coverage_snapshot.eligible,true);
 const orderBody={customer_name:'Coverage Browser',customer_phone:'555-map-'+(mobile?'m':'d'),items:[{service_id:'shared-service',service_name:'Wash',unit_price:10,quantity:1}],fulfillment_type:'pickup_only',pickup_date:'2030-01-02',pickup_slot_id:fixture.slot,service_address:'10 Coverage Street',service_latitude:40,service_longitude:-87.5};
 assert.equal((await request('POST','/orders',orderBody)).status(),409);const order=await call('POST','/orders',{...orderBody,service_latitude:41.5});assert.equal(order.coverage_snapshot.eligible,true);assert.equal(order.coverage_snapshot.mode,'zones');
 await page.goto(base+'/coverage');await page.getByRole('button',{name:'Save store coverage',exact:true}).waitFor();await page.screenshot({path:'/tmp/coverage-'+(mobile?'mobile':'desktop')+'.png',fullPage:true});assert.deepEqual(errors,[]);console.log((mobile?'mobile web':'desktop')+': radius/zone editor, units, address feedback, stale revision, map pin, tile fallback, API enforcement and store isolation passed');await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

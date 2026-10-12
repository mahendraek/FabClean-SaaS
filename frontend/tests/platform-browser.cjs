// Real local PostgreSQL/API onboarding flows. No production calls or email delivery.
const { chromium } = require('playwright');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path');
const fixtures = JSON.parse(fs.readFileSync(process.env.PLATFORM_TEST_FIXTURES || '/tmp/pr7-browser-fixture.json','utf8'));
const api = process.env.PLATFORM_TEST_API || 'http://127.0.0.1:8005';
if (!['localhost','127.0.0.1'].includes(new URL(api).hostname)) throw new Error('Use a disposable local API');
const root = path.resolve(__dirname,'../dist');
const server = http.createServer((req,res) => {
 let file = path.join(root,decodeURIComponent(new URL(req.url,'http://local').pathname));
 if (!file.startsWith(root+'/')) {res.writeHead(403);return res.end();}
 if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file=path.join(file,'index.html');
 if (!fs.existsSync(file)) file+='.html';
 if (!fs.existsSync(file)) {res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');fs.createReadStream(file).pipe(res);
});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{}),args:['--no-sandbox']});
 try {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
  for (const mobile of [false,true]) {
   const contexts=[],errors=[];
   async function pageFor(superadmin) {
    const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile});contexts.push(context);
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    if (superadmin) await page.addInitScript(data=>{if(!localStorage.getItem('fixture_init')){localStorage.setItem('fixture_init','yes');localStorage.setItem('fabclean_staff',JSON.stringify({id:data.super_user,name:'Platform Admin',role:'owner'}));localStorage.setItem('fabclean_session',data.super_token);}},fixtures);
    await page.route('**/api/**',async route=>{const url=new URL(route.request().url());const response=await route.fetch({url:api+url.pathname+url.search});await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*'}});});
    return page;
   }
   const admin=await pageFor(true),owner=await pageFor(false);
   await admin.goto(base+'/platform-admin');await admin.getByText('Platform online',{exact:true}).waitFor();
   const suffix=Date.now()+'-'+(mobile?'mobile':'desktop'),brandName='Browser Brand '+suffix,email='owner-'+suffix+'@example.invalid';
   await admin.getByLabel('Brand name',{exact:true}).fill(brandName);await admin.getByLabel('Brand slug',{exact:true}).fill('browser-'+suffix);await admin.getByLabel('Owner email',{exact:true}).fill(email);
   const createdResponse=admin.waitForResponse(r=>new URL(r.url()).pathname==='/api/platform/brands'&&r.request().method()==='POST');
   await admin.getByRole('button',{name:'Create brand and invite owner',exact:true}).click();const created=await (await createdResponse).json();
   await admin.getByLabel('Owner invitation link',{exact:true}).waitFor();
   assert.ok((await admin.getByLabel('Owner invitation link',{exact:true}).innerText()).includes('#token='));
   await owner.goto(base+'/accept-invite#token='+created.invitation.token);
   await owner.getByLabel('Invitation code',{exact:true}).waitFor();
   await owner.waitForFunction(()=>(document.querySelector('[aria-label="Invitation code"]')?.value.length || 0)>30);
   await owner.waitForFunction(()=>!window.location.hash);
   assert.ok(!new URL(owner.url()).hash,'Invitation fragment should be removed');
   await owner.getByRole('button',{name:'Check invitation',exact:true}).click();await owner.getByText(email,{exact:true}).waitFor();
   await owner.getByLabel('Owner name',{exact:true}).fill('Browser Owner');await owner.getByLabel('New password',{exact:true}).fill('Browser-Owner-password-123');
   await owner.getByRole('button',{name:'Accept owner invitation',exact:true}).click();await owner.getByText('Owner invitation accepted. Sign in to continue.',{exact:true}).waitFor();
   await owner.getByRole('button',{name:'Go to sign in',exact:true}).click();
   async function signIn() {await owner.locator('input').nth(0).fill(email);await owner.locator('input').nth(1).fill('Browser-Owner-password-123');await owner.getByText('Sign In',{exact:true}).click();await owner.getByText(brandName+' · Main Store',{exact:true}).waitFor();}
   await signIn();let ownerToken=await owner.evaluate(()=>localStorage.getItem('fabclean_session'));
   assert.equal((await owner.request.get(api+'/api/handoffs',{headers:{'X-Session-Token':ownerToken}})).status(),403);
   const featureRow=admin.getByText('Store handoffs',{exact:true}).locator('..');await featureRow.getByRole('button',{name:'Enabled',exact:true}).click();
   await admin.getByRole('button',{name:'Review brand changes',exact:true}).click();await admin.getByRole('button',{name:'Confirm change',exact:true}).click();await admin.getByText('Brand and entitlements updated.',{exact:true}).waitFor();
   assert.equal((await owner.request.get(api+'/api/handoffs',{headers:{'X-Session-Token':ownerToken}})).status(),200);
   await admin.getByRole('button',{name:'Suspend brand',exact:true}).click();await admin.getByLabel('Lifecycle reason',{exact:true}).fill('Cancel lifecycle check');await admin.getByRole('button',{name:'Cancel change',exact:true}).click();
   assert.equal((await owner.request.get(api+'/api/orders',{headers:{'X-Session-Token':ownerToken}})).status(),200);
   await admin.getByRole('button',{name:'Suspend brand',exact:true}).click();await admin.getByLabel('Lifecycle reason',{exact:true}).fill('Browser lifecycle test');await admin.getByRole('button',{name:'Confirm change',exact:true}).click();await admin.getByText('Brand lifecycle updated.',{exact:true}).waitFor();
   assert.equal((await owner.request.get(api+'/api/orders',{headers:{'X-Session-Token':ownerToken}})).status(),401);
   await admin.getByRole('button',{name:'Reactivate brand',exact:true}).click();await admin.getByLabel('Lifecycle reason',{exact:true}).fill('Browser reactivation test');await admin.getByRole('button',{name:'Confirm change',exact:true}).click();await admin.getByRole('button',{name:'Suspend brand',exact:true}).waitFor();
   assert.equal((await owner.request.get(api+'/api/orders',{headers:{'X-Session-Token':ownerToken}})).status(),401);
   await owner.goto(base+'/sign-in');await owner.getByText('Sign In',{exact:true}).waitFor();await signIn();ownerToken=await owner.evaluate(()=>localStorage.getItem('fabclean_session'));
   assert.equal((await owner.request.get(api+'/api/orders',{headers:{'X-Session-Token':ownerToken}})).status(),200);
   await admin.getByRole('button',{name:'Add platform plan',exact:true}).click();await admin.getByLabel('Plan code',{exact:true}).fill('browser-'+suffix);await admin.getByLabel('Plan name',{exact:true}).fill('Browser Plan '+suffix);await admin.getByLabel('Plan store limit',{exact:true}).fill('3');await admin.getByLabel('Plan staff limit',{exact:true}).fill('8');
   await admin.getByRole('switch',{name:'Plan AI assistance',exact:true}).click();await admin.getByRole('button',{name:'Review platform plan',exact:true}).click();await admin.getByRole('button',{name:'Confirm change',exact:true}).click();await admin.getByText('Platform plan saved.',{exact:true}).waitFor();
   await admin.getByRole('button',{name:'Browser Plan '+suffix,exact:true}).click();await admin.getByRole('button',{name:'Review brand changes',exact:true}).click();await admin.getByRole('button',{name:'Confirm change',exact:true}).click();await admin.getByText('Brand and entitlements updated.',{exact:true}).waitFor();
   assert.equal((await owner.request.get(api+'/api/ai/status',{headers:{'X-Session-Token':ownerToken}})).status(),200);
   const deactivated=await admin.request.put(api+'/api/brand/stores/'+created.initial_store.id,{headers:{'X-Session-Token':fixtures.super_token},data:{active:false}});assert.equal(deactivated.status(),200);
   await admin.getByRole('button',{name:'Refresh platform',exact:true}).click();
   await admin.getByRole('button',{name:new RegExp('^'+brandName+' ·')}).click();
   await admin.getByRole('button',{name:'Reactivate store Main Store',exact:true}).click();await admin.getByRole('button',{name:'Confirm change',exact:true}).click();
   await admin.getByText('Main Store · Active',{exact:true}).waitFor();
   assert.equal((await owner.request.get(api+'/api/orders',{headers:{'X-Session-Token':ownerToken}})).status(),200);
   await owner.goto(base+'/platform-admin');await owner.getByText('SuperAdmin access required',{exact:true}).waitFor();assert.equal(await owner.getByText('Platform online',{exact:true}).count(),0);
   assert.deepEqual(errors,[]);await admin.screenshot({path:`/tmp/platform-${mobile?'mobile':'desktop'}.png`,fullPage:true});
   console.log(`${mobile?'mobile web':'desktop'}: real API onboarding, invitation, license override, cancel/suspend/reactivate, relogin, plan assignment, store recovery and permission denial passed`);
   for (const context of contexts) await context.close();
  }
 } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});

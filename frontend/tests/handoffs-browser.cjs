// Exported web UI against a real LOCAL PostgreSQL-backed API. No production calls.
// Prepare fixtures with backend/tests/create_handoff_browser_fixture.py (module).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), http = require('node:http'), path = require('node:path');
const fixtures = JSON.parse(fs.readFileSync(process.env.HANDOFF_TEST_FIXTURES || '/tmp/pr5-browser-fixture.json', 'utf8'));
const api = process.env.HANDOFF_TEST_API || 'http://127.0.0.1:8005';
if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Browser handoff tests require a local disposable API');
const root = path.resolve(__dirname, '../dist');
const server = http.createServer((req,res) => {
  let file = path.join(root, decodeURIComponent(new URL(req.url, 'http://local').pathname));
  if (!file.startsWith(root + '/') && file !== root) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) file += '.html';
  if (!fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  res.setHeader('Content-Type', file.endsWith('.js') ? 'application/javascript' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {}), args: ['--no-sandbox'] });
  let activePage;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    for (const [index, mobile] of [false, true].entries()) {
      const contexts = [], errors = [];
      async function pageFor(actor) {
        const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 }, isMobile: mobile, hasTouch: mobile });
        contexts.push(context); const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.addInitScript(({ id, token, name }) => { localStorage.setItem('fabclean_staff', JSON.stringify({ id, name, role: 'manager' })); localStorage.setItem('fabclean_session', token); }, { id: fixtures.users[actor], token: fixtures.tokens[actor], name: actor });
        await page.route('**/api/**', async route => {
          const request = route.request(), url = new URL(request.url());
          const response = await route.fetch({ url: api + url.pathname + url.search });
          await route.fulfill({ response, headers: { ...response.headers(), 'access-control-allow-origin': '*' } });
        });
        await page.goto(base + '/handoffs');
        await page.getByText(`Browser Test Brand · ${actor === 'source' ? 'Market Street Store' : 'Central Plant'}`, { exact: true }).waitFor();
        await page.getByRole('button', { name: 'Refresh', exact: true }).click({ trial: true });
        return page;
      }
      const source = await pageFor('source'), plant = await pageFor('plant');
      activePage = source;
      const order = fixtures.orders[index * 2];
      await source.getByText('New handoff', { exact: true }).click();
      await source.getByText(order.order_number, { exact: true }).click();
      await source.getByText('Central Plant · central plant', { exact: true }).click();
      await source.getByLabel('Shared handoff notes', { exact: true }).fill('Sealed bag for local browser test');
      await source.getByText('Review dispatch', { exact: true }).click();
      await source.getByText('Back', { exact: true }).click();
      assert.equal(await source.getByText('In transit to destination', { exact: true }).count(), 0);
      await source.getByText('Review dispatch', { exact: true }).click();
      await source.getByText('Confirm handoff', { exact: true }).click();
      await source.getByText('In transit to destination', { exact: true }).waitFor();
      await plant.getByText('Refresh', { exact: true }).click();
      await plant.getByText('Confirm receipt', { exact: true }).click();
      await plant.getByText('Confirm handoff', { exact: true }).click();
      await plant.getByText('At destination', { exact: true }).waitFor();
      assert.equal(await plant.getByText('Private Customer', { exact: true }).count(), 0);
      await plant.getByText('Dispatch return', { exact: true }).last().click();
      await plant.getByText('Confirm handoff', { exact: true }).click();
      await plant.getByText('In transit to origin', { exact: true }).waitFor();
      await source.getByText('Refresh', { exact: true }).click();
      await source.getByText('Confirm return received', { exact: true }).click();
      const completion = source.waitForResponse(response => new URL(response.url()).pathname.endsWith('/actions') && response.request().method() === 'POST');
      await source.getByText('Confirm handoff', { exact: true }).click();
      const completedResponse = await completion;
      assert.equal(completedResponse.status(), 200, 'Return completion must succeed before reload');
      const completed = await completedResponse.json();
      assert.equal(completed.order_id, order.id);
      assert.equal(completed.status, 'completed');
      async function showCompletedOrder() {
        // The global store header appears before this screen finishes loading.
        // Wait for the screen's enabled refresh control before selecting a filter.
        await source.getByRole('button', { name: 'Refresh', exact: true }).click({ trial: true });
        const closedFilter = source.getByRole('button', { name: 'Closed handoffs', exact: true });
        await closedFilter.click();
        const card = source.getByText(`${order.order_number} · Outgoing`, { exact: true }).locator('..');
        await card.getByText('Returned to origin', { exact: true }).waitFor();
      }
      await showCompletedOrder();
      // Hold the reloaded history response until the loading state is visible.
      // This exercises the slower CI timing without sleeps or a larger timeout.
      let releaseHistory;
      const historyGate = new Promise(resolve => { releaseHistory = resolve; });
      const historyRoute = '**/api/handoffs';
      const delayedHistory = async route => {
        await historyGate;
        await route.fallback();
      };
      await source.route(historyRoute, delayedHistory);
      const refreshed = source.waitForResponse(response => new URL(response.url()).pathname === '/api/handoffs' && response.request().method() === 'GET');
      try {
        await source.reload();
        await source.getByText('Browser Test Brand · Market Street Store', { exact: true }).waitFor();
        await source.getByLabel('Loading handoffs', { exact: true }).waitFor();
        assert.equal(await source.getByRole('button', { name: 'Refresh', exact: true }).isDisabled(), true);
      } finally {
        releaseHistory();
      }
      const historyResponse = await refreshed;
      assert.equal(historyResponse.status(), 200);
      const history = await historyResponse.json();
      assert.equal(history.handoffs.find(handoff => handoff.id === completed.id)?.status, 'completed', 'Completed custody must persist in the reloaded API history');
      await showCompletedOrder();
      await source.unroute(historyRoute, delayedHistory);
      assert.deepEqual(errors, []);
      await source.screenshot({ path: process.env.HANDOFF_SCREENSHOT_DIR ? path.join(process.env.HANDOFF_SCREENSHOT_DIR, `handoffs-${mobile ? 'mobile' : 'desktop'}.png`) : `/tmp/handoffs-${mobile ? 'mobile' : 'desktop'}.png`, fullPage: true });
      console.log(`${mobile ? 'mobile web' : 'desktop'}: real API dispatch, confirmation back, receipt, return, completion and refresh passed`);
      for (const context of contexts) await context.close();
    }
  } catch (error) {
    if (activePage && !activePage.isClosed()) {
      await activePage.screenshot({ path: '/tmp/handoffs-failure.png', fullPage: true }).catch(() => {});
      console.error('Handoff screen alerts:', await activePage.getByRole('alert').allTextContents().catch(() => []));
    }
    throw error;
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });

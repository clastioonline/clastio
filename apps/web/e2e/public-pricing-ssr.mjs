import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { launchBrowser } from './browser.mjs';

const cwd = fileURLToPath(new URL('../', import.meta.url));
const port = Number(process.env.SSR_TEST_PORT || 3114);
const base = `http://127.0.0.1:${port}`;
let phase = 'valid';
let serverRequests = 0;
const plans = () => ({ items: [
  { code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0, features: [], limits: { credits: 60, max_lectures: 3 } },
  ...[['teacher', 'Teacher', phase === 'changed' ? 177.25 : 149], ['pro', 'Teacher Pro', 249], ['assistant', 'Genie Assistant', 399]]
    .map(([code, name, price]) => ({ code, name, price_monthly_aed: price, price_annual_aed: price * 10,
      features: ['Editable PowerPoints'], limits: { credits: 800, max_lectures: 10 } })),
], currency: 'AED', vat_rate: .05, online_payments: true, payment_provider: 'stripe',
trial: { enabled: true, plan: 'pro', days: 7, credits: 50 } });

const fixture = createServer((request, response) => {
  if (request.url !== '/api/v1/billing/plans') { response.writeHead(404).end(); return; }
  serverRequests++;
  assert.equal(request.headers.cookie, undefined, 'server pricing forwards no session cookie');
  assert.equal(request.headers.authorization, undefined, 'server pricing sends no auth header');
  response.writeHead(phase === 'unavailable' ? 503 : 200, { 'content-type': 'application/json' });
  response.end(JSON.stringify(phase === 'unavailable' ? { error: { message: 'Unavailable' } } :
    phase === 'malformed' ? { items: 'not a catalogue' } : plans()));
});
await new Promise(resolve => fixture.listen(0, '127.0.0.1', resolve));
const fixtureUrl = `http://127.0.0.1:${fixture.address().port}`;
const web = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '--hostname', '127.0.0.1', '--port', String(port)],
  { cwd, env: { ...process.env, API_URL: fixtureUrl, NEXT_TELEMETRY_DISABLED: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
let output = '';
for (const stream of [web.stdout, web.stderr]) stream.on('data', chunk => { output = (output + chunk).slice(-6000); });
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (web.exitCode !== null) throw new Error('Isolated Next server exited before readiness');
    try { ready = (await fetch(base + '/pricing', { signal: AbortSignal.timeout(2000) })).ok; } catch {}
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  assert.ok(ready, 'isolated Next pricing page started');

  const raw = async () => {
    const response = await fetch(base + '/pricing');
    assert.equal(response.status, 200);
    return response.text();
  };
  let html = await raw();
  assert.match(html, /<h3[^>]*>Teacher<\/h3>/, 'plan cards are HTML, not just an embedded data payload');
  for (const price of [149, 249, 399]) assert.ok(html.includes(`AED ${price}`), `raw HTML has configured AED ${price}`);
  assert.ok(!html.includes('Loading current plans'), 'no browser fetch is needed for the initial price cards');
  phase = 'changed';
  html = await raw();
  assert.ok(html.includes('AED 177.25'), 'request-time catalogue changes preserve price decimals');
  for (const unavailable of ['unavailable', 'malformed']) {
    phase = unavailable;
    html = await raw();
    assert.ok(html.includes("We couldn&#x27;t load current prices") || html.includes("We couldn't load current prices"));
    assert.ok(html.includes('Retry pricing'));
    assert.ok(!/<h3[^>]*>Teacher<\/h3>/.test(html), 'failed catalogue does not invent or reuse plan prices');
  }

  phase = 'valid';
  browser = await launchBrowser();
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const crawler = await noJs.newPage();
  await crawler.goto(base + '/pricing');
  await crawler.getByText('AED 149', { exact: true }).waitFor();
  assert.equal(await crawler.getByRole('heading', { name: 'Teacher', exact: true }).count(), 1);
  await noJs.close();

  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let clientUnavailable = true;
  let clientRequests = 0;
  await page.route('**/api/v1/billing/plans', route => {
    clientRequests++;
    return route.fulfill({ status: clientUnavailable ? 503 : 200,
      json: clientUnavailable ? { error: { message: 'Unavailable' } } : plans() });
  });
  await page.goto(base + '/pricing');
  await page.getByRole('button', { name: 'Retry pricing', exact: true }).waitFor();
  assert.ok(clientRequests > 0, 'SSR fallback still refreshes on hydration');
  assert.equal(await page.getByRole('heading', { name: 'Teacher', exact: true }).count(), 0,
    'a failed client refresh hides stale server prices and plan choices');
  clientUnavailable = false;
  await page.getByRole('button', { name: 'Retry pricing', exact: true }).click();
  await page.getByText('AED 149', { exact: true }).waitFor();
  await page.getByRole('tab', { name: 'Yearly', exact: true }).click();
  await page.getByText('AED 1490 billed yearly · +5% VAT', { exact: true }).waitFor();
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, serverRequests, clientRequests,
    checks: ['raw HTML configured AED plans', 'request-time decimal price change', '503/malformed fallback',
      'JavaScript-disabled prices', 'client refresh failure hides stale cards', 'retry recovery', 'yearly totals'] }));
} catch (error) {
  console.error(error.message);
  // Next startup output contains only this synthetic fixture's endpoints, never request headers or keys.
  console.error(output.replace(/\bsk[-_][A-Za-z0-9_-]+\b/g, '[redacted]'));
  process.exitCode = 1;
} finally {
  await browser?.close();
  web.kill('SIGTERM');
  await new Promise(resolve => fixture.close(resolve));
}

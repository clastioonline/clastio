// Isolated Next + synthetic public API. No requests reach the teacher database.
// Run sequentially with public-pricing-ssr.mjs: both use Next's .next/dev lock.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { launchBrowser } from './browser.mjs';
import { legalDocumentTitles } from '../lib/legal-documents.ts';
import { PUBLIC_POLICY_ALIASES } from '../lib/seo.ts';
import { supportPages } from '../lib/support-pages.ts';

const cwd = fileURLToPath(new URL('../', import.meta.url));
const port = Number(process.env.SUPPORT_SSR_TEST_PORT || 3116);
const base = `http://127.0.0.1:${port}`;
const evidenceDirectory = new URL('../../../artifacts/system-pages-20261012/', import.meta.url);
await mkdir(evidenceDirectory, { recursive: true });
const types = ['terms', 'privacy', 'acceptable_use', 'cookie', 'refund'];
const checks = [], publicRequests = [], clientRequests = [];
let phase = 'published';

function document(type, selected = '2.0') {
  const archived = selected === '1.0';
  const versions = ['2.0', '1.0'].map(version => ({ type, title: legalDocumentTitles[type], version,
    effective_from: version === '2.0' ? '2026-10-12T00:00:00Z' : '2026-09-26T00:00:00Z',
    status: version === '2.0' ? 'published' : 'archived' }));
  return { ...versions.find(version => version.version === selected),
    content: `# Synthetic ${type} policy heading\nSynthetic ${type} body for version ${selected}, visible without JavaScript.\n\n## Source and account information\nThis document is test content, not a policy publication.\n- A synthetic policy item.\n- A second policy item.\n<script>window.unsafeLegalFixture=true</script>`,
    summary_of_changes: archived ? 'Synthetic archived version.' : 'Synthetic published version.', versions };
}

const fixture = createServer((request, response) => {
  const url = new URL(request.url, 'http://fixture.local');
  publicRequests.push({ path: url.pathname, method: request.method, cookieForwarded: !!request.headers.cookie, authorizationForwarded: !!request.headers.authorization });
  let payload, status = 200;
  if (url.pathname === '/api/v1/legal') payload = { items: types.map(type => document(type).versions[0]) };
  else if (url.pathname.startsWith('/api/v1/legal/')) {
    const type = url.pathname.slice('/api/v1/legal/'.length);
    const version = url.searchParams.get('version') || '2.0';
    if (!types.includes(type) || !['1.0', '2.0'].includes(version)) { status = 404; payload = { error: { code: 'not_found', message: 'Synthetic document missing' } }; }
    else if (phase === 'unavailable') { status = 503; payload = { error: { code: 'unavailable', message: 'Synthetic legal service unavailable' } }; }
    else if (phase === 'malformed') payload = { type, title: legalDocumentTitles[type], version: '2.0', status: 'published', content: null, versions: [] };
    else payload = document(type, version);
  } else if (url.pathname === '/api/v1/public/config') payload = { app_name: 'Clastio', support_email: 'Support@clastio.online', ai_live_enabled: false, online_payments: false };
  else if (url.pathname === '/api/v1/status') payload = { ok: true, global: { paused: false }, services: [], maintenance: { enabled: false } };
  else { status = 404; payload = { error: { code: 'fixture_only', message: 'Synthetic API endpoint not provided' } }; }
  response.writeHead(status, { 'content-type': 'application/json' });
  response.end(JSON.stringify(payload));
});
await new Promise(resolve => fixture.listen(0, '127.0.0.1', resolve));
const fixtureUrl = `http://127.0.0.1:${fixture.address().port}`;
const web = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '--hostname', '127.0.0.1', '--port', String(port)],
  { cwd, env: { ...process.env, API_URL: fixtureUrl, NEXT_PUBLIC_SITE_URL: base, NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: '', NEXT_TELEMETRY_DISABLED: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
let output = '', browser;
for (const stream of [web.stdout, web.stderr]) stream.on('data', chunk => { output = (output + chunk).slice(-6000); });
const crawlerHeaders = { 'user-agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)', cookie: 'synthetic_private_session=do-not-forward', authorization: 'Bearer synthetic-public-test-only' };
const raw = async path => {
  const response = await fetch(base + path, { headers: crawlerHeaders, signal: AbortSignal.timeout(30000) });
  return { response, html: await response.text() };
};

try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (web.exitCode !== null) throw new Error('Isolated Next support server exited before readiness');
    try { ready = (await fetch(base + '/contact', { signal: AbortSignal.timeout(2000) })).ok; } catch {}
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  assert.ok(ready, 'isolated Next support server started');
  browser = await launchBrowser();
  const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 }, extraHTTPHeaders: crawlerHeaders });
  const crawler = await noJs.newPage();
  const internalLinks = new Set();
  const collectLinks = async () => {
    for (const href of await crawler.locator('a[href]').evaluateAll(links => links.map(link => link.getAttribute('href')))) {
      if (!href.startsWith('/')) continue;
      assert.ok(!href.startsWith('//'), 'internal links cannot redirect to another authority');
      const url = new URL(href, base);
      assert.equal(url.origin, base);
      internalLinks.add(url.pathname + url.search);
    }
  };
  for (const type of types) {
    const path = `/legal/${type}`;
    const { response, html } = await raw(path);
    assert.equal(response.status, 200, path);
    assert.match(html, new RegExp(`<h2[^>]*>Synthetic ${type} policy heading</h2>`), 'policy body is HTML, not only serialized props');
    assert.match(html, new RegExp(`<p[^>]*>Synthetic ${type} body for version 2.0, visible without JavaScript.</p>`));
    assert.ok(!html.includes('<script>window.unsafeLegalFixture=true</script>'), 'policy text cannot inject executable scripts');
    const browserResponse = await crawler.goto(base + path);
    assert.equal(browserResponse.status(), 200);
    assert.equal(await crawler.getByRole('heading', { name: legalDocumentTitles[type], exact: true, level: 1 }).count(), 1);
    assert.equal(await crawler.getByRole('heading', { name: `Synthetic ${type} policy heading`, exact: true }).count(), 1);
    assert.ok(await crawler.getByText(`Synthetic ${type} body for version 2.0, visible without JavaScript.`, { exact: true }).count());
    assert.equal(await crawler.locator('link[rel="canonical"]').getAttribute('href'), base + path);
    assert.ok(!(await crawler.locator('meta[name="robots"]').getAttribute('content')).includes('noindex'));
    assert.ok(await crawler.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${path} fits mobile`);
    await collectLinks();
  }
  checks.push('five published legal documents render full headings/body in raw HTML and without JavaScript');
  await crawler.goto(base + '/legal/privacy?version=1.0');
  assert.equal(await crawler.locator('link[rel="canonical"]').getAttribute('href'), base + '/legal/privacy');
  assert.match(await crawler.locator('meta[name="robots"]').getAttribute('content'), /noindex/);
  assert.ok(await crawler.getByText(/archived version/).count());
  assert.ok(await crawler.getByText('Synthetic privacy body for version 1.0, visible without JavaScript.', { exact: true }).count());
  checks.push('archived version is noindex, renders its own body and canonicalises to current policy');
  for (const path of ['/legal/missing-type', '/legal/toString', '/legal/privacy?version=9.9', '/legal/privacy?version=bad%2Fversion', '/legal/privacy?version=1.0&version=2.0', '/legal/dmca']) assert.equal((await raw(path)).response.status, 404, path);
  checks.push('missing/invalid version, missing/unpublished type and prototype-shaped type return HTTP404');
  for (const state of ['unavailable', 'malformed']) {
    phase = state;
    const { response, html } = await raw('/legal/terms');
    assert.equal(response.status, 500, `${state} policy is not a 200 soft error for Googlebot`);
    assert.ok(!html.includes('<h2>Synthetic terms policy heading</h2>'));
  }
  phase = 'published';
  checks.push('unavailable/malformed legal API returns HTTP500 to blocking-metadata Googlebot');

  for (const support of supportPages) {
    const { response, html } = await raw(support.path);
    assert.equal(response.status, 200, support.path);
    assert.ok(html.includes('Support@clastio.online'));
    await crawler.goto(base + support.path);
    assert.equal(await crawler.getByRole('heading', { level: 1 }).innerText(), support.title);
    for (const section of support.sections) {
      assert.equal(await crawler.getByRole('heading', { name: section.title, exact: true }).count(), 1);
      assert.ok(await crawler.getByText(section.text, { exact: true }).count());
    }
    for (const href of await crawler.locator('a[href^="mailto:"]').evaluateAll(links => links.map(link => link.getAttribute('href')))) assert.ok(href.startsWith('mailto:Support@clastio.online'));
    await collectLinks();
  }
  await crawler.goto(base + '/contact');
  assert.equal(await crawler.getByRole('heading', { level: 1 }).innerText(), 'Contact Clastio');
  assert.ok(await crawler.getByRole('link', { name: 'Support@clastio.online', exact: true }).count());
  for (const href of await crawler.locator('a[href^="mailto:"]').evaluateAll(links => links.map(link => link.getAttribute('href')))) assert.ok(href.startsWith('mailto:Support@clastio.online'));
  await collectLinks();
  await crawler.screenshot({ path: fileURLToPath(new URL('contact-mobile.png', evidenceDirectory)) });
  await crawler.goto(base + '/legal');
  assert.equal(await crawler.getByRole('heading', { level: 1 }).innerText(), 'Policies and privacy information');
  for (const type of types) assert.ok(await crawler.locator(`a[href="/legal/${type}"]`).count());
  await collectLinks();
  for (const path of internalLinks) {
    const response = await fetch(base + path, { signal: AbortSignal.timeout(30000) });
    assert.equal(response.status, 200, `same-origin help/contact/legal link resolves: ${path}`);
  }
  for (const alias of PUBLIC_POLICY_ALIASES) {
    const response = await fetch(base + alias.source, { redirect: 'manual' });
    assert.ok([301, 308].includes(response.status), 'familiar policy URL redirects permanently');
    assert.equal(new URL(response.headers.get('location'), base).pathname, alias.destination);
    const final = await fetch(base + alias.source);
    assert.equal(final.status, 200);
    assert.equal(new URL(final.url).pathname, alias.destination);
  }
  checks.push(`${supportPages.length} help/support pages, Contact, legal directory, ${internalLinks.size} internal links and all policy aliases resolve`);
  await noJs.close();

  const client = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true, serviceWorkers: 'block' });
  await client.addInitScript(() => localStorage.setItem('clastio:cookie-consent', JSON.stringify({ analytics: false, marketing: false, at: 'synthetic-test' })));
  let exportCalls = 0, authenticated = true;
  const exportPayload = { user: { id: 'synthetic-teacher', email: 'synthetic@example.com' }, classes: [], courses: [], lectures: [], documents: [], assets: [], ai_calls_count: 0 };
  await client.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    clientRequests.push({ path, method: request.method() });
    if (request.method() !== 'GET') return route.fulfill({ status: 500, json: { error: { message: 'Unexpected mutation in read-only fixture' } } });
    if (path === '/api/v1/auth/me') return route.fulfill({ status: authenticated ? 200 : 401,
      json: authenticated ? { user: { ...exportPayload.user, role: 'teacher', name: 'Synthetic teacher', email_verified: true } } : { error: { code: 'unauthenticated', message: 'Sign in' } } });
    if (path === '/api/v1/me/export') { exportCalls++; return route.fulfill({ json: exportPayload }); }
    return route.fulfill({ status: 200, json: {} });
  });
  const page = await client.newPage();
  await page.goto(base + '/contact');
  assert.equal(await page.getByRole('dialog', { name: 'Cookie preferences' }).count(), 0, 'stored decline initially hides the banner');
  await page.getByRole('button', { name: 'Cookie preferences', exact: true }).click();
  const choices = page.getByRole('dialog', { name: 'Cookie preferences' });
  await choices.waitFor();
  assert.equal(await choices.getByRole('checkbox', { name: 'Analytics cookies' }).isChecked(), false);
  await choices.getByRole('button', { name: 'Save choice', exact: true }).click();
  await choices.waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('clastio:cookie-consent')).analytics), false);
  checks.push('footer cookie button reopens a stored essential-only choice and saves optional analytics off');

  await page.goto(base + '/data-export-request?download=1');
  await page.getByRole('button', { name: 'Download account summary', exact: true }).waitFor();
  assert.equal(exportCalls, 0, 'loading the page or passing a query cannot download account data');
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download account summary', exact: true }).click();
  const download = await downloaded;
  assert.equal(download.suggestedFilename(), 'clastio-account-summary.json');
  assert.deepEqual(JSON.parse(await readFile(await download.path(), 'utf8')), exportPayload);
  assert.equal(exportCalls, 1);
  await page.getByText('Your browser received the account summary. Check its downloads list to save the JSON file.', { exact: true }).waitFor();
  await page.screenshot({ path: fileURLToPath(new URL('data-export-mobile.png', evidenceDirectory)) });
  authenticated = false;
  await page.reload();
  await page.getByRole('heading', { name: 'Sign in to request your data', exact: true }).waitFor();
  assert.equal(exportCalls, 1, 'signed-out view cannot request an export');
  assert.equal(await page.getByRole('button', { name: 'Download account summary', exact: true }).count(), 0);
  checks.push('mocked JSON summary downloads only after explicit click; signed-out state offers no export action');
  await client.close();
  assert.ok(publicRequests.length > 0);
  assert.ok(publicRequests.every(request => !request.cookieForwarded && !request.authorizationForwarded), 'server public fetches do not forward visitor session or auth headers');
  assert.ok(publicRequests.every(request => request.method === 'GET'));
  assert.ok(clientRequests.every(request => request.method === 'GET'), 'no actual or mocked mutation was attempted');
  checks.push('synthetic incoming visitor Cookie/Authorization are not forwarded to server public API');
  const evidence = { passed: true, isolatedSyntheticApi: true, realDatabaseRequests: 0, legalTypes: types, supportPages: supportPages.map(page => page.path), checks, publicRequests, clientRequests };
  await writeFile(new URL('public-support-ssr.json', evidenceDirectory), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify({ passed: true, legalDocuments: types.length, supportPages: supportPages.length, internalLinks: internalLinks.size, publicRequests: publicRequests.length, checks }));
} catch (error) {
  await writeFile(new URL('public-support-ssr-failed.json', evidenceDirectory), JSON.stringify({ passed: false, isolatedSyntheticApi: true,
    completedChecks: checks, publicRequests, clientRequests, error: error.message }, null, 2) + '\n');
  console.error(error.message);
  console.error(output.replace(/\bsk[-_][A-Za-z0-9_-]+\b/g, '[redacted]'));
  process.exitCode = 1;
} finally {
  await browser?.close();
  web.kill('SIGTERM');
  await new Promise(resolve => fixture.close(resolve));
}

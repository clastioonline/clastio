// Read-only: verify genuine HTTP error responses and a public-only offline fallback.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';
import { systemPages } from '../lib/system-pages.ts';

const base = process.env.BASE_URL || 'http://localhost:3005';
assertLocalTestBase(base);
const evidenceDirectory = new URL('../../../artifacts/system-pages-20261012/', import.meta.url);
await mkdir(evidenceDirectory, { recursive: true });
const browser = await launchBrowser();
const results = [], writes = [];
try {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  await context.route('**/api/v1/**', route => {
    if (route.request().method() !== 'GET') { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage();
  for (const definition of systemPages) {
    const response = await page.goto(`${base}/${definition.slug}`);
    assert.equal(response.status(), definition.status, definition.slug);
    assert.match(response.headers()['x-robots-tag'], /noindex/);
    assert.equal(response.headers()['x-clastio-system-page'], definition.slug);
    assert.equal(await page.locator('h1').count(), 1);
    assert.equal(await page.locator('h1').innerText(), definition.title);
    assert.equal(await page.getByRole('link', { name: definition.primaryAction.label, exact: true }).getAttribute('href'), definition.primaryAction.href);
    assert.equal(await page.locator('meta[name="robots"]').getAttribute('content'), 'noindex,nofollow');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${definition.slug} fits mobile`);
    const head = await page.request.head(`${base}/${definition.slug}`);
    assert.equal(head.status(), definition.status);
    assert.equal((await head.body()).length, 0, 'HEAD has no body');
    results.push({ path: `/${definition.slug}`, status: response.status(), mobile: true, withoutJavaScript: true, noindex: true });
  }
  for (const path of ['/a-real-missing-url-20261012', '/unknown/deep/path-20261012']) {
    const response = await page.goto(`${base}${path}`);
    assert.equal(response.status(), 404, 'missing URLs must remain HTTP 404');
    assert.equal(await page.locator('h1').innerText(), systemPages.find(page => page.slug === '404').title);
    assert.ok(await page.locator('meta[name="robots"][content*="noindex"]').count());
    results.push({ path, status: 404, branded: true });
  }
  await page.goto(`${base}/404`);
  await page.screenshot({ path: fileURLToPath(new URL('404-mobile.png', evidenceDirectory)) });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.emulateMedia({ colorScheme: 'dark' });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: fileURLToPath(new URL('404-dark-desktop.png', evidenceDirectory)) });
  await context.close();

  const offlineContext = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'allow' });
  await offlineContext.route('**/api/v1/**', route => {
    if (route.request().method() !== 'GET') { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const offlinePage = await offlineContext.newPage();
  await offlinePage.goto(base);
  await offlinePage.evaluate(async () => {
    await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;
  });
  await offlinePage.waitForFunction(() => !!navigator.serviceWorker.controller);
  await offlinePage.waitForFunction(async () => {
    const cache = await caches.open('clastio-public-brand-v2');
    return !!(await cache.match('/offline'));
  });
  const cachedPaths = await offlinePage.evaluate(async () => {
    const cache = await caches.open('clastio-public-brand-v2');
    return (await cache.keys()).map(request => new URL(request.url).pathname).sort();
  });
  assert.deepEqual(cachedPaths, ['/brand/app-icon-512.png', '/brand/favicon.png', '/offline']);
  await offlineContext.setOffline(true);
  const offlineResponse = await offlinePage.goto(`${base}/help`);
  assert.equal(offlineResponse.status(), 503);
  assert.equal(offlineResponse.headers()['x-clastio-system-page'], 'offline');
  assert.equal(await offlinePage.locator('h1').innerText(), 'Reconnect to keep teaching');
  await offlinePage.screenshot({ path: fileURLToPath(new URL('offline-mobile.png', evidenceDirectory)) });
  for (const path of ['/login', '/dashboard', '/api/v1/auth/me', '/lessons/private-never-cached']) {
    await assert.rejects(offlinePage.goto(`${base}${path}`, { timeout: 10000 }), /net::ERR|Network|NS_ERROR/, `private request ${path} cannot use an offline page`);
  }
  await offlineContext.setOffline(false);
  await offlinePage.goto(`${base}/help`);
  assert.equal(await offlinePage.getByRole('heading', { level: 1 }).count(), 1);
  results.push({ publicOfflineFallback: true, offlineStatus: 503, cachedPaths, privatePathsUseNetwork: true, privateResponseCaching: false });
  await offlineContext.close();
  assert.deepEqual(writes, []);
  await writeFile(new URL('generic-pages.json', evidenceDirectory), JSON.stringify({ results, apiWrites: writes.length }, null, 2) + '\n');
  console.log(`${systemPages.length} generic state pages pass actual GET/HEAD status, noindex, mobile and JavaScript-disabled checks; unknown URLs return branded 404; real offline public navigation and private network-only behavior pass. No API writes.`);
} finally { await browser.close(); }

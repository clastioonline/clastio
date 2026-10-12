// Read-only slow-chunk reproduction. No server or teacher data changes.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
assertLocalTestBase(base);
const browser = await launchBrowser();
let release;
const pendingChunk = new Promise(resolve => { release = resolve; });
let heldBannerChunks = 0;
try {
  const context = await browser.newContext({ serviceWorkers: 'block' });
  await context.addInitScript(() => localStorage.setItem('clastio:cookie-consent', JSON.stringify({ analytics: false, marketing: false })));
  await context.route('**/api/v1/**', route => route.request().method() === 'GET' ? route.continue() : route.abort());
  await context.route('**/_next/static/**/*.js', async route => {
    const response = await route.fetch();
    const body = await response.text();
    if (body.includes('clastio:cookie-consent') && body.includes('Analytics cookies')) {
      heldBannerChunks++;
      await pendingChunk;
    }
    await route.fulfill({ response, body });
  });
  const page = await context.newPage();
  await page.goto(base + '/contact', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const button = [...document.querySelectorAll('button')].find(button => button.textContent === 'Cookie preferences');
    return button && Object.keys(button).some(key => key.startsWith('__reactProps$') && typeof button[key]?.onClick === 'function');
  });
  for (let attempt = 0; attempt < 100 && heldBannerChunks === 0; attempt++) await page.waitForTimeout(50);
  assert.equal(heldBannerChunks, 1, 'hold only the actual dynamically imported cookie banner');
  await page.getByRole('button', { name: 'Cookie preferences', exact: true }).click();
  release();
  let opensAfterDelayedMount = true;
  try { await page.getByRole('dialog', { name: 'Cookie preferences' }).waitFor({ timeout: 6000 }); }
  catch { opensAfterDelayedMount = false; }
  let secondClickOpens = false;
  if (!opensAfterDelayedMount) {
    await page.getByRole('button', { name: 'Cookie preferences', exact: true }).click();
    await page.getByRole('dialog', { name: 'Cookie preferences' }).waitFor();
    secondClickOpens = true;
  }
  const result = { heldBannerChunks, footerHydratedBeforeClick: true, opensAfterDelayedMount, secondClickOpens, apiWrites: 0 };
  const directory = new URL('../../../artifacts/system-pages-20261012/', import.meta.url);
  await mkdir(directory, { recursive: true });
  await writeFile(new URL(opensAfterDelayedMount ? 'cookie-race-fixed.json' : 'cookie-race-reproduced.json', directory), JSON.stringify(result, null, 2) + '\n');
  assert.ok(opensAfterDelayedMount, 'The first preferences click must survive delayed CookieBanner mounting');
  console.log(JSON.stringify(result));
  await context.close();
} finally { release?.(); await browser.close(); }

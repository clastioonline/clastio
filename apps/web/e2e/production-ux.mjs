import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';
const base = process.env.BASE_URL || 'http://localhost:3000';
const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const out = path.resolve('e2e/screenshots');
fs.mkdirSync(out, { recursive: true });
try {
  await page.goto(base);
  await page.getByRole('button', { name: 'Essential only' }).click();
  for (const width of [320, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole('heading', { name: 'Before your first lesson' }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `landing fits ${width}px`);
    await page.screenshot({ path: path.join(out, `landing-${width}.png`), fullPage: true });
  }
  await page.getByRole('button', { name: 'Mathematics', exact: true }).click();
  await page.getByRole('heading', { name: 'Different fractions, the same amount' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Mathematics', exact: true }).getAttribute('aria-pressed'), 'true');
  await page.getByText('Do I have to keep this page open?', { exact: true }).click();
  await page.getByText('Only while a file is transferring.', { exact: false }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('navigation', { name: 'Explore Clastio' }).getByRole('link', { name: 'FAQ' }).click();
  assert.equal(new URL(page.url()).hash, '#faq');
  console.log('✓ Landing examples, FAQ, mobile navigation and 320–1920px layouts passed.');

  const signup = await context.request.post(`${base}/api/v1/auth/signup`, { data: {
    email: `ux-${Date.now()}@example.com`, name: 'UX Review', password: 'ux-review-123', accept_terms: true,
  } });
  assert.equal(signup.status(), 200, await signup.text());
  await context.request.post(`${base}/api/v1/me/onboarding/complete`);
  await page.goto(`${base}/templates`);
  await page.getByLabel('Search designs').fill('no-such-design-xyz');
  await page.getByText('No matching designs.', { exact: false }).waitFor();
  await page.getByLabel('Search designs').fill('');
  await page.getByLabel('Filter designs').selectOption('builtin');
  await page.getByRole('heading', { name: 'Built-in styles', exact: true }).waitFor();
  await context.setOffline(true);
  await page.getByRole('status').filter({ hasText: 'You’re offline' }).waitFor();
  await context.setOffline(false);
  await page.getByText('You’re offline.', { exact: false }).waitFor({ state: 'hidden' });
  for (const [api, route, label] of [['projects', 'projects', 'your projects'], ['lessons', 'lessons', 'your lessons'], ['templates', 'templates', 'your designs']]) {
    const pattern = `**/api/v1/${api}*`;
    await page.route(pattern, r => r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { message: 'Test unavailable' } }) }));
    await page.goto(`${base}/${route}`);
    await page.getByRole('alert').filter({ hasText: label }).waitFor();
    await page.unroute(pattern);
    await page.getByRole('button', { name: 'Try again', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: label }).waitFor({ state: 'hidden' });
  }
  assert.deepEqual(errors, []);
  console.log('✓ Template discovery, offline feedback and failed-request recovery passed.');
} catch (error) {
  await page.screenshot({ path: path.join(out, 'production-ux-failure.png'), fullPage: true }).catch(() => {});
  throw error;
} finally { await browser.close(); }

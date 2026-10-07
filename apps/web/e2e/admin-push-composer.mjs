// UI-only test with intercepted API calls: no campaign is sent to real users.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { launchBrowser } from './browser.mjs';
const browser = await launchBrowser();
const base = process.env.BASE_URL || 'http://127.0.0.1:3002';
try {
 const page = await browser.newPage();
 const errors = [], sent = [];
 page.on('pageerror', error => errors.push(error.message));
 await page.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
  let data = { items: [], unread: 0 };
  if (path === '/auth/me') data = { user: { id: 'admin', role: 'admin', admin_role: 'admin', permissions: ['announcements.manage', 'analytics.view'], name: 'Admin', email: 'admin@example.com', email_verified: true, locale: 'en', status: 'active' }, pending_legal: [] };
  if (path === '/admin/push-campaigns/preview') data = { users: 2, devices: 3, audience_users: 10, configured: true };
  if (path === '/admin/push-campaigns' && route.request().method() === 'POST') { sent.push(route.request().postDataJSON()); data = { job_id: 'test-job' }; }
  else if (path === '/admin/push-campaigns') data = { configured: true, items: [] };
  if (path === '/admin/push-campaigns/recipients') data = { items: [{ id: '11111111-1111-4111-8111-111111111111', name: 'Test Teacher', email: 'teacher@example.com' }] };
  await route.fulfill({ json: data });
 });
 fs.mkdirSync('e2e/screenshots', { recursive: true });
 for (const width of [320, 390, 1280]) {
  await page.setViewportSize({ width, height: 844 });
  await page.goto(base + '/admin/announcements');
  await page.getByRole('heading', { name: 'Send push notifications', exact: true }).waitFor();
  const consent = page.getByRole('button', { name: 'Essential only', exact: true });
  if (await consent.isVisible()) await consent.click();
  await page.getByLabel('Template', { exact: true }).selectOption('maintenance');
  await page.getByRole('button', { name: 'Review recipients', exact: true }).click();
  await page.getByRole('button', { name: 'Send to 2 users', exact: true }).waitFor();
  await page.getByLabel('Push title', { exact: true }).fill('Maintenance tomorrow');
  await page.getByRole('button', { name: 'Send to 2 users', exact: true }).waitFor({ state: 'hidden' });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Overflow at ${width}`);
  if (width === 390) await page.screenshot({ path: 'e2e/screenshots/admin-push-mobile.png', fullPage: true });
 }
 await page.getByLabel('Recipients', { exact: true }).selectOption('selected');
 await page.getByRole('checkbox').first().check();
 await page.getByRole('button', { name: 'Review recipients', exact: true }).click();
 await page.getByRole('button', { name: 'Send to 2 users', exact: true }).click();
 await page.getByText('Push campaign queued', { exact: true }).waitFor();
 assert.equal(sent.length, 1);
 assert.equal(sent[0].audience, 'selected');
 assert.equal(sent[0].user_ids.length, 1);
 assert.deepEqual(errors, []);
 console.log('✓ Templates, live preview, audience review, draft invalidation and selected-user sending work at phone and desktop widths (API fixtures only).');
} finally { await browser.close(); }

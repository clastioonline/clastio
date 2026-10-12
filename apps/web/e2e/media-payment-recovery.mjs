// Payment-dependent UI checks. Every API request is mocked; no gateway or teacher database is used.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { launchBrowser } from './browser.mjs';
const base = process.env.BASE_URL || 'http://localhost:3005';
const out = path.resolve(process.env.ARTIFACT_DIR || '../../artifacts/payment-flow-20261012/frontend');
const browser = await launchBrowser();
const evidence = [];
await fs.mkdir(out, { recursive: true });
const user = { id: 'mock-payment-teacher', name: 'Payment Teacher', email: 'payment@example.com', role: 'teacher', permissions: [], status: 'active', email_verified: true, onboarding_completed: true };
const plans = { items: [{ code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0, limits: { credits: 60, max_lectures: 2 }, features: [] }, { code: 'pro', name: 'Pro', price_monthly_aed: 99, price_annual_aed: 999, limits: { credits: 600, max_lectures: 10 }, features: [] }], online_payments: true, payment_provider: 'dodo', vat_rate: 0, trial: { enabled: false, days: 7, plan: 'pro', credits: 50 } };
const media = balance => ({ balance, enabled: true, online_payments: true, pricing: { image: 5, video_per_second: 3 }, styles: ['photorealistic'], video_seconds: [4, 8], packs: [{ code: 'starter', name: 'Starter', credits: 100, price_aed: 20 }], items: [] });
async function scenario(name, check) {
  const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => localStorage.setItem('clastio:cookie-consent', JSON.stringify({ analytics: false, marketing: false })));
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const state = { balance: 0, mediaFailure: false, credits: 55, reserved: 5, jobStatus: 'running', showJob: false, paymentStatuses: [], checkoutUrl: 'javascript:alert(1)' };
  const reads = {}, writes = [], errors = [];
  const billing = () => ({ plan: { code: 'free', name: 'Free' }, subscription: null, pending_checkout: null, trial: null, trial_available: false, usage: Object.fromEntries(['credits','ai_images','whatsapp_messages','storage_mb'].map(key => [key, { used: key === 'credits' ? 5 : 0, limit: 60, available: key === 'credits' ? state.credits : 60, reserved: key === 'credits' ? state.reserved : 0 }])), payments: state.paymentStatuses.map((status, i) => ({ date: '2026-10-12T00:00:00Z', status, currency: 'AED', amount: 20 + i, tax: 0 })) });
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), endpoint = new URL(req.url()).pathname.replace('/api/v1',''), method = req.method();
    if (method === 'GET') reads[endpoint] = (reads[endpoint] || 0) + 1;
    else writes.push({ endpoint, method });
    let data = { items: [], unread: 0, active_count: 0 }, status = 200;
    if (endpoint === '/auth/me') data = { user, pending_legal: [] };
    else if (endpoint === '/billing/plans') data = plans;
    else if (endpoint === '/billing/subscription' || endpoint === '/me/usage') data = billing();
    else if (endpoint === '/media' && method === 'GET') {
      if (state.mediaFailure) { status = 503; data = { error: { code: 'unavailable', message: 'Media balance temporarily unavailable.' } }; }
      else data = media(state.balance);
    } else if (endpoint === '/media/packs/starter/checkout' && method === 'POST') data = { url: state.checkoutUrl };
    else if (endpoint === '/usage/estimates') data = { costs: { course_plan: 2, slide: 1 }, remaining: state.credits, reserved: state.reserved, reset_at: '2026-11-01T00:00:00Z' };
    else if (endpoint === '/me/profile') data = { name: user.name, curriculum: 'british', subjects: ['Science'], grades: ['10'], teaching_languages: ['en'], class_duration_minutes: 45 };
    else if (endpoint === '/memory') data = { preferences: [] };
    else if (endpoint === '/activity' && state.showJob) data = { active_count: ['running','queued'].includes(state.jobStatus) ? 1 : 0, items: [{ id: 'mock-reserved-job', type: 'lesson_generation', label: 'Presentation', title: 'Mock lesson', href: '/projects', status: state.jobStatus, progress: 100, stage: 'Done', error: null, created_at: '2026-10-12T00:00:00Z', completed_at: null }] };
    else if (endpoint === '/billing/referrals') data = { enabled: false, progress: { completed_tasks: 0, next_milestone: 10 } };
    else if (method !== 'GET') { status = 500; data = { error: { code: 'unexpected_mock_write', message: `Unexpected mutation ${endpoint}` } }; }
    await route.fulfill({ status, json: data });
  });
  try {
    await check({ page, state, reads, writes });
    assert.deepEqual(errors, [], name + ': client errors');
    evidence.push({ name, passed: true, writes });
    console.log('✓ ' + name);
  } catch (error) {
    evidence.push({ name, passed: false, error: error.message });
    await page.screenshot({ path: path.join(out, name.replace(/[^a-z0-9]+/gi,'-') + '-failed.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally { await context.close(); }
}
const noReceipt = async page => {
  assert.equal(await page.getByText('Payment received', { exact: true }).count(), 0);
  assert.equal(await page.getByText('Payment successful', { exact: true }).count(), 0);
};
try {
  await scenario('Delayed media balance updates never certify a URL payment', async ({ page, state, reads, writes }) => {
    await page.goto(base + '/media?status=success&payment_id=fake');
    await page.getByText('Checking your media credit balance', { exact: true }).waitFor();
    assert.match(await page.locator('[aria-label="Current media credit balance"]').innerText(), /0\s+media credits/);
    await noReceipt(page); assert.equal(writes.length, 0);
    state.balance = 100;
    await page.waitForFunction(() => document.querySelector('[aria-label="Current media credit balance"]')?.textContent?.includes('100'), undefined, { timeout: 12000 });
    assert.ok(reads['/media'] >= 2, 'return polling reads the delayed server balance');
    await noReceipt(page); assert.equal(writes.length, 0);
    const before = reads['/media'];
    const refreshed = page.waitForResponse(response => response.url().endsWith('/media'));
    await page.getByRole('button', { name: 'Refresh balance', exact: true }).click();
    await refreshed;
    assert.ok(reads['/media'] > before);
  });
  await scenario('Media return polling is bounded and explicit refresh stays available', async ({ page, reads, writes }) => {
    await page.clock.install();
    await page.goto(base + '/media?status=success');
    await page.getByText('Checking your media credit balance', { exact: true }).waitFor();
    await page.clock.fastForward(46000);
    await page.getByText('Review your media credit balance', { exact: true }).waitFor();
    // Drain a poll started just before the checking window closed.
    await page.waitForTimeout(100);
    const before = reads['/media'];
    await page.clock.fastForward(10000);
    await page.waitForTimeout(100);
    assert.equal(reads['/media'], before, 'no continued media polling with no pending jobs after45seconds');
    const refreshed = page.waitForResponse(response => response.url().endsWith('/media'));
    await page.getByRole('button', { name: 'Refresh balance', exact: true }).click();
    await refreshed;
    assert.ok(reads['/media'] > before);
    await noReceipt(page); assert.equal(writes.length, 0);
  });
  await scenario('Media API failure has explicit recovery and safe checkout error', async ({ page, state, writes }) => {
    state.mediaFailure = true;
    await page.goto(base + '/media?status=success');
    await page.getByRole('alert').filter({ hasText: 'your media studio and credit balance' }).waitFor();
    assert.equal(writes.length, 0);
    state.mediaFailure = false;
    await page.getByRole('button', { name: 'Try again', exact: true }).click();
    await page.getByRole('heading', { name: 'Media studio', exact: true }).waitFor();
    await noReceipt(page);
    await page.getByRole('button', { name: 'Buy', exact: true }).click();
    await page.getByText('The checkout destination could not be confirmed. Contact support.', { exact: true }).waitFor();
    assert.deepEqual(writes, [{ endpoint: '/media/packs/starter/checkout', method: 'POST' }]);
    assert.match(page.url(), /\/media\?/);
    state.mediaFailure = true;
    await page.getByRole('button', { name: 'Refresh balance', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'your media studio and credit balance' }).waitFor();
    state.mediaFailure = false;
    await page.getByRole('button', { name: 'Try again', exact: true }).click();
    await page.getByRole('heading', { name: 'Media studio', exact: true }).waitFor();
  });
  await scenario('Failed or cancelled return labels cannot assert a transaction result', async ({ page, writes }) => {
    for (const status of ['failed','cancelled']) {
      await page.goto(base + '/media?status=' + status);
      await page.getByText('Checking your media credit balance', { exact: true }).waitFor();
      await noReceipt(page);
      assert.equal(await page.getByText('Payment failed', { exact: true }).count(), 0);
      assert.equal(writes.length, 0);
    }
  });
  await scenario('Media checkout follows the API destination without granting a balance', async ({ page, state, writes }) => {
    state.checkoutUrl = base + '/media?status=success&pack=starter';
    await page.goto(base + '/media');
    await page.getByRole('heading', { name: 'Media studio', exact: true }).waitFor();
    assert.equal(writes.length, 0);
    await page.getByRole('button', { name: 'Buy', exact: true }).click();
    await page.waitForURL('**/media?status=success&pack=starter');
    await page.getByText('Checking your media credit balance', { exact: true }).waitFor();
    assert.match(await page.locator('[aria-label="Current media credit balance"]').innerText(), /0\s+media credits/);
    await noReceipt(page);
    assert.deepEqual(writes, [{ endpoint: '/media/packs/starter/checkout', method: 'POST' }]);
  });
  await scenario('Billing badges reflect paid failed pending and refunded states', async ({ page, state, writes }) => {
    state.paymentStatuses = ['paid','failed','pending','refunded'];
    await page.goto(base + '/billing');
    await page.getByRole('heading', { name: 'Plan & billing', exact: true }).waitFor();
    for (const [status, cls] of [['paid','bg-success-50'],['failed','bg-danger-50'],['pending','bg-warn-50'],['refunded','bg-surface-2']]) {
      assert.ok((await page.locator('table').getByText(status, { exact: true }).getAttribute('class')).includes(cls), status + ' uses its status tone');
    }
    assert.equal(writes.length, 0);
  });
  for (const terminal of ['succeeded','failed','cancelled']) await scenario('Financial displays refresh after job ' + terminal, async ({ page, state, reads, writes }) => {
    state.showJob = true;
    await page.goto(base + '/projects/new');
    await page.getByRole('heading', { name: 'What chapter are you teaching?', exact: true }).waitFor();
    await page.getByText('55 credits available', { exact: false }).first().waitFor();
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('clastio:limit', { detail: { message: 'Mock plan limit' } })));
    await page.getByRole('dialog', { name: 'Upgrade to keep going', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Upgrade', exact: true }).waitFor();
    const keys = ['/me/usage','/usage/estimates','/billing/subscription'];
    const before = Object.fromEntries(keys.map(key => [key, reads[key] || 0]));
    const finalCredits = terminal === 'succeeded' ? 42 : 60;
    state.credits = finalCredits; state.reserved = 0; state.jobStatus = terminal;
    await page.evaluate(() => window.dispatchEvent(new Event('clastio:work-started')));
    await page.waitForFunction(value => document.body.textContent.includes(value + ' credits available'), finalCredits);
    for (const key of keys) assert.ok(reads[key] > before[key], key + ' refetched on settlement');
    assert.equal(await page.getByText('5 reserved for queued work', { exact: false }).count(), 0);
    const settled = Object.fromEntries(keys.map(key => [key, reads[key]]));
    const checked = page.waitForResponse(response => response.url().endsWith('/activity'));
    await page.evaluate(() => window.dispatchEvent(new Event('clastio:work-started')));
    await checked; await page.waitForTimeout(150);
    for (const key of keys) assert.equal(reads[key], settled[key], key + ' not invalidated repeatedly for same terminal feed');
    assert.equal(writes.length, 0);
  });
  console.log('Payment-dependent frontend: ' + evidence.length + ' mocked scenarios passed.');
} finally {
  await fs.writeFile(path.join(out, 'evidence.json'), JSON.stringify({ base, scenarios: evidence, realAccountMutations: 0, realGatewayRequests: 0 }, null, 2));
  await browser.close();
}

import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

// Exercise the launch journeys without making provider calls or changing real accounts.
const base = process.env.BASE_URL || 'http://localhost:3100';
const browser = await launchBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
let role = 'teacher', permissions = [], completed = true, authFailure = false, billingFailure = false;
let settingsRequests = 0, trialRequests = 0, authRequests = 0, checkoutBody, licenseBody;
const plans = { items: [
  { code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0, limits: { credits: 30, max_lectures: 3 }, features: [] },
  ...[['teacher', 'Teacher', 149], ['pro', 'Teacher Pro', 249], ['assistant', 'Genie Assistant', 399]].map(([code, name, price]) => ({ code, name, price_monthly_aed: price, price_annual_aed: price * 10, limits: { credits: 800, max_lectures: 10 }, features: [] })),
], online_payments: true, vat_rate: 0.05, trial: { enabled: true, plan: 'pro', days: 7, credits: 50 } };
const summary = () => ({ plan: { code: 'free', name: 'Free' }, subscription: null, trial: null, trial_available: true, pending_checkout: null, usage: Object.fromEntries(['credits', 'ai_images', 'whatsapp_messages', 'storage_mb'].map(key => [key, { used: 0, limit: 30 }])), payments: [] });
let billing = summary();
await page.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
  let data = { items: [], unread: 0, total: 0, active_count: 0 };
  if (path === '/auth/me') {
    authRequests++;
    if (authFailure) return route.fulfill({ status: 503, json: { error: { message: 'Temporarily unavailable' } } });
    data = { user: { id: 'launch-review', name: 'Launch Teacher', email: 'teacher@example.com', role, permissions, status: 'active', email_verified: true, onboarding_completed: completed }, pending_legal: [] };
  }
  if (path === '/billing/plans' || path === '/admin/plans') data = plans;
  if (path === '/billing/subscription') {
    if (billingFailure) return route.fulfill({ status: 503, json: { error: { message: 'Billing temporarily unavailable' } } });
    data = billing;
  }
  if (path === '/me/usage') data = billing;
  if (path === '/billing/referrals') data = { enabled: false, progress: { completed_tasks: 0, next_milestone: 10 } };
  if (path === '/auth/trial') {
    trialRequests++;
    billing = { ...summary(), plan: { code: 'pro', name: 'Teacher Pro' }, subscription: { provider: 'trial', status: 'trialing', current_period_end: '2099-01-01' }, trial: { active: true, days_left: 7, ends_at: '2099-01-01' } };
  }
  if (path === '/billing/checkout') { checkoutBody = route.request().postDataJSON(); data = { url: `${base}/billing?preview=1` }; }
  if (path === '/billing/licenses/redeem') licenseBody = route.request().postDataJSON();
  if (path === '/admin/settings') { settingsRequests++; return route.fulfill({ status: 403, json: { error: { message: 'Settings permission required' } } }); }
  if (path === '/admin/licenses') data = { items: [
    { id: 'expired', key_suffix: 'ABCD1234', plan_code: 'teacher', months: 1, expires_at: '2020-01-01', redeemed_at: null, revoked: false },
    { id: 'available', key_suffix: 'EFGH5678', plan_code: 'pro', months: 3, expires_at: '2099-01-01', redeemed_at: null, revoked: false },
  ] };
  await route.fulfill({ status: 200, json: data });
});
try {
  await page.goto(`${base}/pricing`);
  await page.getByRole('button', { name: 'Essential only' }).click();
  assert.equal(authRequests, 0, 'public pricing and cookie consent do not request authentication');

  billingFailure = true;
  billing.usage.credits = { used: 0, limit: 60, available: 80, reserved: 12 };
  await page.goto(`${base}/billing`);
  await page.getByRole('alert').filter({ hasText: 'your plan and billing' }).waitFor();
  billingFailure = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await page.getByText('80 available · 12 reserved for queued work', { exact: true }).waitFor();
  await page.getByText('80 credits available', { exact: false }).waitFor();
  await page.getByRole('button', { name: 'Start 7-day free trial' }).click();
  await page.getByText('Teacher Pro free trial', { exact: true }).waitFor();
  assert.equal(trialRequests, 1, 'Free teachers can explicitly start a trial after onboarding');

  billing = summary();
  await page.goto(`${base}/billing#license`);
  await page.reload(); // Changing only the hash retains the previous trial's cached entitlement.
  await page.getByLabel('License key', { exact: true }).fill('CLASTIO-TEST-LICENSE');
  await page.getByRole('button', { name: 'Redeem license', exact: true }).click();
  await page.waitForFunction(() => document.readyState === 'complete');
  assert.deepEqual(licenseBody, { key: 'CLASTIO-TEST-LICENSE' });
  await page.getByLabel('Have a coupon code?').fill('SCHOOL20');
  await page.getByRole('button', { name: 'Upgrade', exact: true }).first().click();
  await page.waitForURL('**/billing?preview=1');
  assert.deepEqual(checkoutBody, { plan: 'teacher', interval: 'month', coupon_code: 'SCHOOL20' });

  billing = { ...summary(), subscription: { provider: 'stripe', status: 'unpaid', current_period_end: '2099-01-01', interval: 'month' } };
  await page.goto(`${base}/billing?status=success`);
  await page.getByRole('button', { name: 'Manage subscription', exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Upgrade', exact: true }).count(), 0, 'unresolved online subscription cannot create another checkout');
  assert.equal(await page.getByRole('button', { name: 'Start 7-day free trial' }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Redeem license', exact: true }).count(), 0);
  assert.equal(await page.getByText("You're on Free. Thank you!", { exact: true }).count(), 0, 'return URL cannot claim payment success');

  billing = { ...summary(), trial_available: false, pending_checkout: { id: 'checkout-1', provider: 'dodo', status: 'open', plan: 'teacher', interval: 'month', url: 'https://checkout.example.com/session-existing', expires_at: '2099-01-01' } };
  await page.goto(`${base}/billing`);
  await page.getByRole('link', { name: 'Resume checkout', exact: true }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'Resume checkout', exact: true }).getAttribute('href'), 'https://checkout.example.com/session-existing');
  assert.equal(await page.getByRole('button', { name: 'Upgrade', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Start 7-day free trial' }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Redeem license', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Close unpaid checkout', exact: true }).count(), 0, 'Dodo checkout is not locally released without provider confirmation');

  authFailure = true;
  await page.goto(`${base}/billing`);
  await page.getByRole('alert').filter({ hasText: 'your account' }).waitFor();
  assert.equal(new URL(page.url()).pathname, '/billing', 'server failures do not log the teacher out');
  authFailure = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await page.getByRole('heading', { name: 'Plan & billing' }).waitFor();

  role = 'admin'; permissions = ['billing.view'];
  await page.goto(`${base}/onboarding`);
  await page.waitForURL('**/admin/billing');
  await page.getByRole('heading', { name: 'Subscriptions & payments', exact: true }).waitFor();
  await page.goto(`${base}/admin`);
  await page.waitForURL('**/admin/billing');
  await page.goto(`${base}/admin/plans`);
  await page.getByText('…ABCD1234', { exact: false }).waitFor();
  assert.equal(settingsRequests, 0, 'read-only billing staff do not request restricted settings');
  assert.equal(await page.getByRole('button', { name: 'Create license', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Revoke', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Save plan', exact: true }).count(), 0);
  await page.getByText('Expired', { exact: false }).waitFor();

  role = 'teacher'; permissions = []; completed = false; billing = summary();
  await page.goto(`${base}/onboarding`);
  await page.getByRole('button', { name: 'Open activity', exact: true }).click();
  await page.getByRole('dialog', { name: 'Your activity' }).waitFor();
  await page.getByRole('button', { name: 'Keep exploring', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Skip for now', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `onboarding classes fit ${width}px`);
  }
  await page.getByRole('button', { name: 'Finish setup', exact: true }).click();
  await page.getByRole('heading', { name: 'Choose your plan', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Continue on Free', exact: true }).click();
  await page.getByRole('heading', { name: 'Clastio is ready', exact: true }).waitFor();
  assert.equal(trialRequests, 1, 'finishing onboarding on Free does not start a trial');
  assert.deepEqual(errors, []);
  console.log('Launch journeys passed: public consent, onboarding/activity, explicit trial, coupon checkout, license redemption, payment recovery, account/billing retry and read-only staff permissions.');
} finally { await browser.close(); }

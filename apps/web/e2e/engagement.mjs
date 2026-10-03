// Mocked browser checks: no real accounts or payments.
import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
const browser = await chromium.launch({executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const limits = {credits: 50, ai_images: 5, whatsapp_messages: 20, storage_mb: 100, max_lectures: 5};
const plan = {code: 'pro', name: 'Pro', price_monthly_aed: 49, price_annual_aed: 490, limits, features: ['Your own design']};
let submitted;
await page.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
  let data = {items: [], unread: 0, total: 0};
  if (path === '/auth/me') data = {user: {id: 'review', email: 'teacher@example.com', name: 'Test Teacher', role: 'teacher', permissions: [], status: 'active', email_verified: true, locale: 'en', timezone: 'Asia/Kolkata', onboarding_completed: true}, pending_legal: []};
  if (path === '/billing/plans') data = {items: [plan], online_payments: true, trial: {enabled: true, days: 7, credits: 50, plan: 'pro'}};
  if (path === '/billing/subscription' || path === '/me/usage') data = {plan, trial: {active: true, days_left: 7, ends_at: '2026-10-10T00:00:00Z'}, subscription: {provider: 'trial'}, usage: Object.fromEntries(Object.keys(limits).map(k => [k, {used: k === 'credits' ? 10 : 0, limit: limits[k]}])), payments: []};
  if (path === '/billing/referrals') data = {enabled: true, url: 'https://clastio.online/signup?ref=abcd1234', reward_media_credits: 25, invited: 3, qualified: 1, earned_media_credits: 25, progress: {completed_tasks: 4, next_milestone: 5}};
  if (path === '/billing/checkout') {
    submitted = route.request().postDataJSON();
    return route.fulfill({status: 422, json: {error: {code: 'invalid_coupon', message: 'This coupon code is invalid or expired.'}}});
  }
  await route.fulfill({status: 200, json: data});
});
try {
  await page.goto(`${process.env.BASE_URL || 'http://localhost:3100'}/billing`);
  await page.getByText('Your trial allowance', {exact: true}).waitFor();
  await page.getByText('3 joined · 1 qualified · 25 media credits earned', {exact: true}).waitFor();
  await page.getByText('1 more to your next milestone of 5.', {exact: true}).waitFor();
  await page.getByLabel('Have a coupon code?').fill('SAVE20');
  await page.getByRole('button', {name: 'Keep this plan', exact: true}).click();
  await page.getByText('This coupon code is invalid or expired.', {exact: true}).waitFor();
  assert.deepEqual(submitted, {plan: 'pro', interval: 'month', coupon_code: 'SAVE20'});
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 900});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `billing fits ${width}px`);
  }
  assert.deepEqual(errors, []);
  console.log('Trial, referral/progress, coupon submission/error, mobile/desktop checks passed.');
} finally { await browser.close(); }

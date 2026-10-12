// Exercise local return recovery using mocked auth/billing only; never create a payment.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
assertLocalTestBase(base);
const browser = await launchBrowser();
const evidence = [];
try {
  for (const destination of ['/billing?status=success&session_id=synthetic-checkout', '/media?status=success&payment_id=synthetic-payment']) {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    await context.addInitScript(() => localStorage.setItem('clastio:cookie-consent', JSON.stringify({ analytics: false, marketing: false })));
    let signedIn = false;
    const writes = [], errors = [];
    const user = { id: 'synthetic-return-teacher', email: 'return@example.com', name: 'Return Teacher', role: 'teacher', status: 'active', permissions: [], email_verified: true, onboarding_completed: true };
    const quotas = Object.fromEntries(['credits', 'ai_images', 'whatsapp_messages', 'storage_mb'].map(key => [key, { used: 0, reserved: 0, available: 60, limit: 60 }]));
    const billing = { plan: { code: 'free', name: 'Free' }, subscription: null, pending_checkout: null, trial: null, trial_available: false, payments: [], usage: quotas };
    await context.route('**/api/v1/**', async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace('/api/v1', '');
      let status = 200, json = { items: [], unread: 0, active_count: 0 };
      if (request.method() !== 'GET') {
        writes.push(path);
        if (path === '/auth/login') { signedIn = true; json = { user }; }
        else { status = 500; json = { error: { message: 'Unexpected fixture mutation' } }; }
      } else if (path === '/auth/me') {
        status = signedIn ? 200 : 401;
        json = signedIn ? { user, pending_legal: [] } : { error: { code: 'unauthenticated', message: 'Sign in' } };
      } else if (path === '/me/usage' || path === '/billing/subscription') json = billing;
      else if (path === '/auth/oauth/providers') json = { providers: [] };
      else if (path === '/memory') json = { preferences: [], items: [] };
      else if (path === '/billing/referrals') json = { enabled: false, progress: { completed_tasks: 0, next_milestone: 10 } };
      else if (path === '/usage/estimates') json = { costs: { slide: 1, course_plan: 2 }, remaining: 60 };
      else if (path === '/media') json = { balance: 0, enabled: false, online_payments: false, pricing: { image: 5, video_per_second: 3 }, styles: ['illustration'], video_seconds: [4], packs: [], items: [] };
      else if (path === '/billing/plans') json = { items: [{ code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0, limits: { credits: 60, max_lectures: 3 }, features: [] }], online_payments: false, payment_provider: null, currency: 'AED', vat_rate: .05, trial: { enabled: false, days: 7, plan: 'pro', credits: 50 } };
      await route.fulfill({ status, json });
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + destination);
    await page.waitForURL(url => url.pathname === '/session-expired');
    assert.equal(new URL(page.url()).searchParams.get('next'), destination);
    const login = page.getByRole('link', { name: 'Sign in', exact: true });
    await login.waitFor();
    assert.equal(new URL(await login.getAttribute('href'), base).searchParams.get('next'), destination);
    await login.click();
    await page.getByLabel('Email', { exact: true }).fill(user.email);
    await page.getByLabel(/^Password/).fill('synthetic-password-123');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForURL(url => url.pathname + url.search === destination);
    await page.getByRole('heading', { name: destination.startsWith('/billing') ? 'Plan & billing' : 'Media studio', exact: true }).waitFor();
    assert.equal(await page.getByText('Payment received', { exact: true }).count(), 0);
    assert.deepEqual(writes, ['/auth/login']);
    assert.deepEqual(errors, []);
    evidence.push({ destination, sessionReturnPreserved: true, loginReturnPreserved: true, realGatewayRequests: 0, mockedWrites: writes });
    await context.close();
  }
  const out = new URL('../../../artifacts/payment-flow-20261012/', import.meta.url);
  await mkdir(out, { recursive: true });
  await writeFile(new URL('auth-return.json', out), JSON.stringify({ passed: true, realAccountMutations: 0, evidence }, null, 2) + '\n');
  console.log('Both subscription and media return queries survive session recovery and mocked password sign-in; no payment is inferred or created.');
} finally { await browser.close(); }

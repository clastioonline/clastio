// Account and payment recovery states. Every API request is intercepted; no teacher DB is touched.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { launchBrowser } from './browser.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
const out = path.resolve(process.env.ARTIFACT_DIR || '../../artifacts/system-pages-20261012/account');
const teacher = { id: 'mock-state-teacher', email: 'state.teacher@example.com', name: 'State Teacher', role: 'teacher', permissions: [], status: 'active', email_verified: true, onboarding_completed: true, locale: 'en', timezone: 'Asia/Dubai' };
const free = () => ({ plan: { code: 'free', name: 'Free' }, subscription: null, pending_checkout: null, trial: null, usage: { credits: { used: 0, limit: 60, available: 60, reserved: 0 }, ai_images: { used: 0, limit: 0, available: 0 }, whatsapp_messages: { used: 0, limit: 0, available: 0 }, storage_mb: { used: 0, limit: 100 } }, payments: [] });
const paid = () => ({ ...free(), plan: { code: 'pro', name: 'Pro' }, subscription: { status: 'active', provider: 'stripe', interval: 'month', cancel_at_period_end: false, current_period_end: '2026-11-12T00:00:00Z' } });
const browser = await launchBrowser();
const evidence = [];
let current;
await fs.mkdir(out, { recursive: true });

async function scenario(name, options, check) {
  current = name;
  const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 390, height: 844 } });
  await context.addInitScript(() => localStorage.setItem('clastio:cookie-consent', JSON.stringify({ essential: true, analytics: false, marketing: false })));
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const state = { user: { ...teacher }, billing: free(), authStatus: 200, marketing: true, notificationItems: [{ category: 'lesson_ready', label: 'Lesson ready', mandatory: false, in_app: true, email: true, push: false }, { category: 'security', label: 'Security', mandatory: true, in_app: true, email: true, push: false }], ...options };
  const writes = [];
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname.replace('/api/v1', '');
    const method = request.method();
    const mutation = method !== 'GET' && method !== 'HEAD';
    let body;
    try { body = mutation ? request.postDataJSON() : undefined; } catch {}
    if (mutation) writes.push({ endpoint, method, body, idempotency: request.headers()['idempotency-key'] });
    let data = { items: [], unread: 0 };
    let status = 200;
    if (endpoint === '/auth/me') {
      status = state.authStatus;
      data = status === 200 ? { user: state.user, pending_legal: [] } : { error: { code: status === 401 ? 'session_expired' : 'forbidden', message: status === 401 ? 'Sign in to continue.' : 'This account is not available. Contact support.' } };
    } else if (endpoint === '/billing/subscription' || endpoint === '/me/usage') data = state.billing;
    else if (endpoint === '/billing/plans') data = { items: [{ code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0, limits: { credits: 60, max_lectures: 2 }, features: [] }, { code: 'pro', name: 'Pro', price_monthly_aed: 99, price_annual_aed: 999, limits: { credits: 600, max_lectures: 10 }, features: ['Presentation generation'] }], trial: { enabled: false, days: 7 }, vat_rate: 0, online_payments: true };
    else if (endpoint === '/billing/cancel' && method === 'POST') { state.billing.subscription.cancel_at_period_end = true; data = { status: 'active', cancel_at_period_end: true }; }
    else if (endpoint === '/billing/portal' && method === 'POST') data = { url: 'javascript:alert(1)' };
    else if (endpoint === '/billing/checkout' && method === 'POST') data = { url: 'javascript:alert(1)' };
    else if (endpoint === '/me/delete' && method === 'POST') { state.authStatus = 401; data = { deleted: true, status: 'pending_deletion', purge_on: '2026-11-11T00:00:00Z' }; }
    else if (endpoint === '/auth/resend-verification' && method === 'POST') data = { ok: true };
    else if (endpoint === '/auth/verify-email' && method === 'POST') { status = state.verifyStatus || 200; data = status === 200 ? { ok: true, email: teacher.email } : { error: { code: 'link_expired', message: 'That verification link has expired.' } }; }
    else if (endpoint === '/auth/login' && method === 'POST') { status = 403; data = { error: { code: 'account_suspended', message: 'This account is suspended. Contact support.' } }; }
    else if (endpoint === '/me/consents') {
      if (method === 'PUT') state.marketing = body.marketing_email;
      data = { consents: {}, marketing: { marketing_email: state.marketing, marketing_whatsapp: false } };
    } else if (endpoint === '/me/notification-preferences') {
      if (method === 'PUT') {
        for (const [category, prefs] of Object.entries(body.categories || {})) state.notificationItems = state.notificationItems.map(item => item.category === category ? { ...item, ...prefs } : item);
      }
      data = { items: state.notificationItems };
    } else if (mutation) { status = 500; data = { error: { code: 'unexpected_mock_write', message: `Unexpected mocked mutation: ${method} ${endpoint}` } }; }
    await route.fulfill({ status, json: data });
  });
  const visit = async (slug, heading) => {
    const response = await page.goto(base + slug);
    assert.equal(response.status(), 200, `${name}: route ${slug} must render`);
    await page.getByRole('heading', { name: heading, exact: true, level: 1 }).waitFor();
    // A Suspense fallback can share the final page heading; wait for checked content as well.
    await page.waitForFunction(expected => document.querySelector('.sys-card h1')?.textContent === expected
      && !document.querySelector('.sys-description')?.textContent?.startsWith('Loading the current account status'), heading);
    const robots = await page.locator('meta[name="robots"]').getAttribute('content');
    assert.match(robots, /noindex/);
    assert.match(robots, /nofollow/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name}: mobile page must fit viewport`);
  };
  try {
    await check({ page, state, writes, visit });
    assert.deepEqual(pageErrors, [], `${name}: client errors`);
    evidence.push({ name, passed: true, writes: writes.map(({ endpoint, method }) => ({ endpoint, method })) });
    console.log(`✓ ${name}`);
  } catch (error) {
    await page.screenshot({ path: path.join(out, name.replace(/[^a-z0-9]+/gi, '-') + '-failed.png'), fullPage: true }).catch(() => {});
    evidence.push({ name, passed: false, error: error.message });
    throw error;
  } finally { await context.close(); }
}

try {
  await scenario('Session recovery preserves safe return and cannot imply deletion', { authStatus: 401 }, async ({ page, writes, visit }) => {
    await visit('/session-expired?next=%2Fprojects%2Fnew', 'Sign in to continue');
    assert.equal(await page.getByRole('link', { name: 'Sign in', exact: true }).getAttribute('href'), '/login?next=%2Fprojects%2Fnew');
    await visit('/session-expired?next=https%3A%2F%2Fevil.example', 'Sign in to continue');
    assert.equal(await page.getByRole('link', { name: 'Sign in', exact: true }).getAttribute('href'), '/login?next=%2Fdashboard');
    await visit('/account-deleted?status=deleted&success=true', 'Account closure status');
    assert.match(await page.locator('.sys-description').innerText(), /cannot confirm an account deletion/);
    assert.equal(writes.length, 0);
  });
  await scenario('Account restrictions use actual service status', { authStatus: 403 }, async ({ page, writes, visit }) => {
    await visit('/account-suspended?status=active', 'Account access is unavailable');
    await visit('/account-deactivated?status=deleted', 'Account access is unavailable');
    assert.equal(writes.length, 0);
  });
  await scenario('Active accounts override restrictive URL labels', {}, async ({ writes, visit }) => {
    await visit('/account-suspended', 'Your account is active');
    await visit('/account-deactivated', 'Your account is active');
    await visit('/account-deleted', 'Your account is active');
    assert.equal(writes.length, 0);
  });
  await scenario('Verification requires server state and explicit resend', { user: { ...teacher, email_verified: false } }, async ({ page, writes, visit }) => {
    await visit('/verification-success?verified=true', 'Verify your email');
    assert.equal(writes.length, 0);
    await page.getByRole('button', { name: 'Resend verification email' }).click();
    await page.getByText('A verification email was requested. Check your inbox and spam folder.', { exact: true }).waitFor();
    assert.deepEqual(writes.map(item => item.endpoint), ['/auth/resend-verification']);
    await visit('/verification-failed?success=1', 'Verify your email');
    await visit('/link-expired?purpose=reset', 'Get a fresh account link');
    assert.equal(await page.getByRole('link', { name: 'Request a reset email', exact: true }).getAttribute('href'), '/forgot-password');
    assert.equal(writes.length, 1);
  });
  await scenario('Verified account status is confirmed by auth', {}, async ({ page, writes, visit }) => {
    await visit('/verification-success', 'Your email is verified');
    assert.equal(await page.getByRole('link', { name: 'Continue to the app', exact: true }).evaluate(element => getComputedStyle(element).color), 'rgb(255, 255, 255)', 'Primary Button links keep readable white text in the shared shell');
    assert.equal(writes.length, 0);
  });
  await scenario('Payment URL cannot grant a paid plan or claim failed payment', {}, async ({ page, writes, visit }) => {
    await visit('/payment-success?status=paid&plan=pro&session_id=fake', 'Checking payment confirmation');
    assert.equal(await page.getByText('Free', { exact: true }).count(), 1);
    await visit('/payment-failed?status=failed', 'Review your payment status');
    await visit('/subscription-expired?expired=true', 'Current plan: Free');
    await visit('/trial-expired?ended=true', 'Check your trial status');
    assert.equal(writes.length, 0);
  });
  await scenario('Pending checkout is resumed only from billing response', { billing: { ...free(), pending_checkout: { id: 'pending', status: 'open', provider: 'stripe', url: 'https://checkout.example.com/mock' } } }, async ({ page, writes, visit }) => {
    await visit('/checkout?url=https%3A%2F%2Fevil.example', 'Resume your checkout');
    assert.equal(await page.getByRole('link', { name: 'Resume checkout', exact: true }).getAttribute('href'), 'https://checkout.example.com/mock');
    await visit('/payment-success?status=paid', 'Checking payment confirmation');
    assert.equal(writes.length, 0);
  });
  await scenario('Fresh checkout uses explicit current-plan choice and rejects unsafe redirect', {}, async ({ page, writes, visit }) => {
    await visit('/checkout?plan=pro&checkout=true', 'Choose a plan');
    await page.getByRole('heading', { name: 'Pro', exact: true }).waitFor();
    assert.equal(writes.length, 0);
    await page.getByRole('button', { name: 'Upgrade', exact: true }).click();
    await page.getByText('The checkout destination could not be confirmed. Contact support.', { exact: true }).waitFor();
    assert.deepEqual(writes.map(({ endpoint, method, body }) => ({ endpoint, method, body })), [{ endpoint: '/billing/checkout', method: 'POST', body: { plan: 'pro', interval: 'month' } }]);
    assert.match(page.url(), /\/checkout/);
  });
  await scenario('Confirmed paid access and failed portal destination', { billing: paid() }, async ({ page, writes, visit }) => {
    await visit('/payment-success', 'Your subscription is active');
    await visit('/payment-failed', 'Your current subscription is active');
    await visit('/billing-portal?url=javascript:alert(1)', 'Manage payment settings');
    assert.equal(writes.length, 0);
    await page.getByRole('button', { name: 'Open secure billing portal', exact: true }).click();
    await page.getByText('The billing portal destination could not be confirmed. Contact support.', { exact: true }).waitFor();
    assert.deepEqual(writes.map(item => item.endpoint), ['/billing/portal']);
    assert.match(page.url(), /billing-portal/);
  });
  await scenario('Payment issue and ended trial are server-confirmed', { billing: { ...paid(), subscription: { ...paid().subscription, status: 'past_due' } } }, async ({ state, writes, visit }) => {
    await visit('/payment-failed', 'A payment needs attention');
    state.billing = { ...free(), trial: { active: false, ended: true } };
    await visit('/trial-expired', 'Your trial has ended');
    assert.equal(writes.length, 0);
  });
  await scenario('Cancellation requires explicit acknowledgement and API confirmation', { billing: paid() }, async ({ page, writes, visit }) => {
    await visit('/subscription-cancelled?cancelled=true', 'Review cancellation status');
    assert.equal(writes.length, 0);
    const button = page.getByRole('button', { name: 'Request cancellation', exact: true });
    assert.equal(await button.isDisabled(), true);
    await page.getByRole('checkbox', { name: 'I want to cancel renewal at the end of the current billing period.' }).check();
    await button.click();
    await page.getByRole('heading', { name: 'Cancellation is scheduled', exact: true, level: 1 }).waitFor();
    assert.deepEqual(writes.map(item => item.endpoint), ['/billing/cancel']);
    assert.ok(writes[0].idempotency);
  });
  await scenario('Available credits respect reservations and grants', { billing: { ...free(), usage: { credits: { used: 55, limit: 60, available: 0, reserved: 5 } } } }, async ({ page, state, writes, visit }) => {
    await visit('/usage-limit?resource=credits', 'Allowance is reserved for queued work');
    assert.match(await page.locator('.sys-content').innerText(), /5 reserved for queued work/);
    state.billing = { ...free(), usage: { credits: { used: 0, limit: 0, available: 25, reserved: 0 } } };
    await visit('/upgrade-required?resource=unexpected', 'Your allowance is available');
    assert.match(await page.locator('.sys-description').innerText(), /25 available/);
    assert.equal(writes.length, 0);
  });
  await scenario('Deletion is an explicit request and never a URL-confirmed completion', {}, async ({ page, writes, visit }) => {
    await visit('/delete-account?confirm=true&email=state.teacher@example.com', 'Request account deletion');
    const submit = page.getByRole('button', { name: 'Submit deletion request', exact: true });
    assert.equal(writes.length, 0);
    assert.equal(await submit.isDisabled(), true);
    await page.getByRole('textbox', { name: 'Confirm your account email', exact: true }).fill(teacher.email);
    assert.equal(await submit.isDisabled(), true);
    await page.getByRole('checkbox', { name: 'I understand this closes access now and requests scheduled deletion.' }).check();
    await submit.click();
    await page.getByRole('heading', { name: 'Deletion request accepted', exact: true, level: 1 }).waitFor();
    assert.equal(await page.getByRole('link', { name: 'Contact support about this request', exact: true }).evaluate(element => element.getBoundingClientRect().width <= element.parentElement.getBoundingClientRect().width + 1), true, 'Long mobile action fits its container');
    assert.match(await page.locator('.sys-description').innerText(), /does not mean that final deletion has already completed/);
    assert.deepEqual(writes.map(({ endpoint, method, body }) => ({ endpoint, method, body })), [{ endpoint: '/me/delete', method: 'POST', body: { confirm_email: teacher.email } }]);
    assert.ok(writes[0].idempotency);
    await visit('/account-deleted?status=deleted', 'Account closure status');
    assert.match(await page.locator('.sys-description').innerText(), /cannot confirm/);
    assert.equal(writes.length, 1);
  });
  await scenario('Staff cannot enter teacher deletion or billing flows', { user: { ...teacher, role: 'admin', permissions: ['analytics.view'] } }, async ({ page, writes, visit }) => {
    await visit('/delete-account', 'Staff accounts are managed by an administrator');
    assert.equal(await page.getByRole('button', { name: 'Submit deletion request' }).count(), 0);
    await visit('/checkout', 'Staff billing access');
    assert.equal(writes.length, 0);
  });
  await scenario('Email opt-out and notification preferences change only explicitly', {}, async ({ page, writes, visit }) => {
    await visit('/email-unsubscribe?unsubscribe=true', 'Manage email marketing');
    assert.equal(writes.length, 0);
    await page.getByRole('button', { name: 'Unsubscribe from marketing email', exact: true }).click();
    await page.getByRole('heading', { name: 'Email marketing is off', exact: true, level: 1 }).waitFor();
    assert.deepEqual(writes.map(({ endpoint, method, body }) => ({ endpoint, method, body })), [{ endpoint: '/me/consents', method: 'PUT', body: { marketing_email: false } }]);
    await visit('/notification-preferences', 'Notification preferences');
    const mandatory = page.getByRole('checkbox', { name: 'Security: email', exact: true });
    assert.equal(await mandatory.isDisabled(), true);
    const savedPreference = page.waitForResponse(response => response.url().endsWith('/me/notification-preferences') && response.request().method() === 'PUT');
    // The controlled setting changes after the save response, rather than optimistically on click.
    await page.getByRole('checkbox', { name: 'Lesson ready: email', exact: true }).click();
    await savedPreference;
    await page.waitForFunction(() => document.querySelector('input[aria-label="Lesson ready: email"]')?.checked === false);
    assert.deepEqual(writes.at(-1).body, { categories: { lesson_ready: { email: false } } });
    assert.equal(writes.length, 2);
    await page.screenshot({ path: path.join(out, 'notification-preferences-mobile.png'), fullPage: true });
  });
  await scenario('Existing verification and sign-in failures lead to recovery pages', { verifyStatus: 400 }, async ({ page, writes }) => {
    await page.goto(base + '/verify-email?token=mock-expired-verification');
    await page.getByText('That verification link has expired.', { exact: false }).waitFor();
    assert.equal(await page.getByRole('link', { name: 'Check verification and get help', exact: true }).getAttribute('href'), '/verification-failed');
    assert.deepEqual(writes.map(item => item.endpoint), ['/auth/verify-email']);
    await page.goto(base + '/reset-password');
    await page.getByRole('link', { name: 'Request a reset email', exact: true }).waitFor();
    assert.equal(writes.length, 1);
    await page.goto(base + '/auth/magic');
    await page.getByRole('link', { name: 'Get help with this link', exact: true }).waitFor();
    assert.equal(writes.length, 1);
    await page.goto(base + '/login?legacy=1');
    await page.getByRole('heading', { name: 'Welcome back', exact: true }).waitFor();
    await page.getByRole('textbox', { name: 'Email', exact: true }).fill(teacher.email);
    await page.locator('input[type=password]').fill('only-a-mocked-password');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByRole('link', { name: 'Review account access and recovery', exact: true }).waitFor();
    assert.equal(await page.getByRole('link', { name: 'Review account access and recovery', exact: true }).getAttribute('href'), '/account-suspended');
    assert.deepEqual(writes.map(item => item.endpoint), ['/auth/verify-email', '/auth/login']);
  });
  console.log(`Account system pages: ${evidence.length} mocked scenarios passed; no real API mutations.`);
} catch (error) {
  console.error(`Account state scenario failed: ${current}`);
  throw error;
} finally {
  await fs.writeFile(path.join(out, 'evidence.json'), JSON.stringify({ base, scenarios: evidence }, null, 2));
  await browser.close();
}

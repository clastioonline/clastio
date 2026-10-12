// Onboarding teaching choices and accessibility; mocked APIs avoid account/database writes.
import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
const browser = await launchBrowser();
try {
  const page = await browser.newPage();
  const requests = [];
  const errors = [];
  let completed = false;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');
    const method = request.method();
    let body;
    if (method !== 'GET') { try { body = request.postDataJSON(); } catch {} requests.push({ path, method, body }); }
    let data = { items: [], unread: 0 };
    if (path === '/auth/me') data = { user: { id: 'scope-teacher', name: 'Scope Teacher', email: 'scope@example.com', role: 'teacher', permissions: [], status: 'active', email_verified: true, onboarding_completed: completed }, pending_legal: [] };
    else if (path === '/billing/plans') data = { items: [], trial: { enabled: false, days: 7 } };
    else if (path === '/billing/subscription') data = { plan: { code: 'free' }, subscription: null };
    else if (path === '/me/profile') data = body;
    else if (path === '/me/onboarding/complete') { completed = true; data = { ok: true }; }
    else if (path === '/classes') data = { id: 'class-10', ...body };
    await route.fulfill({ json: data });
  });
  await page.goto(base + '/onboarding');
  await page.getByRole('heading', { name: /Welcome to Clastio/ }).waitFor();
  const consent = page.getByRole('button', { name: 'Essential only', exact: true });
  if (await consent.isVisible()) await consent.click();
  const science = page.getByRole('button', { name: 'Science', exact: true });
  const physics = page.getByRole('button', { name: 'Physics', exact: true });
  assert.equal(await science.getAttribute('aria-label'), 'Science');
  assert.equal(await science.getAttribute('aria-pressed'), 'true');
  await science.click();
  assert.equal(await science.getAttribute('aria-pressed'), 'false');
  assert.equal(await page.getByRole('button', { name: 'Continue', exact: true }).isDisabled(), true);
  await physics.click();
  assert.equal(await physics.getAttribute('aria-pressed'), 'true');
  await page.getByRole('button', { name: 'Grade 8', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'Continue', exact: true }).isDisabled(), true);
  await page.getByRole('button', { name: 'Grade 10', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Skip for now', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('heading', { name: 'Add your classes', exact: true }).waitFor();
  assert.equal(await page.getByLabel('Class', { exact: true }).inputValue(), '');
  assert.deepEqual(await page.getByRole('combobox', { name: 'Grade', exact: true }).locator('option').evaluateAll(options => options.map(option => option.value)), ['10']);
  assert.deepEqual(await page.getByRole('combobox', { name: 'Subject', exact: true }).locator('option').evaluateAll(options => options.map(option => option.value)), ['Physics']);
  await page.getByLabel('Class', { exact: true }).fill('10A');
  await page.getByRole('button', { name: 'Finish setup', exact: true }).click();
  await page.getByRole('heading', { name: 'Choose your plan', exact: true }).waitFor();
  assert.deepEqual(requests.find(item => item.path === '/classes').body, { name: '10A', grade: '10', subject: 'Physics', curriculum: 'british' });
  assert.deepEqual(errors, []);
  console.log('✓ Onboarding chips have clear accessible names and selection state; chosen subjects/grades populate classes without stale defaults.');
} finally { await browser.close(); }

import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';
const base = process.env.BASE_URL || 'http://localhost:3000';
assertLocalTestBase(base);
const browser = await launchBrowser();
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  const login = await context.request.post(`${base}/api/v1/auth/login`, {
    data: { email: 'admin@example.com', password: 'admin-demo-123' },
  });
  assert.equal(login.status(), 200, await login.text());
  const ledger = await context.request.get(`${base}/api/v1/admin/ai-budget`);
  assert.equal(ledger.status(), 200, await ledger.text());
  assert.equal((await ledger.json()).policy.live_enabled, false);
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${base}/admin/ai-costs`);
    await page.getByRole('button', { name: 'Save spending controls' }).waitFor();
    await page.getByText('Settled this month', { exact: true }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  }
  const teacher = await browser.newContext();
  const signup = await teacher.request.post(`${base}/api/v1/auth/signup`, { data: {
    email: `budget-${Date.now()}@example.com`, name: 'Budget Review', password: 'budget-review-123', accept_terms: true,
  } });
  assert.equal(signup.status(), 200, await signup.text());
  const usage = await teacher.request.get(`${base}/api/v1/me/usage`).then(response => response.json());
  assert.equal(usage.plan.code, 'free');
  assert.equal(usage.trial?.active || false, false);
  await teacher.request.post(`${base}/api/v1/me/onboarding/complete`);
  const estimatesResponse = await teacher.request.get(`${base}/api/v1/usage/estimates`);
  assert.equal(estimatesResponse.status(), 200);
  const estimates = await estimatesResponse.json();
  const teacherPage = await teacher.newPage();
  teacherPage.on('pageerror', error => errors.push(error.message));
  await teacherPage.setViewportSize({ width: 390, height: 844 });
  await teacherPage.goto(`${base}/projects/new`);
  const cookies = teacherPage.getByRole('button', { name: 'Essential only', exact: true });
  if (await cookies.count()) await cookies.click();
  await teacherPage.getByLabel('Number of lessons').selectOption('2');
  await teacherPage.getByLabel('Slides per lesson').selectOption('10');
  await teacherPage.getByText(`About ${estimates.costs.course_plan + 20 * estimates.costs.slide} credits`, { exact: false }).waitFor();
  await teacherPage.getByRole('switch', { name: /^Build all chapter parts after planning/ }).click();
  await teacherPage.getByText(`About ${estimates.costs.course_plan} credits`, { exact: false }).waitFor();
  assert.ok(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await teacher.close();
  assert.deepEqual(errors, []);
  console.log('✓ Budget dashboard fits phone/tablet/desktop; live AI stays paused; teacher estimate follows generation options.');
} finally { await browser.close(); }

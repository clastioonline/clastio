import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
assertLocalTestBase(base);
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
let profile = { name: 'Sara', email: 'test@example.com', school_name: '', curriculum: 'british', timezone: 'Asia/Dubai',
  subjects: ['Physics'], grades: ['10'], working_days: [0, 1, 2, 3, 4], class_duration_minutes: 45,
  teaching_languages: ['en'], metadata_policy: {}, planning_preferences: {} };
let saved;
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let value = { items: [] };
    if (path.endsWith('/auth/me')) value = { user: { id: 'test', name: 'Sara', email: 'test@example.com',
      role: 'teacher', permissions: [], onboarding_completed: true, email_verified: true }, pending_legal: [] };
    if (path.endsWith('/me/usage')) value = { plan: { code: 'free', name: 'Free' },
      usage: { credits: { limit: 10, used: 0, reserved: 0, remaining: 10 } }, trial: { active: false } };
    if (path.endsWith('/me/consents')) value = { consents: {}, marketing: { marketing_email: false, marketing_whatsapp: false } };
    if (path.endsWith('/me/profile')) {
      if (route.request().method() === 'PUT') { saved = route.request().postDataJSON(); profile = saved; }
      value = profile;
    }
    await route.fulfill({ json: value });
  });
  await page.goto(`${base}/settings`);
  const nameToggle = page.getByRole('switch', { name: /^Show my name at the bottom right/ });
  const numberToggle = page.getByRole('switch', { name: /^Show PPT page numbers/ });
  await nameToggle.waitFor();
  assert.equal(await nameToggle.getAttribute('aria-checked'), 'false');
  assert.equal(await numberToggle.getAttribute('aria-checked'), 'false');
  const consent = page.getByRole('button', { name: 'Essential only', exact: true });
  if (await consent.count()) await consent.click();
  await nameToggle.click();
  await page.getByText('Teacher name on slides', { exact: true }).locator('..').locator('input').fill('Ms Sara · Physics');
  await numberToggle.click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.getByText('Settings saved', { exact: true }).waitFor();
  assert.equal(saved.metadata_policy.teacher_footer_enabled, true);
  assert.equal(saved.metadata_policy.teacher_footer_text, 'Ms Sara · Physics');
  assert.equal(saved.metadata_policy.page_numbers_enabled, true);
  assert.deepEqual(errors, []);
  console.log('Teacher footer and page numbers start off and save independently with custom text.');
} finally { await browser.close(); }

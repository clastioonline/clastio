import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase, verifyTestTeacher } from './fixtures.mjs';

const base = process.env.BASE_URL || 'http://localhost:3000';
assertLocalTestBase(base);
const browser = await launchBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const out = path.resolve('e2e/screenshots');
fs.mkdirSync(out, { recursive: true });
const checkWidth = async (label) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  assert.ok(overflow <= 1, `${label}: ${overflow}px horizontal overflow`);
};
try {
  const signup = await context.request.post(`${base}/api/v1/auth/signup`, { data: {
    email: `templates-${Date.now()}@example.com`, name: 'Design Review', password: 'template-test-123', accept_terms: true,
  } });
  assert.equal(signup.status(), 200, await signup.text());
  await verifyTestTeacher(browser, context, base);
  await context.request.post(`${base}/api/v1/me/onboarding/complete`);
  await page.goto(`${base}/templates`);
  await page.getByRole('button', { name: 'Essential only' }).click();
  await page.getByRole('heading', { name: 'Your templates' }).waitFor();
  await page.locator('input[type=file]').setInputFiles(path.resolve('../../samples/science_ms_sara.pptx'));
  await page.waitForURL(/\/templates\/[0-9a-f-]+$/, { timeout: 180000 });
  const detailUrl = page.url();
  const id = detailUrl.split('/').at(-1);
  await page.getByLabel('Template name').fill('Responsive teaching design');
  const saved = page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(`/templates/${id}`));
  await page.getByRole('button', { name: 'Save & refresh previews' }).click();
  const response = await saved;
  assert.equal(response.status(), 200, await response.text());
  const job = (await response.json()).job_id;
  assert.ok(job);
  await page.goto(`${base}/activity`);
  let finished = false;
  for (let i = 0; i < 120; i++) {
    const result = await context.request.get(`${base}/api/v1/jobs/${job}`).then(r => r.json());
    assert.notEqual(result.status, 'failed', result.error);
    if (result.status === 'succeeded') { finished = true; break; }
    await page.waitForTimeout(1000);
  }
  assert.ok(finished, 'preview job completed');
  await page.goto(detailUrl);
  await page.getByRole('heading', { name: 'Responsive teaching design', exact: true }).waitFor();
  await page.getByLabel('Title size (pt)').fill('5');
  assert.ok(await page.getByRole('button', { name: 'Save & refresh previews' }).isDisabled());
  await page.reload();
  for (const width of [320, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, name] of [[`${base}/templates`, 'list'], [detailUrl, 'detail']]) {
      await page.goto(route);
      await page.getByRole('heading', { name: name === 'list' ? 'My designs' : 'Responsive teaching design', exact: true }).waitFor();
      await checkWidth(`templates ${name} at ${width}`);
      const broken = await page.locator('main img').evaluateAll(imgs => imgs.filter(i => i.complete && !i.naturalWidth).length);
      assert.equal(broken, 0, 'no broken preview images');
      await page.screenshot({ path: path.join(out, `templates-${name}-${width}.png`), fullPage: true });
    }
  }
  for (const width of [320, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['/dashboard', '/lessons', '/projects', '/assistant', '/activity', '/settings', '/calendar', '/media', '/projects/new', '/curriculum', '/teacher-memory', '/whatsapp', '/billing', '/notifications', '/support', '/tutorials']) {
      await page.goto(base + route);
      await page.locator('main h1').first().waitFor();
      await page.waitForTimeout(250);
      await checkWidth(`${route} at ${width}`);
    }
  }
  await page.goto(`${base}/templates/00000000-0000-0000-0000-000000000000`);
  await page.getByText('This design could not be loaded.', { exact: false }).waitFor();
  await page.goto(detailUrl);
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: 'Delete template' }).click();
  await page.waitForURL(`${base}/templates`);
  assert.deepEqual(errors, []);
  console.log('✓ Template upload, background editing, validation, deletion and missing-design feedback passed.');
  console.log('✓ Templates fit 320–1920px; main teacher pages fit phone, tablet and small desktop widths.');
} catch (e) {
  await page.screenshot({ path: path.join(out, 'templates-failure.png'), fullPage: true }).catch(() => {});
  throw e;
} finally { await browser.close(); }

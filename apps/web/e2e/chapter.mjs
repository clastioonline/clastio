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
page.on('pageerror', error => errors.push(error.message));
const out = path.resolve('e2e/screenshots/chapter-review');
fs.mkdirSync(out, { recursive: true });
async function waitJob(id) {
  for (let attempt = 0; attempt < 90; attempt++) {
    const result = await context.request.get(`${base}/api/v1/jobs/${id}`).then(response => response.json());
    assert.notEqual(result.status, 'failed', result.error);
    if (result.status === 'succeeded') return result;
    await page.waitForTimeout(1000);
  }
  throw new Error('Job did not finish');
}
try {
  const signup = await context.request.post(`${base}/api/v1/auth/signup`, { data: {
    email: `chapter-review-${Date.now()}@example.com`, name: 'Chapter Review', password: 'chapter-review-123', accept_terms: true,
  } });
  assert.equal(signup.status(), 200, await signup.text());
  await verifyTestTeacher(browser, context, base);
  await context.request.post(`${base}/api/v1/me/onboarding/complete`);
  await page.goto(`${base}/projects/new`);
  const cookieButton = page.getByRole('button', { name: 'Essential only' });
  if (await cookieButton.count()) await cookieButton.click();
  await page.getByRole('heading', { name: 'What chapter are you teaching?' }).waitFor();
  await page.getByLabel('Chapter / topic', { exact: true }).fill('Trigonometry');
  await page.getByLabel('Grade', { exact: true }).selectOption('8');
  await page.getByLabel('Subject', { exact: true }).selectOption({ label: 'Mathematics' });
  await page.getByLabel('Number of lessons').selectOption('2');
  await page.getByLabel('Slides per lesson').selectOption('6');
  await page.getByLabel('How would you like to prepare this chapter?').selectOption('daily');
  await page.getByLabel('What have you already taught? (optional)').fill('Right triangles and side names');
  await page.getByLabel('What needs revision? (optional)').fill('Opposite and adjacent');
  await page.getByLabel('Choose books and notes').setInputFiles({ name: 'chapter-notes.txt', mimeType: 'text/plain',
    buffer: Buffer.from('Trigonometry chapter notes. Sine = opposite / hypotenuse. Cosine = adjacent / hypotenuse. Tangent = opposite / adjacent. Begin by labelling triangle sides.') });
  await page.getByText(/Ready ·/).waitFor({ timeout: 60000 });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `chapter form fits ${width}px`);
    await page.screenshot({ path: path.join(out, `chapter-form-${width}.png`), fullPage: true });
  }
  const created = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/courses'));
  await page.getByRole('button', { name: 'Plan chapter & build first lesson' }).click();
  const createdResponse = await created;
  assert.equal(createdResponse.status(), 200, await createdResponse.text());
  const result = await createdResponse.json();
  assert.equal(result.course.options.source_file_ids.length, 1);
  assert.equal(result.course.options.chapter_mode, 'daily');
  await waitJob(result.job_id);
  let project;
  for (let attempt = 0; attempt < 90; attempt++) {
    project = await context.request.get(`${base}/api/v1/projects/${result.course.project_id}`).then(response => response.json());
    assert.notEqual(project.lessons[0]?.status, 'failed', project.lessons[0]?.error);
    if (project.lessons[0]?.has_pptx) break;
    await page.waitForTimeout(1000);
  }
  assert.ok(project.lessons[0].has_pptx);
  assert.equal(project.lessons[1].has_pptx, false);
  await page.goto(`${base}/projects/${result.course.project_id}`);
  await page.getByRole('button', { name: 'Prepare next day' }).click();
  await page.getByLabel('What did you teach in the previous class?').fill('We practised sine');
  await page.getByLabel('What should be revised again?').fill('Side labels');
  await page.screenshot({ path: path.join(out, 'next-day-preparation.png'), fullPage: true });
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.goto(`${base}/lessons/${project.lessons[0].id}`);
  await page.getByText('Edit slide manually', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await page.getByLabel('Title', { exact: true }).fill('Teacher edited chapter slide');
  await page.getByLabel('Layout', { exact: true }).selectOption('table');
  await page.getByLabel('Row 1 column 1').fill('Sine');
  await page.getByLabel('Row 1 column 2').fill('Opposite / hypotenuse');
  const saved = page.waitForResponse(response => response.request().method() === 'PATCH' && /\/slides\/2$/.test(response.url()));
  await page.getByRole('button', { name: 'Save & rebuild', exact: true }).click();
  const savedResponse = await saved;
  assert.equal(savedResponse.status(), 200, await savedResponse.text());
  await waitJob((await savedResponse.json()).job_id);
  await page.reload();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await page.getByLabel('Title', { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Title', { exact: true }).inputValue(), 'Teacher edited chapter slide');
  assert.equal(await page.getByLabel('Row 1 column 2').inputValue(), 'Opposite / hypotenuse');
  assert.ok(await page.getByRole('link', { name: 'Download editable PPT' }).getAttribute('href'));
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `manual editor fits ${width}px`);
    await page.screenshot({ path: path.join(out, `manual-editor-${width}.png`), fullPage: true });
  }
  assert.deepEqual(errors, []);
  console.log('Passed: source upload and selection, daily chapter preparation, next-day instructions, manual table editing, persisted PPT download and responsive layouts.');
} catch (error) {
  await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {});
  throw error;
} finally { await browser.close(); }

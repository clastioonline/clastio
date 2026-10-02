// Verify durable work: submit, leave, reload, close the browser context, and recover results.
// Optional BACKGROUND_WORKER_CONTAINER pauses a local test worker for deterministic queue assertions.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';

const base = process.env.BASE_URL || 'http://localhost:3000';
const worker = process.env.BACKGROUND_WORKER_CONTAINER;
const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const out = path.resolve('e2e/screenshots');
fs.mkdirSync(out, { recursive: true });
let context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const watch = (page) => page.on('pageerror', (e) => errors.push(e.message));
let page = await context.newPage();
watch(page);
try {
  const signup = await context.request.post(`${base}/api/v1/auth/signup`, { data: {
    email: `background-${Date.now()}@example.com`, name: 'Background Teacher', password: 'background-test-123', accept_terms: true,
  } });
  assert.equal(signup.status(), 200, await signup.text());
  await context.request.post(`${base}/api/v1/me/onboarding/complete`);
  if (worker) execFileSync('docker', ['stop', worker], { stdio: 'pipe' });
  await page.goto(`${base}/lessons?tab=documents`);
  await page.getByRole('button', { name: 'Essential only' }).click();
  await page.getByRole('button', { name: 'New worksheet or quiz' }).click();
  const dialog = page.getByRole('dialog', { name: 'Create an assessment' });
  await dialog.getByRole('button', { name: 'A topic', exact: true }).click();
  await dialog.getByPlaceholder('e.g. Equivalent fractions, Grade 5').fill('Equivalent fractions, Grade 5');
  const documentResponse = page.waitForResponse((r) => r.url().endsWith('/api/v1/documents') && r.request().method() === 'POST');
  const started = Date.now();
  await dialog.getByRole('button', { name: 'Create', exact: true }).click();
  const response = await documentResponse;
  assert.equal(response.status(), 200, await response.text());
  const document = await response.json();
  assert.ok(Date.now() - started < 10000, 'submission returns promptly');
  if (worker) assert.equal(document.document.status, 'queued');
  await dialog.getByRole('button', { name: /Continue in background|Done/ }).click();
  await page.goto(`${base}/assistant`);
  await page.getByPlaceholder(/Ask anything/).fill('What did I teach last week?');
  const assistantResponse = page.waitForResponse((r) => r.url().endsWith('/api/v1/assistant/tasks') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  const replyResponse = await assistantResponse;
  assert.equal(replyResponse.status(), 202, await replyResponse.text());
  const reply = await replyResponse.json();
  await page.goto(`${base}/activity`);
  await page.getByRole('heading', { name: 'Activity', exact: true }).waitFor();
  await page.reload();
  await page.locator('main article').first().waitFor();
  let feed = await context.request.get(`${base}/api/v1/activity`).then((r) => r.json());
  assert.ok(feed.items.some((j) => j.id === document.job_id));
  assert.ok(feed.items.some((j) => j.id === reply.job_id));
  if (worker) assert.equal(feed.active_count, 2);
  await page.screenshot({ path: path.join(out, 'background-queued.png'), fullPage: true });
  console.log('✓ Submissions returned promptly; tasks survived navigation and reload.');

  const storageState = await context.storageState();
  await context.close();
  if (worker) execFileSync('docker', ['start', worker], { stdio: 'pipe' });
  context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  watch(page);
  await page.goto(`${base}/activity`);
  await page.getByRole('tab', { name: 'Ready', exact: true }).click();
  await page.getByRole('link', { name: 'Open result', exact: true }).nth(1).waitFor({ timeout: 180000 });
  feed = await context.request.get(`${base}/api/v1/activity`).then((r) => r.json());
  assert.equal(feed.items.find((j) => j.id === document.job_id).status, 'succeeded');
  assert.equal(feed.items.find((j) => j.id === reply.job_id).status, 'succeeded');
  await page.screenshot({ path: path.join(out, 'background-ready.png'), fullPage: true });
  await page.goto(`${base}/assistant?conversation=${reply.conversation_id}`);
  await page.getByText(/covered recently|you prepared these lessons|couldn.t find any lessons/).first().waitFor();
  await page.goto(`${base}/lessons?tab=documents&document=${document.document.id}`);
  await page.getByRole('link', { name: 'Student PDF', exact: true }).waitFor();
  const notices = await context.request.get(`${base}/api/v1/me/notifications`).then((r) => r.json());
  assert.ok(notices.items.some((n) => n.link === `/assistant?conversation=${reply.conversation_id}`));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/activity`);
  await page.getByRole('heading', { name: 'Activity', exact: true }).waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  assert.ok(overflow <= 1, `mobile activity overflow: ${overflow}`);
  await page.getByRole('button', { name: /^Open activity/ }).first().click();
  await page.getByRole('dialog', { name: 'Your activity' }).waitFor();
  await page.screenshot({ path: path.join(out, 'background-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('✓ Results and notifications survived closing the browser context; mobile activity works.');
} catch (error) {
  await page.screenshot({ path: path.join(out, 'background-failure.png'), fullPage: true }).catch(() => {});
  throw error;
} finally {
  if (worker) execFileSync('docker', ['start', worker], { stdio: 'pipe' });
  await browser.close();
}

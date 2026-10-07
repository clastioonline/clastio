// Browser layout checks with deterministic API fixtures; no database writes or paid calls.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { launchBrowser } from './browser.mjs';
const base = process.env.BASE_URL || 'http://127.0.0.1:3002';
const user = { id: 'mobile-teacher', name: 'Mobile Teacher', email: 'mobile@example.com', role: 'teacher', permissions: [], status: 'active', email_verified: true, locale: 'en', timezone: 'Asia/Kolkata', onboarding_completed: true };
const spec = { number: 1, layout: 'concept', purpose: 'Explain', title: 'Understanding fractions', bullets: [{ text: 'A fraction represents part of a whole.', level: 0 }], steps: [], columns: [], terms: [], visual: { kind: 'none', fit: 'contain' }, timing_minutes: 3, speaker_notes: '', manual_objects: {}, sources: [] };
const lesson = { lesson: { id: 'mobile-lesson', number: 1, title: 'Understanding fractions', status: 'generated', version: 1, qc: {}, review_approved: true }, course: { project_id: 'project', topic: 'Fractions', grade: '4' }, slides: [1, 2, 3].map(number => ({ id: `slide-${number}`, number, version: 1, spec: { ...spec, number }, qc: { editable_objects: [{ id: '2', name: 'Title', text: spec.title, x: .1, y: .1, width: .8, height: .2, aspect_ratio: 16/9 }] } })), documents: [], downloads: {}, reflections: [] };
const browser = await launchBrowser();
fs.mkdirSync('e2e/screenshots', { recursive: true });
try {
 const page = await browser.newPage();
 const errors = [];
 page.on('pageerror', error => errors.push(error.message));
 await page.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
  let data = { items: [], unread: 0 };
  if (path === '/auth/me') data = { user, pending_legal: [] };
  if (path === '/me/usage') data = { plan: { code: 'pro', name: 'Pro' }, usage: { credits: { used: 0, limit: 100, reserved: 0, remaining: 100 } } };
  if (path === '/lessons/mobile-lesson') data = lesson;
  if (path === '/me/dashboard') data = { kpis: { total: 3, ready: 3, taught: 0, building: 0, pending: 0 }, checklist: {}, week: [], next_class: null, upcoming: [], classes: [], coverage: { total: 0 } };
  if (path === '/planner/day') data = { classes: [], duration_factor: 1 };
  if (path === '/memory') data = { preferences: [] };
  if (path === '/usage/estimates') data = { costs: { slide: 1 } };
  await route.fulfill({ json: data });
 });
 for (const width of [320, 390, 768, 1280]) {
  await page.setViewportSize({ width, height: 844 });
  for (const path of ['/dashboard', '/projects', '/assistant', '/lessons/mobile-lesson']) {
   await page.goto(base + path);
   await page.getByRole('navigation', { name: 'Mobile navigation' }).waitFor({ state: width < 1024 ? 'visible' : 'hidden' });
   if (path.includes('/lessons/')) await page.getByText('Design canvas', { exact: true }).waitFor();
   else if (path === '/dashboard') await page.getByRole('heading', { name: "Today's classes", exact: true }).waitFor();
   else if (path === '/projects') await page.getByRole('heading', { name: 'Lessons & PPTs', exact: true }).waitFor();
   else await page.getByRole('textbox').last().waitFor();
   const consent = page.getByRole('button', { name: 'Essential only', exact: true });
   if (await consent.isVisible()) await consent.click();
   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
   if (overflow > 1) console.log(await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(el => ({ tag: el.tagName, cls: el.className, text: el.textContent.slice(0, 70) }))));
   assert.ok(overflow <= 1, `${path} at ${width}px overflows by ${overflow}px`);
   if (path === '/dashboard' && width < 1024) {
    const today = await page.getByRole('heading', { name: "Today's classes", exact: true }).boundingBox();
    const analytics = await page.getByText('Lessons prepared', { exact: true }).boundingBox();
    assert.ok(today.y < analytics.y, 'Classroom tasks precede statistics on phones');
   }
   if (path.includes('/lessons/')) {
    const canvas = await page.getByText('Design canvas', { exact: true }).boundingBox();
    const strip = await page.getByRole('button', { name: /Select Title/ }).boundingBox();
    assert.ok(canvas && strip, 'Editor objects are reachable');
    await page.getByRole('button', { name: 'Insert text box', exact: true }).click();
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
   }
   if (width === 390 && path === '/projects') {
    await page.getByRole('button', { name: 'Open menu', exact: true }).click();
    await page.getByRole('dialog', { name: 'Navigation menu' }).waitFor();
    assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden');
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', { name: 'Navigation menu' }).waitFor({ state: 'hidden' });
   }
   if (width === 390) await page.screenshot({ path: `e2e/screenshots/mobile-${path.includes('/lessons/') ? 'editor' : path.slice(1)}.png`, fullPage: true });
  }
 }
 assert.deepEqual(errors, []);
 console.log('✓ Dashboard, projects, assistant, and editor fit 320, 390, 768 and 1280px; mobile navigation and canvas actions work.');
} finally { await browser.close(); }

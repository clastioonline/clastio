// Source catalogue browsing, filtering and reading do not call AI or import files.
import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

const base = process.env.BASE_URL || 'http://localhost:3005';
const user = { id: 'teacher', name: 'Teacher', email: 'teacher@example.com', role: 'teacher', permissions: [],
  status: 'active', email_verified: true, locale: 'en', timezone: 'Asia/Dubai', onboarding_completed: true };
const collection = { id: 'moe-minhaji', title: 'UAE MoE textbooks — Minhaji', curriculum: 'moe',
  publisher: 'UAE Ministry of Education', source_url: 'https://minhaji.moe.gov.ae/', access: 'school_login',
  note: 'Choose your official school textbook.', education_stages: ['primary', 'secondary'], reviewed_on: '2026-10-12' };
const reference = { id: 'cambridge-physics', title: 'Cambridge IGCSE Physics Coursebook', curriculum: 'british',
  publisher: 'Cambridge University Press', subjects: ['Physics'], grades: [], education_stages: ['secondary'],
  language: 'en', edition: 'Third edition', source_url: 'https://www.cambridgeinternational.org/resource-centre/',
  access: 'publisher', license: 'Publisher licence required', license_url: 'https://www.cambridgeinternational.org/resource-centre/',
  rights_note: 'Import or sharing needs publisher permission.', curriculum_note: 'Check the syllabus and examination year.', reviewed_on: '2026-10-12' };
const supplementary = { ...reference, id: 'openstax-maths', title: 'Elementary Algebra 2e', curriculum: 'american',
  publisher: 'OpenStax', subjects: ['Mathematics'], access: 'read_online', source_url: 'https://openstax.org/books/elementary-algebra-2e/pages/1-introduction',
  license: 'CC BY-NC-SA 4.0; AI use requires written permission', rights_note: 'Written publisher permission is required for AI offerings.' };
const browser = await launchBrowser();
try {
  const page = await browser.newPage(); const errors = []; const mutations = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (route.request().method() !== 'GET') mutations.push(path);
    let data = { items: [], unread: 0 };
    if (path === '/auth/me') data = { user, pending_legal: [] };
    if (path === '/me/usage') data = { plan: { code: 'pro', name: 'Pro' }, usage: { credits: { used: 0, limit: 100, reserved: 0, remaining: 100 } } };
    if (path === '/me/profile') data = { subjects: ['Physics'], grades: ['10'], curriculum: 'british' };
    if (path === '/memory') data = { preferences: [] };
    if (path === '/books/catalogue') data = { items: [], directories: {}, collections: [collection,
      { ...collection, id: 'british-cambridge-resources', title: 'Cambridge endorsed textbook directory', curriculum: 'british', access: 'publisher' }],
      reference_books: [reference, supplementary] };
    await route.fulfill({ json: data });
  });
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`${base}/books`);
    const sourceCatalogue = page.getByRole('region', { name: 'Textbook source catalogue' });
    await sourceCatalogue.getByRole('heading', { name: 'UAE MoE textbooks — Minhaji', exact: true }).waitFor();
    assert.equal(await sourceCatalogue.getByRole('heading', { name: reference.title, exact: true }).count(), 0);
    await page.getByLabel('Book curriculum', { exact: true }).selectOption('british');
    await sourceCatalogue.getByRole('heading', { name: reference.title, exact: true }).waitFor();
    assert.equal(await sourceCatalogue.getByRole('heading', { name: supplementary.title, exact: true }).count(), 0);
    await sourceCatalogue.getByLabel('Include supplementary references from other curricula').check();
    await sourceCatalogue.getByRole('heading', { name: supplementary.title, exact: true }).waitFor();
    await sourceCatalogue.getByLabel('Browse textbook titles', { exact: true }).fill('algebra');
    assert.equal(await sourceCatalogue.getByRole('heading', { name: reference.title, exact: true }).count(), 0);
    await sourceCatalogue.getByText('Usage rights & source', { exact: true }).click();
    await sourceCatalogue.getByText(supplementary.rights_note, { exact: true }).waitFor();
    const reading = sourceCatalogue.getByRole('link', { name: 'Read on publisher website' });
    assert.equal(await reading.getAttribute('href'), supplementary.source_url);
    assert.equal(await reading.getAttribute('target'), '_blank');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.getByLabel('Book availability', { exact: true }).selectOption('ready');
    assert.equal(await sourceCatalogue.count(), 0);
  }
  await page.goto(`${base}/digital-library`);
  await page.getByRole('heading', { name: 'Find your school textbooks', exact: true }).waitFor();
  assert.deepEqual(errors, []);
  assert.deepEqual(mutations.filter(path => path.startsWith('/books/')), []);
  console.log('Textbook sources: official scope, supplementary opt-in, title filter, rights, mobile layout and no AI/import mutations passed.');
} finally { await browser.close(); }

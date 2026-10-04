import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';

const base = process.env.BASE_URL || 'http://localhost:3101';
assertLocalTestBase(base);
const browser = await launchBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [], queries = [];
page.on('pageerror', error => errors.push(error.message));
const names = ['Clean Classroom', 'Warm Sand', 'Chalkboard', 'UAE Heritage', 'Green Emirates', 'Maths Studio',
  'Discovery Lab', 'Language & Stories', 'Arabic Classroom', 'Little Explorers', 'British Classroom',
  'CBSE Concept Builder', 'IB Inquiry Atelier', 'Emirates Learning', 'Future Makers'];
const templates = names.map((name, index) => ({ id: `style-${index}`, name, mode: 'builtin', builtin: true,
  can_edit: false, status: 'ready', is_default: name === 'Warm Sand', previews: ['/brand/favicon.png'],
  description: `${name} offers editable classroom layouts.`, tags: index >= 3 ? ['UAE', name === 'Maths Studio' ? 'Mathematics' : 'Classroom'] : ['Classroom'],
  colors: { primary: '#173E75', background: '#FFFFFF', text: '#1F2937' }, fonts: { body: 'Lato', heading: 'Montserrat' },
}));
const profile = { country: 'AE', school_name: 'Example School', curriculum: 'british', grades: ['8'], subjects: ['Mathematics'],
  teaching_languages: ['en'], class_duration_minutes: 45, default_template_id: 'style-1' };

await page.route('**/api/v1/**', async route => {
  const url = new URL(route.request().url()), path = url.pathname.replace('/api/v1', '');
  let data = { items: [], unread: 0, total: 0, active_count: 0 };
  if (path === '/auth/me') data = { user: { id: 'template-review', name: 'Template Teacher', email: 'teacher@example.com',
    role: 'teacher', permissions: [], status: 'active', email_verified: true, onboarding_completed: true }, pending_legal: [] };
  if (path === '/me/profile') {
    await new Promise(resolve => setTimeout(resolve, 400)); // Templates deliberately arrive before the saved profile.
    data = profile;
  }
  if (path === '/classes') data = { items: [{ id: 'class-8a', name: '8A', grade: '8', subject: 'Science', curriculum: 'cbse' }] };
  if (path === '/memory') data = { preferences: [] };
  if (path === '/usage/estimates') data = { costs: { course_plan: 1, slide: 1 }, usage: { credits: { available: 100 } } };
  if (path === '/me/usage') data = { plan: { name: 'Free', code: 'free' }, usage: { credits: { limit: 30, used: 0 } }, trial: null };
  if (path === '/templates') {
    queries.push(url.search);
    const name = url.searchParams.get('class_id') ? 'CBSE Concept Builder' : url.searchParams.get('subject') === 'English' ? 'Language & Stories' : 'Maths Studio';
    const recommended = [
      { template_id: 'style-1', name: 'Warm Sand', score: 100, reason: 'Your saved default design' },
      { template_id: templates.find(t => t.name === name).id, name, score: 60, reason: `Designed for ${url.searchParams.get('subject') || 'Mathematics'}` },
    ];
    data = { items: templates.map(t => ({ ...t, recommendation: recommended.find(r => r.template_id === t.id) })),
      recommendations: recommended, context: { ...profile, school_name: profile.school_name } };
  }
  if (path.startsWith('/templates/')) data = { ...templates.find(t => t.id === path.split('/')[2]), typography: { title_pt: 34, body_pt: 22 }, analysis: {}, content_style: {} };
  await route.fulfill({ status: 200, json: data });
});

try {
  await page.goto(`${base}/templates`);
  await page.getByRole('button', { name: 'Essential only' }).click();
  await page.getByRole('heading', { name: 'Suggested for your teaching', exact: true }).waitFor();
  await page.getByText('Your saved default design', { exact: false }).first().waitFor();
  await page.getByLabel('Filter designs').selectOption('uae');
  const builtinSection = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Built-in styles', exact: true }) });
  assert.equal(await builtinSection.getByRole('link').count(), 12, 'all twelve UAE designs are available');
  await page.getByLabel('Search designs').fill('mathematics');
  assert.equal(await builtinSection.getByRole('link').count(), 1, 'subject tags are searchable');
  await builtinSection.getByRole('link').click();
  await page.getByRole('heading', { name: 'Maths Studio', exact: true }).waitFor();
  await page.getByRole('link', { name: 'Use for a lesson', exact: true }).click();
  await page.getByRole('button', { name: 'Use Maths Studio', exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Use Maths Studio', exact: true }).getAttribute('aria-pressed'), 'true', 'explicit gallery choice overrides the default');

  await page.goto(`${base}/projects/new`);
  await page.getByRole('button', { name: 'Use Warm Sand', exact: true }).waitFor();
  await page.getByText('Selected: Warm Sand', { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Use Warm Sand', exact: true }).getAttribute('aria-pressed'), 'true', 'late profile response preserves the saved default');
  await page.getByRole('button', { name: 'Use Maths Studio', exact: true }).click();
  await page.getByLabel('Subject', { exact: true }).selectOption('English');
  await page.getByRole('button', { name: 'Use Language & Stories', exact: true }).waitFor();
  await page.getByText('Selected: Maths Studio', { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Use Maths Studio', exact: true }).getAttribute('aria-pressed'), 'true', 'new recommendations never overwrite a manual choice');
  assert.ok(queries.some(query => query.includes('subject=English') && query.includes('grade=8')), 'lesson context reaches recommendation API');

  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['/templates', '/projects/new']) {
      await page.goto(base + path);
      await page.locator('main h1').waitFor();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      assert.ok(overflow <= 1, `${path} fits ${width}px: ${overflow}px overflow`);
    }
  }
  await page.getByRole('button', { name: 'Show all 15 designs', exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('button[aria-label^="Use "]').length === 15);
  assert.equal(await page.getByRole('button', { name: /^Use / }).count(), 15);
  assert.deepEqual(errors, []);
  console.log('✓ UAE gallery, subject search, explicit/default/manual design choices, context suggestions and 320–1440px layouts passed.');
} catch (error) {
  console.log(await page.locator('main *').evaluateAll(elements => elements.filter(e => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 15).map(e => ({ tag: e.tagName, class: e.className, text: e.textContent?.slice(0, 100), right: e.getBoundingClientRect().right }))));
  await page.screenshot({ path: '/private/tmp/clastio-uae-export/browser-failure.png', fullPage: true });
  throw error;
} finally { await browser.close(); }

// Public SEO/answer discovery checks. No accounts, generation, payments or API writes.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { launchBrowser } from './browser.mjs';
import { assertLocalTestBase } from './fixtures.mjs';
import { teacherGuides } from '../lib/teacher-guides.ts';
import { searchQueryPatterns } from '../lib/search-query-patterns.ts';

const base = process.env.BASE_URL || 'http://localhost:3005';
const site = (process.env.EXPECTED_SITE_URL || base).replace(/\/+$/, '');
assertLocalTestBase(base);
const browser = await launchBrowser();
const errors = [], writes = [];
try {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 900 } });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/api/v1/**', route => {
    if (route.request().method() !== 'GET') { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const guidesBySlug = new Map(teacherGuides.map(guide => [guide.slug, guide]));
  assert.equal(guidesBySlug.size, teacherGuides.length, 'guide URLs must be unique');
  for (const guide of teacherGuides) {
    const response = await page.goto(`${base}/solutions/${guide.slug}`);
    assert.equal(response.status(), 200, guide.slug);
    assert.equal(await page.locator('h1').count(), 1);
    assert.equal(await page.locator('h1').innerText(), guide.title);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), `${site}/solutions/${guide.slug}`);
    assert.equal(await page.locator('meta[name="description"]').getAttribute('content'), guide.description);
    assert.equal(await page.locator('meta[property="og:image:width"]').getAttribute('content'), '1200');
    assert.equal(await page.locator('meta[name="twitter:card"]').getAttribute('content'), 'summary_large_image');
    assert.ok(!(await page.locator('meta[name="robots"]').getAttribute('content')).includes('noindex'));
    assert.equal((await page.title()).match(/Clastio/g)?.length, 1, 'brand appears once in the title');
    assert.ok((await response.text()).includes('Example teacher prompt'), 'answers are in server HTML');
    assert.equal(await page.getByRole('heading', { name: 'Common questions', exact: true }).count(), 1);
    const graph = JSON.parse(await page.locator('script[type="application/ld+json"]').first().textContent())['@graph'];
    const article = graph.find(node => node['@type'] === 'Article');
    const crumbs = graph.find(node => node['@type'] === 'BreadcrumbList');
    assert.equal(article.headline, guide.title);
    assert.equal(article.mainEntityOfPage, `${site}/solutions/${guide.slug}`);
    assert.equal(crumbs.itemListElement.at(-1).item, article.mainEntityOfPage);
    if (guide.reviewedAt) {
      assert.equal(article.dateModified, guide.reviewedAt);
      assert.equal(await page.locator('time').getAttribute('datetime'), guide.reviewedAt);
      assert.ok(guide.sources?.length, 'reviewed factual guides expose their sources');
      for (const source of guide.sources) assert.ok(await page.locator('#sources a').evaluateAll((links, url) => links.some(link => link.getAttribute('href') === url), source.url));
    } else assert.equal(article.dateModified, undefined, 'untouched guides get no invented freshness date');
    for (const slug of guide.relatedSlugs || []) assert.ok(guidesBySlug.has(slug), 'related guide exists');
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${guide.slug} fits ${width}`);
    }
  }
  await page.goto(base);
  assert.equal(await page.locator('h1').count(), 1);
  const graph = JSON.parse(await page.locator('script[type="application/ld+json"]').first().textContent())['@graph'];
  assert.deepEqual(graph.map(node => node['@type']), ['Organization', 'WebSite', 'SoftwareApplication']);
  assert.ok(graph.every(node => !node.aggregateRating && !node.review), 'no fabricated review schema');
  for (const slug of ['british-curriculum-lesson-planning', 'how-to-choose-ai-presentation-maker-for-teachers', 'ai-lesson-planning-costs-and-credits']) assert.ok(await page.locator(`a[href="/solutions/${slug}"]`).count());
  for (const width of [390, 1280]) { await page.setViewportSize({ width, height: 900 }); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `home fits ${width}`); }
  await page.screenshot({ path: fileURLToPath(new URL('../../../artifacts/discovery-audit-20261012/home-desktop.png', import.meta.url)) });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: fileURLToPath(new URL('../../../artifacts/discovery-audit-20261012/home-mobile.png', import.meta.url)) });
  const imagePath = await page.locator('meta[property="og:image"]').getAttribute('content');
  const imageResponse = await page.request.get(new URL(new URL(imagePath).pathname, base).href);
  assert.equal(imageResponse.status(), 200);
  assert.ok(imageResponse.headers()['content-type'].includes('image/png'));
  const imageBytes = await imageResponse.body();
  assert.equal(imageBytes.readUInt32BE(16), 1200);
  assert.equal(imageBytes.readUInt32BE(20), 630);

  const sitemap = await (await page.request.get(`${base}/sitemap.xml`)).text();
  for (const guide of teacherGuides) assert.ok(sitemap.includes(`${site}/solutions/${guide.slug}`));
  for (const path of ['/dashboard', '/copilot', '/books', '/login', '/signup']) assert.ok(!sitemap.includes(`${site}${path}<`));
  const robots = await (await page.request.get(`${base}/robots.txt`)).text();
  const groups = robots.split(/\n\s*\n/).filter(group => group.includes('User-Agent:'));
  for (const bot of ['*', 'OAI-SearchBot']) {
    const group = groups.find(value => value.includes(`User-Agent: ${bot}\n`));
    assert.ok(group, bot);
    for (const path of ['/books', '/digital-library', '/copilot', '/lesson-planners', '/demo-classes']) assert.ok(group.includes(`Disallow: ${path}`), `${bot}: ${path}`);
    assert.ok(group.includes('Allow: /api/v1/billing/plans$'));
  }
  const llms = await (await page.request.get(`${base}/llms.txt`)).text();
  assert.ok(llms.includes('## Public resources'));
  for (const guide of teacherGuides) assert.ok(llms.includes(`/solutions/${guide.slug}`));
  assert.ok(!llms.includes('/api/v1/'));
  for (const path of ['/copilot', '/books', '/digital-library', '/lesson-planners', '/demo-classes', '/login', '/signup']) {
    const response = await page.request.get(`${base}${path}`, { maxRedirects: 0 });
    assert.match(response.headers()['x-robots-tag'], /noindex/, path);
  }
  for (const path of ['/solutions/not-a-real-teacher-guide', '/solutions/toString', '/solutions/AI-PPT']) assert.equal((await page.request.get(`${base}${path}`)).status(), 404);
  for (const path of new Set(searchQueryPatterns.map(pattern => pattern.page))) assert.equal((await page.request.get(`${base}${path}`)).status(), 200, 'regex mapping resolves');

  // Use the real public catalogue to check that crawlers see current prices without JavaScript.
  const plans = await (await page.request.get(`${base}/api/v1/billing/plans`)).json();
  const pricingResponse = await page.goto(`${base}/pricing`);
  assert.equal(pricingResponse.status(), 200);
  for (const plan of plans.items) {
    assert.ok(await page.getByRole('heading', { name: plan.name, exact: true }).count(), 'plan is present in server HTML');
    if (plan.price_monthly_aed) assert.ok(await page.getByText(`AED ${new Intl.NumberFormat('en-AE', { maximumFractionDigits: 2 }).format(plan.price_monthly_aed)}`, { exact: true }).count(), 'current price is present in server HTML');
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  console.log(`${teacherGuides.length} guides pass server HTML/schema/canonicals/sources/mobile checks; current pricing renders without JavaScript; crawler files, private noindex, OG image, buyer links and regex page mappings pass. No account/API writes.`);
  await context.close();
} finally { await browser.close(); }

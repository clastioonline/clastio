// Read-only HTTP coverage of the rebuilt local public inventory and recovery exclusions.
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { assertLocalTestBase } from './fixtures.mjs';
import { PRIVATE_PATHS, PUBLIC_POLICY_ALIASES } from '../lib/seo.ts';
import { systemPages } from '../lib/system-pages.ts';
const resolver = registerHooks({ resolve(specifier, context, nextResolve) {
  return nextResolve(specifier === './usage' && context.parentURL?.endsWith('/lib/account-state.ts') ? './usage.ts' : specifier, context);
} });
const { authAccountSystemRoutes, billingSystemRoutes } = await import('../lib/account-state.ts');
resolver.deregister();
const base = process.env.BASE_URL || 'http://localhost:3005';
const site = process.env.NEXT_PUBLIC_SITE_URL || 'https://clastio.online';
assertLocalTestBase(base);
const get = path => fetch(base + path, { redirect: 'manual', credentials: 'omit', signal: AbortSignal.timeout(10000) });
const text = html => html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<[^>]*>/g, ' ').replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
const words = value => text(value).replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const sitemapResponse = await get('/sitemap.xml');
assert.equal(sitemapResponse.status, 200);
const sitemap = await sitemapResponse.text();
const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1]);
assert.equal(new Set(urls).size, urls.length);
const publicResults = [], stateResults = [], aliasResults = [], localLinks = new Set();
for (let start = 0; start < urls.length; start += 6) {
  const results = await Promise.allSettled(urls.slice(start, start + 6).map(async canonical => {
    assert.equal(new URL(canonical).origin, site);
    const path = new URL(canonical).pathname;
    const response = await get(path);
    assert.equal(response.status, 200, path);
    assert.ok(!/noindex/i.test(response.headers.get('x-robots-tag') || ''), path);
    const html = await response.text();
    const tag = /<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/.exec(html);
    assert.ok(tag, `${path} canonical present`);
    assert.equal(new URL(tag[1]).href, new URL(canonical).href, `${path} canonical`);
    const h1 = [...html.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)].map(match => text(match[1]));
    assert.equal(h1.length, 1, `${path} single server H1`);
    assert.ok(h1[0]);
    assert.ok(!/<meta\s+name="robots"\s+content="[^"]*noindex/i.test(html), `${path} public indexing`);
    for (const link of html.matchAll(/<a\b[^>]*href="([^"#]+)"/g)) {
      const href = link[1].replace(/&amp;/g, '&');
      const target = new URL(href, canonical);
      if (target.origin === site) localLinks.add(target.pathname + target.search);
    }
    if (path.startsWith('/legal/')) {
      const documentResponse = await get('/api/v1' + path);
      assert.equal(documentResponse.status, 200);
      const document = await documentResponse.json();
      assert.equal(h1[0], document.title);
      assert.ok(html.includes('legal-doc mt-6'), 'actual published document container');
      assert.ok(document.content.trim().length > 100);
      // The source notice may retain legacy branding; rendering does not rewrite published versions.
      const sample = document.content.split('\n').find(line => line.trim().length > 60 && !/^[#>*-]/.test(line));
      assert.ok(sample && words(html).includes(words(sample)), `${path} real paragraph in server HTML`);
    }
    return { path, status: response.status, h1: h1[0], canonical };
  }));
  for (const result of results) { if (result.status === 'rejected') throw result.reason; publicResults.push(result.value); }
}
const states = [...systemPages.map(page => ({ path: '/' + page.slug, status: page.status })),
  ...[...authAccountSystemRoutes, ...billingSystemRoutes].map(page => ({ path: '/' + page.slug, status: 200 })),
  { path: '/data-export-request', status: 200 }];
for (const state of states) {
  assert.ok(PRIVATE_PATHS.includes(state.path));
  const response = await get(state.path);
  assert.equal(response.status, state.status, state.path);
  assert.match(response.headers.get('x-robots-tag'), /noindex/);
  assert.ok(!urls.includes(site + state.path));
  stateResults.push({ ...state, noindex: true });
}
for (const alias of PUBLIC_POLICY_ALIASES) {
  const response = await get(alias.source);
  assert.equal(response.status, 308);
  assert.equal(new URL(response.headers.get('location'), base).pathname, alias.destination);
  assert.ok(!urls.includes(site + alias.source));
  aliasResults.push({ ...alias, status: response.status });
}
const expectedErrors = new Map(states.map(state => [state.path, state.status]));
const expectedAliases = new Set(PUBLIC_POLICY_ALIASES.map(alias => alias.source));
for (const path of localLinks) {
  const response = await get(path);
  assert.equal(response.status, expectedAliases.has(path) ? 308 : expectedErrors.get(path.split('?')[0]) || 200, `linked route ${path}`);
}
const robots = await (await get('/robots.txt')).text();
const llms = await (await get('/llms.txt')).text();
for (const state of states) { assert.ok(robots.includes('Disallow: ' + state.path)); assert.ok(!llms.includes(site + state.path + ')')); }
assert.ok(!sitemap.includes('clerk.'));
for (const path of ['/contact', '/help', '/legal', '/security', '/data-privacy', '/data-processing', '/accessibility', '/copyright', '/cancellation-policy']) assert.ok(urls.includes(site + path));
const directory = new URL('../../../artifacts/system-pages-20261012/', import.meta.url);
await mkdir(directory, { recursive: true });
await writeFile(new URL('public-http.json', directory), JSON.stringify({ base, canonicalOrigin: site, publicResults, stateResults, aliasResults, linkedRoutesChecked: localLinks.size, apiWrites: 0 }, null, 2) + '\n');
console.log(`${urls.length} public sitemap URLs have 200, matching canonical and server H1; actual policies contain published text; ${states.length} state routes excluded/noindex; ${aliasResults.length} canonical redirects and ${localLinks.size} linked routes pass. No API writes.`);

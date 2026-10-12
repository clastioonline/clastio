import assert from 'node:assert/strict';
import { test } from 'node:test';
import { jsonLd, normalizeSiteOrigin, pageMetadata, PRIVATE_PATHS, PUBLIC_POLICY_ALIASES, siteGraph, siteUrl, SOCIAL_IMAGE } from '../lib/seo.ts';
import { systemPages } from '../lib/system-pages.ts';

test('canonical origins exclude paths, query strings and credentials', () => {
  assert.equal(normalizeSiteOrigin(' https://Clastio.online/site/?utm_source=preview#section '), 'https://clastio.online');
  assert.equal(normalizeSiteOrigin('http://localhost:3005/'), 'http://localhost:3005');
  for (const value of ['not-a-url', 'javascript:alert(1)', 'https://user:password@example.com', '']) {
    assert.equal(normalizeSiteOrigin(value), 'https://clastio.online');
  }
});

test('public canonical URLs are stable and cannot point to another origin', () => {
  const origin = normalizeSiteOrigin(process.env.NEXT_PUBLIC_SITE_URL);
  assert.equal(siteUrl('/solutions/example/?utm_source=test#example'), `${origin}/solutions/example`);
  for (const path of ['//elsewhere.example', '/\\elsewhere.example', 'https://elsewhere.example', '/\t/elsewhere.example']) {
    assert.throws(() => siteUrl(path));
  }
  const metadata = pageMetadata('Example guide', 'Reviewed classroom guidance', '/solutions/example');
  assert.equal(metadata.alternates.canonical, `${origin}/solutions/example`);
  assert.equal(metadata.openGraph.url, metadata.alternates.canonical);
  assert.equal(metadata.twitter.card, 'summary_large_image');
  assert.equal(metadata.title.absolute, 'Example guide | Clastio');
  assert.equal(metadata.openGraph.title, metadata.title.absolute);
  assert.equal(metadata.twitter.title, metadata.title.absolute);
  assert.equal(pageMetadata('Clastio pricing', 'Plans', '/pricing').title.absolute, 'Clastio pricing');
  assert.equal(metadata.robots.index, true);
  assert.equal(SOCIAL_IMAGE.width, 1200);
  assert.equal(SOCIAL_IMAGE.height, 630);
});

test('account routes, authentication and APIs stay outside public discovery', () => {
  for (const path of ['/books', '/copilot', '/digital-library', '/lesson-planners', '/demo-classes', '/rewards', '/login', '/signup', '/api']) {
    assert.ok(PRIVATE_PATHS.includes(path), `${path} is a private crawl prefix`);
  }
  for (const path of ['/pricing', '/solutions', '/faq', '/legal', '/contact', '/help', '/security', '/accessibility', '/data-processing', '/cancellation-policy']) assert.ok(!PRIVATE_PATHS.includes(path));
  for (const page of systemPages) assert.ok(PRIVATE_PATHS.includes(`/${page.slug}`), `system state ${page.slug} is private to crawlers`);
  for (const path of ['/payment-success', '/payment-failed', '/verification-success', '/account-deleted', '/delete-account', '/data-export-request', '/session-expired', '/usage-limit']) assert.ok(PRIVATE_PATHS.includes(path));
});

test('policy aliases point to published canonical paths without redirect chains', () => {
  const sources = new Set(PUBLIC_POLICY_ALIASES.map(alias => alias.source));
  assert.equal(sources.size, PUBLIC_POLICY_ALIASES.length);
  for (const { source, destination } of PUBLIC_POLICY_ALIASES) {
    assert.match(source, /^\/[a-z-]+$/);
    assert.match(destination, /^\/legal\/[a-z_]+$/);
    assert.ok(!sources.has(destination));
    assert.ok(!PRIVATE_PATHS.includes(source));
  }
});

test('site identity graph uses stable references without invented business or review facts', () => {
  const graph = siteGraph()['@graph'];
  const organization = graph.find(node => node['@type'] === 'Organization');
  const website = graph.find(node => node['@type'] === 'WebSite');
  const app = graph.find(node => node['@type'] === 'SoftwareApplication');
  assert.equal(website.publisher['@id'], organization['@id']);
  assert.equal(app.publisher['@id'], organization['@id']);
  assert.ok(app['@id'].endsWith('/#application'));
  for (const key of ['legalName', 'address', 'taxID', 'sameAs', 'aggregateRating', 'offers']) {
    assert.ok(graph.every(node => !Object.hasOwn(node, key)), `no invented ${key}`);
  }
  const serialized = jsonLd({ name: '</script><script>alert(1)</script>' });
  assert.ok(!serialized.includes('<'));
  assert.equal(JSON.parse(serialized).name, '</script><script>alert(1)</script>');
});

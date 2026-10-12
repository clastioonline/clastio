import assert from 'node:assert/strict';
import test from 'node:test';
import { renderSystemPageHtml, safeSystemHref, systemPageForSlug, systemPages } from '../lib/system-pages.ts';

test('generic system routes have explicit HTTP statuses and exact allowlist lookup', () => {
  const expected = { 400: 400, 401: 401, 403: 403, 404: 404, 409: 409, 429: 429, 500: 500, 503: 503, maintenance: 503, offline: 503, 'browser-not-supported': 200, 'permission-required': 403 };
  assert.equal(systemPages.length, Object.keys(expected).length);
  for (const [slug, status] of Object.entries(expected)) assert.equal(systemPageForSlug(slug)?.status, status);
  for (const slug of ['unknown', '404/foo', '404/', 'constructor', 'toString', 'session-expired']) assert.equal(systemPageForSlug(slug), undefined);
});

test('every rendered system page is self-contained, noindex and has one clear title with recovery links', () => {
  for (const page of systemPages) {
    const html = renderSystemPageHtml(page);
    assert.match(html, /^<!doctype html><html lang="en"/);
    assert.match(html, /<meta name="robots" content="noindex,nofollow">/);
    assert.equal((html.match(/<h1\b/g) || []).length, 1);
    assert.match(html, /<style>[^]*\.sys-page/);
    assert.ok(html.includes(`href="${page.primaryAction.href}"`));
    assert.match(html, /href="\/help"/);
    assert.match(html, /href="\/contact"/);
    assert.doesNotMatch(html, /<script|\/api\/|teacher[_-]?id|checkout_id|session[_-]?token/);
  }
});

test('system HTML escapes content and never creates executable or external recovery links', () => {
  const page = { ...systemPageForSlug('404'), title: '<img src=x onerror=alert(1)>', description: '"/><script>secret()</script>',
    primaryAction: { href: 'javascript:alert(1)', label: '<script>click()</script>' },
    secondaryAction: { href: '//other.example', label: '"Bad link"' }, hints: ['<b>Untrusted hint</b>'] };
  const html = renderSystemPageHtml(page);
  assert.doesNotMatch(html, /<script|<img src=x|href="javascript:|href="\/\/other/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;script&gt;secret\(\)&lt;\/script&gt;/);
  assert.match(html, /&lt;b&gt;Untrusted hint&lt;\/b&gt;/);
  assert.equal((html.match(/class="sys-action[^]*?href="\/"/g) || []).length, 2);
});

test('recovery URLs reject protocols, authority links, backslashes and control characters', () => {
  for (const href of ['javascript:alert(1)', 'https://other.example', '//other.example', '/\\other.example', '/help\nmalicious', '/\u0000help']) assert.equal(safeSystemHref(href), '/');
  for (const href of ['/', '/help', '/login?next=%2Fdashboard', '/legal/privacy#uploads']) assert.equal(safeSystemHref(href), href);
});

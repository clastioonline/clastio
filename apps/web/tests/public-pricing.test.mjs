import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchPublicPricing, parsePublicPricing } from '../lib/public-pricing.ts';

const catalogue = () => ({
  items: [{ code: 'free', name: 'Free', price_monthly_aed: 0, price_annual_aed: 0,
    limits: { credits: 60, max_lectures: 3 }, features: [] },
  { code: 'pro', name: 'Teacher Pro', price_monthly_aed: 249.75, price_annual_aed: 2490,
    limits: { credits: 2000, max_lectures: 20, private_extra: 'not needed' }, features: ['Editable PowerPoints'] }],
  currency: 'AED', vat_rate: .05, online_payments: false, payment_provider: null,
  trial: { enabled: true, plan: 'pro', days: 7, credits: 50 }, private_extra: 'not needed',
});

test('public catalogue preserves configured prices and whitelists display fields', () => {
  const parsed = parsePublicPricing(catalogue());
  assert.equal(parsed.items[1].price_monthly_aed, 249.75);
  assert.deepEqual(parsed.items[1].limits, { credits: 2000, max_lectures: 20 });
  assert.equal(parsed.private_extra, undefined);
  assert.equal(parsePublicPricing({ ...catalogue(), currency: undefined }).currency, 'AED');
});

test('malformed, empty, wrong-currency and inconsistent catalogues are unavailable', () => {
  const invalid = [null, [], {}, { ...catalogue(), currency: 'USD' },
    { ...catalogue(), items: [] }, { ...catalogue(), items: [catalogue().items[0], catalogue().items[0]] },
    { ...catalogue(), vat_rate: 5 }, { ...catalogue(), online_payments: 'true' },
    { ...catalogue(), trial: { enabled: true, plan: 'missing', days: 7, credits: 50 } }];
  for (const value of invalid) assert.equal(parsePublicPricing(value), null);
  for (const [field, value] of [['price_monthly_aed', -1], ['price_annual_aed', Infinity],
    ['features', ['valid', 3]], ['limits', { credits: '2000', max_lectures: 20 }], ['name', '']]) {
    const bad = catalogue();
    bad.items[1][field] = value;
    assert.equal(parsePublicPricing(bad), null, field);
  }
});

test('server fetch selects only the public endpoint without credentials or a price cache', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(String(url), 'http://localhost:8123/api/v1/billing/plans');
    assert.equal(init.method, 'GET');
    assert.equal(init.credentials, 'omit');
    assert.equal(init.redirect, 'error');
    assert.equal(init.cache, 'no-store');
    assert.deepEqual(init.headers, { accept: 'application/json' });
    assert.ok(init.signal instanceof AbortSignal);
    return Response.json(catalogue());
  });
  assert.equal((await fetchPublicPricing('http://localhost:8123/private?ignored=1')).items[1].price_monthly_aed, 249.75);
});

test('unavailable and malformed public API responses produce no substitute prices', async (t) => {
  for (const response of [Response.json({}, { status: 503 }), Response.json({ items: 'broken' }),
    new Response('not json', { headers: { 'content-type': 'application/json' } }), new Response('<html>Error</html>')]) {
    t.mock.method(globalThis, 'fetch', async () => response);
    assert.equal(await fetchPublicPricing(), null);
  }
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unavailable'); });
  assert.equal(await fetchPublicPricing(), null);
});

test('oversized and streaming response bodies are bounded', async (t) => {
  let cancelled = false;
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(70 * 1024)); },
    cancel() { cancelled = true; },
  }), { headers: { 'content-type': 'application/json' } });
  t.mock.method(globalThis, 'fetch', async () => response);
  assert.equal(await fetchPublicPricing(), null);
  assert.equal(cancelled, true);
  t.mock.method(globalThis, 'fetch', async () => Response.json(catalogue(), {
    headers: { 'content-length': String(70 * 1024) },
  }));
  assert.equal(await fetchPublicPricing(), null);
});

test('invalid or credential-bearing backend URLs are never contacted', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(catalogue()); });
  for (const url of ['not a URL', 'file:///tmp/plans', 'https://user:password@example.com']) {
    assert.equal(await fetchPublicPricing(url), null);
  }
  assert.equal(calls, 0);
});

test('a stalled upstream fetch is aborted within the timeout', async (t) => {
  t.mock.method(globalThis, 'fetch', async (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new Error('Aborted')), { once: true });
  }));
  const started = performance.now();
  assert.equal(await fetchPublicPricing(), null);
  assert.ok(performance.now() - started < 4000);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchPublicJson } from '../lib/public-api.ts';
import { legalDocumentTitles, parseLegalDocument, parseLegalIndex, validLegalVersion } from '../lib/legal-documents.ts';

const version = (extra = {}) => ({ type: 'privacy', title: 'Privacy Policy', version: '2.0',
  effective_from: '2026-10-12T00:00:00+00:00', status: 'published', ...extra });
const document = (extra = {}) => ({ ...version(), content: '# Privacy\nSynthetic teacher policy content.',
  summary_of_changes: 'Clarified the synthetic fixture.', versions: [version(), version({ version: '1.0', status: 'archived' })],
  ...extra });
const unavailable = { status: 0, data: null };

function backendOrigin(t, value = 'https://api.example.test') {
  // Only this public configuration variable is changed; no dotenv files or keys are read.
  const previous = process.env.API_URL;
  if (value === undefined) delete process.env.API_URL;
  else process.env.API_URL = value;
  t.after(() => {
    if (previous === undefined) delete process.env.API_URL;
    else process.env.API_URL = previous;
  });
}

test('the public fetch allowlist admits only the reviewed legal and public-config resource shapes', async (t) => {
  backendOrigin(t);
  const seen = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    seen.push(String(url));
    assert.equal(init.method ?? 'GET', 'GET');
    assert.equal(init.credentials, 'omit');
    assert.equal(init.redirect, 'error');
    assert.equal(init.cache, 'no-store');
    assert.deepEqual(init.headers, { accept: 'application/json' });
    assert.ok(init.signal instanceof AbortSignal);
    assert.equal(init.body, undefined);
    return Response.json({ fixture: true });
  });
  const paths = ['/api/v1/legal', '/api/v1/public/config',
    ...Object.keys(legalDocumentTitles).map(type => `/api/v1/legal/${type}`),
    '/api/v1/legal/privacy?version=1.0', '/api/v1/legal/privacy?version=2026-10.2'];
  for (const path of paths) assert.deepEqual(await fetchPublicJson(path), { status: 200, data: { fixture: true } });
  assert.deepEqual(seen, paths.map(path => `https://api.example.test${path}`));
});

test('private, cross-origin, traversal and additional-query resources are rejected before fetch', async (t) => {
  backendOrigin(t);
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json({}); });
  const rejected = ['/api/v1/auth/me', '/api/v1/admin/legal', '/api/v1/billing/plans',
    '/api/v1/public/config/private', '/api/v1/legal/privacy/history', '/api/v1/legal/',
    '/api/v1/legal/privacy?other=1', '/api/v1/legal/privacy?version=1.0&other=1',
    '/api/v1/legal/privacy#section', '/api/v1/legal/../auth/me', '/api/v1/legal/%2e%2e/auth/me',
    '//external.example/api/v1/legal', 'https://external.example/api/v1/legal'];
  for (const path of rejected) await assert.rejects(fetchPublicJson(path), /Unsupported public resource path/, path);
  assert.equal(calls, 0);
});

test('invalid, non-HTTP and credential-bearing origins produce unavailable results without a request', async (t) => {
  backendOrigin(t);
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json({}); });
  for (const origin of ['not a URL', 'file:///tmp/policies', 'ftp://api.example.test',
    'https://fixture-user:fixture-password@api.example.test', 'http://fixture-user@localhost:8000']) {
    process.env.API_URL = origin;
    assert.deepEqual(await fetchPublicJson('/api/v1/legal/privacy'), unavailable);
  }
  assert.equal(calls, 0);
});

test('missing policies keep their 404 and other HTTP failures are not replaced by policy data', async (t) => {
  backendOrigin(t);
  for (const status of [404, 401, 403, 503]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ error: { message: 'Fixture failure' } }, { status }));
    assert.deepEqual(await fetchPublicJson('/api/v1/legal/privacy?version=missing'), { status, data: null });
  }
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('Fixture network unavailable'); });
  assert.deepEqual(await fetchPublicJson('/api/v1/legal'), unavailable);
});

test('missing bodies, wrong media types and malformed JSON are unavailable', async (t) => {
  backendOrigin(t);
  for (const response of [new Response(null, { status: 204 }), new Response('<html>Error</html>'),
    new Response('not json', { headers: { 'content-type': 'application/json' } })]) {
    t.mock.method(globalThis, 'fetch', async () => response);
    assert.deepEqual(await fetchPublicJson('/api/v1/legal'), unavailable);
  }
});

test('UTF-8 split across response chunks is decoded and the stream reader is released', async (t) => {
  backendOrigin(t);
  const data = { fixture: 'Arabic العربية and emoji 🌍' };
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  const response = new Response(new ReadableStream({ start(controller) {
    for (let offset = 0; offset < bytes.length; offset += 2) controller.enqueue(bytes.slice(offset, offset + 2));
    controller.close();
  } }), { headers: { 'content-type': 'application/json; charset=utf-8' } });
  t.mock.method(globalThis, 'fetch', async () => response);
  assert.deepEqual(await fetchPublicJson('/api/v1/public/config'), { status: 200, data });
  assert.equal(response.body.locked, false);
});

test('declared and streamed oversized bodies are cancelled before any result is exposed', async (t) => {
  backendOrigin(t);
  for (const declared of [false, true]) {
    let cancelled = false;
    const response = new Response(new ReadableStream({
      start(controller) { controller.enqueue(new Uint8Array(65)); },
      cancel() { cancelled = true; },
    }), { headers: { 'content-type': 'application/json', ...(declared ? { 'content-length': '65' } : {}) } });
    t.mock.method(globalThis, 'fetch', async () => response);
    assert.deepEqual(await fetchPublicJson('/api/v1/legal', 64), unavailable);
    assert.equal(cancelled, true);
    assert.equal(response.body.locked, false);
  }
});

test('stream failures produce an unavailable result and release the reader', async (t) => {
  backendOrigin(t);
  const response = new Response(new ReadableStream({ start(controller) {
    controller.error(new Error('Fixture stream failed'));
  } }), { headers: { 'content-type': 'application/json' } });
  t.mock.method(globalThis, 'fetch', async () => response);
  assert.deepEqual(await fetchPublicJson('/api/v1/legal'), unavailable);
  assert.equal(response.body.locked, false);
});

test('stalled upstream requests are aborted within the bounded timeout', async (t) => {
  backendOrigin(t);
  t.mock.method(globalThis, 'fetch', async (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new Error('Fixture timeout')), { once: true });
  }));
  const started = performance.now();
  assert.deepEqual(await fetchPublicJson('/api/v1/legal'), unavailable);
  assert.ok(performance.now() - started < 4000);
});

test('published and archived documents preserve same-type history and whitelist public fields', () => {
  const parsed = parseLegalDocument(document({ internal_note: 'not public' }), 'privacy');
  assert.equal(parsed.status, 'published');
  assert.equal(parsed.internal_note, undefined);
  assert.deepEqual(parsed.versions, [version(), version({ version: '1.0', status: 'archived' })]);
  assert.equal(parseLegalDocument(document({ status: 'archived' }), 'privacy').status, 'archived');
  const optional = parseLegalDocument(document({ effective_from: undefined, summary_of_changes: undefined }), 'privacy');
  assert.equal(optional.effective_from, null);
  assert.equal(optional.summary_of_changes, null);
});

test('only recognised policy types and safe version identifiers are accepted', () => {
  for (const value of ['1.0', 'v2', '2026.10.12', 'release-2']) assert.equal(validLegalVersion(value), true);
  for (const value of ['', 'x'.repeat(21), '../1.0', 'v_1', '1.0?other=1', '1.0\n', ' 1.0']) {
    assert.equal(validLegalVersion(value), false, JSON.stringify(value));
  }
  for (const type of ['unknown', 'constructor', '__proto__', 'toString']) {
    assert.equal(parseLegalDocument(document({ type }), type), null);
  }
  assert.equal(parseLegalDocument(document(), 'terms'), null);
  assert.equal(parseLegalDocument(document({ version: '../1.0' }), 'privacy'), null);
});

test('invalid publication states and non-string statuses cannot become published policies', () => {
  for (const status of ['draft', 'scheduled', 'deleted', '', null, 1, ['published'], ['archived']]) {
    assert.equal(parseLegalDocument(document({ status }), 'privacy'), null, JSON.stringify(status));
  }
});

test('blank or malformed policy titles and content cannot produce a readable document', () => {
  for (const [field, value] of [['title', ''], ['title', '  \n'], ['title', 3], ['title', 'x'.repeat(201)],
    ['content', ''], ['content', '\n \t '], ['content', {}], ['content', 'x'.repeat(200001)]]) {
    assert.equal(parseLegalDocument(document({ [field]: value }), 'privacy'), null, field);
  }
});

test('foreign-type, draft, malformed and excessive document histories are rejected', () => {
  for (const versions of [[version({ type: 'terms' })], [version({ status: 'draft' })],
    [version({ effective_from: 'not a date' })], [null], {}, Array.from({ length: 201 }, () => version())]) {
    assert.equal(parseLegalDocument(document({ versions }), 'privacy'), null);
  }
  for (const value of [42, {}, 'x'.repeat(5001)]) {
    assert.equal(parseLegalDocument(document({ summary_of_changes: value }), 'privacy'), null);
  }
});

test('legal index exposes current published entries without labelling archived or invalid entries published', () => {
  const valid = version();
  const other = version({ type: 'terms', title: 'Terms & Conditions' });
  const items = [valid, version({ status: 'archived', version: '1.0' }), version({ status: 'draft' }),
    version({ type: 'constructor' }), version({ effective_from: 'not a date' }), other];
  assert.deepEqual(parseLegalIndex({ items }), [valid, other]);
  for (const value of [null, [], {}, { items: 'not an array' }, { items: Array.from({ length: 101 }, () => valid) }]) {
    assert.deepEqual(parseLegalIndex(value), []);
  }
});

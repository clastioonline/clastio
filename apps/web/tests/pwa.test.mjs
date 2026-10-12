import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../public/sw.js', import.meta.url), 'utf8');

function worker() {
  const handlers = {}, calls = [], stored = new Map(), notices = [];
  const self = {
    location: { origin: 'https://clastio.online' },
    addEventListener: (name, handler) => { handlers[name] = handler; },
    skipWaiting: async () => {},
    clients: { claim: async () => {}, matchAll: async () => [], openWindow: async url => calls.push(['open', url]) },
    registration: { showNotification: async (title, options) => notices.push({ title, ...options }), getNotifications: async () => [] },
  };
  const cache = { put: async (path, value) => stored.set(path, value), match: async path => stored.get(path) };
  let fetcher = async path => path === '/offline'
    ? { ok: false, status: 503, type: 'basic', headers: new Headers({ 'Content-Type': 'text/html; charset=utf-8', 'X-Clastio-System-Page': 'offline' }) }
    : { ok: true, type: 'basic', image: true };
  const fetch = async (path, options) => { calls.push(['fetch', path, options]); return fetcher(path, options); };
  vm.runInNewContext(source, { self, URL, fetch, caches: { open: async () => cache, keys: async () => ['clastio-public-brand-v0', 'unrelated-cache'], delete: async name => calls.push(['delete', name]) } });
  return { self, handlers, calls, stored, notices, setFetcher: next => { fetcher = next; } };
}

async function run(handler, extra = {}) {
  let work;
  handler({ ...extra, waitUntil: promise => { work = promise; } });
  await work;
}

test('service worker preloads only public logos and the marked offline screen with no account cookies', async () => {
  const state = worker();
  await run(state.handlers.install);
  assert.deepEqual([...state.stored.keys()], ['/brand/favicon.png', '/brand/app-icon-512.png', '/offline']);
  assert.equal(state.calls.filter(call => call[0] === 'fetch').length, 3);
  for (const call of state.calls) if (call[0] === 'fetch') assert.equal(call[2].credentials, 'omit');
  await run(state.handlers.activate);
  assert.deepEqual(state.calls.filter(call => call[0] === 'delete'), [['delete', 'clastio-public-brand-v0']]);
});

test('authenticated pages, API calls, teacher files and nonpublic requests always use the network', async () => {
  const { handlers } = worker();
  for (const [method, path] of [
    ['GET', '/dashboard'], ['GET', '/api/v1/auth/me'], ['GET', '/api/v1/assets/private-ppt/download'],
    ['GET', '/lessons/private-lesson'], ['GET', '/brand/favicon.png?user=private'], ['POST', '/brand/favicon.png'],
    ['GET', '/login'], ['GET', '/reset-password?token=private'], ['GET', '/session-expired'],
    ['GET', '/checkout'], ['GET', '/payment-success?checkout_id=private'], ['GET', '/account-deleted'],
    ['GET', '/not-a-public-page'], ['POST', '/help'],
    ['GET', 'https://other.example/brand/favicon.png'],
  ]) {
    handlers.fetch({ request: { method, mode: 'navigate', destination: 'document', url: new URL(path, 'https://clastio.online').href }, respondWith: () => assert.fail(`Unexpected cache interception: ${path}`) });
  }
});

test('a network failure on a known public document uses only the public offline screen', async () => {
  const state = worker();
  await run(state.handlers.install);
  state.setFetcher(async () => { throw new TypeError('Failed to fetch'); });
  for (const path of ['/', '/help', '/contact', '/solutions/ai-presentation-maker-for-teachers', '/legal/privacy']) {
    let work;
    state.handlers.fetch({ request: { method: 'GET', mode: 'navigate', destination: 'document', url: `https://clastio.online${path}` }, respondWith: promise => { work = promise; } });
    const response = await work;
    assert.equal(response, state.stored.get('/offline'));
    assert.equal(response.status, 503);
  }
  assert.deepEqual([...state.stored.keys()], ['/brand/favicon.png', '/brand/app-icon-512.png', '/offline']);
});

test('public navigation preserves HTTP errors and does not cache requested page responses', async () => {
  const state = worker();
  await run(state.handlers.install);
  for (const status of [200, 403, 404, 500, 503]) {
    const networkResponse = { status, body: `Network response ${status}` };
    state.setFetcher(async () => networkResponse);
    let work;
    state.handlers.fetch({ request: { method: 'GET', mode: 'navigate', destination: 'document', url: 'https://clastio.online/solutions/missing-guide' }, respondWith: promise => { work = promise; } });
    assert.equal(await work, networkResponse);
  }
  assert.deepEqual([...state.stored.keys()], ['/brand/favicon.png', '/brand/app-icon-512.png', '/offline']);
});

test('unmarked HTML and redirected sign-in responses cannot become the offline page', async () => {
  for (const response of [
    { status: 503, type: 'basic', headers: new Headers({ 'Content-Type': 'text/html' }) },
    { status: 200, type: 'basic', headers: new Headers({ 'Content-Type': 'text/html', 'X-Clastio-System-Page': 'offline' }) },
    { status: 503, type: 'opaque', headers: new Headers({ 'Content-Type': 'text/html', 'X-Clastio-System-Page': 'offline' }) },
  ]) {
    const state = worker();
    state.setFetcher(async path => path === '/offline' ? response : { ok: true, type: 'basic' });
    await run(state.handlers.install);
    assert.equal(state.stored.has('/offline'), false);
  }
});

test('public non-document fetches stay network-only and an unavailable fallback keeps its network error', async () => {
  const state = worker();
  for (const request of [
    { mode: 'cors', destination: '' }, { mode: 'navigate', destination: 'iframe' },
  ]) state.handlers.fetch({ request: { ...request, method: 'GET', url: 'https://clastio.online/help' }, respondWith: () => assert.fail('A non-document request was intercepted') });
  state.setFetcher(async () => { throw new TypeError('Failed to fetch'); });
  let work;
  state.handlers.fetch({ request: { method: 'GET', mode: 'navigate', destination: 'document', url: 'https://clastio.online/help' }, respondWith: promise => { work = promise; } });
  await assert.rejects(work, /Failed to fetch/);
});

test('push always displays a visible fallback and uses a stable tag', async () => {
  const { handlers, notices } = worker();
  await run(handlers.push, { data: { json: () => ({ title: 'Ready', body: 'Open lesson', tag: 'delivery-one', url: '/lessons/one' }) } });
  assert.equal(notices[0].title, 'Ready');
  assert.equal(notices[0].tag, 'delivery-one');
  assert.equal(notices[0].icon, '/brand/favicon.png');
  await run(handlers.push, { data: { json: () => { throw new Error('Invalid payload'); } } });
  assert.equal(notices[1].title, 'Clastio update');
  assert.equal(notices[1].body, 'Open Clastio to see your latest update.');
});

test('notification clicks never navigate to another origin or to credentials', async () => {
  for (const path of ['https://evil.example', '//evil.example', '/\\evil.example', 'https://user:secret@clastio.online/private']) {
    const { handlers, calls } = worker();
    await run(handlers.notificationclick, { notification: { close: () => {}, data: { url: path } } });
    assert.deepEqual(calls, [['open', 'https://clastio.online/notifications']]);
  }
  const { handlers, calls } = worker();
  await run(handlers.notificationclick, { notification: { close: () => {}, data: { url: '/lessons/ready' } } });
  assert.deepEqual(calls, [['open', 'https://clastio.online/lessons/ready']]);
});

test('signing out clears displayed device notifications', async () => {
  const { self, handlers } = worker();
  let closed = 0;
  self.registration.getNotifications = async () => [{ close: () => closed++ }, { close: () => closed++ }];
  await run(handlers.message, { data: { type: 'CLASTIO_SIGNED_OUT' } });
  assert.equal(closed, 2);
});

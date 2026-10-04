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
  const fetch = async (path, options) => { calls.push(['fetch', path, options]); return { ok: true, type: 'basic', image: true }; };
  vm.runInNewContext(source, { self, URL, fetch, caches: { open: async () => cache, keys: async () => ['clastio-public-brand-v0', 'unrelated-cache'], delete: async name => calls.push(['delete', name]) } });
  return { self, handlers, calls, stored, notices };
}

async function run(handler, extra = {}) {
  let work;
  handler({ ...extra, waitUntil: promise => { work = promise; } });
  await work;
}

test('service worker preloads only public logo assets with no account cookies', async () => {
  const state = worker();
  await run(state.handlers.install);
  assert.deepEqual([...state.stored.keys()], ['/brand/favicon.png', '/brand/app-icon-512.png']);
  assert.equal(state.calls.filter(call => call[0] === 'fetch').length, 2);
  for (const call of state.calls) if (call[0] === 'fetch') assert.equal(call[2].credentials, 'omit');
  await run(state.handlers.activate);
  assert.deepEqual(state.calls.filter(call => call[0] === 'delete'), [['delete', 'clastio-public-brand-v0']]);
});

test('authenticated pages, API calls, teacher files and nonpublic requests always use the network', async () => {
  const { handlers } = worker();
  for (const [method, path] of [
    ['GET', '/dashboard'], ['GET', '/api/v1/auth/me'], ['GET', '/api/v1/assets/private-ppt/download'],
    ['GET', '/lessons/private-lesson'], ['GET', '/brand/favicon.png?user=private'], ['POST', '/brand/favicon.png'],
    ['GET', 'https://other.example/brand/favicon.png'],
  ]) {
    handlers.fetch({ request: { method, url: new URL(path, 'https://clastio.online').href }, respondWith: () => assert.fail(`Unexpected cache interception: ${path}`) });
  }
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

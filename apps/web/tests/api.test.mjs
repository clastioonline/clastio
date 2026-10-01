import assert from 'node:assert/strict';
import { test } from 'node:test';
import { api, streamPost } from '../lib/api.ts';

function streamResponse(chunks) {
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
      controller.close();
    },
  }));
}

test('false JSON bodies use POST', async (t) => {
  t.mock.method(globalThis, 'fetch', async (_url, init) => {
    assert.equal(init.method, 'POST');
    assert.equal(init.body, 'false');
    return Response.json({ ok: true });
  });
  assert.deepEqual(await api('/example', { body: false }), { ok: true });
});

test('SSE handles fragmented frames, CRLF, JSON and text', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => streamResponse([
    'event: answer\r\ndata: {"text":', '"hello"}\r\n\r\n', 'data: plain text\n\n',
  ]));
  const events = [];
  await streamPost('/assistant/messages', {}, (event) => events.push(event));
  assert.deepEqual(events, [
    { event: 'answer', data: { text: 'hello' } },
    { event: 'message', data: 'plain text' },
  ]);
});

test('SSE callback errors propagate once and release the reader', async (t) => {
  const response = streamResponse(['data: {"ok":true}\n\n']);
  t.mock.method(globalThis, 'fetch', async () => response);
  let calls = 0;
  await assert.rejects(streamPost('/assistant/messages', {}, () => {
    calls++;
    throw new Error('consumer failed');
  }), /consumer failed/);
  assert.equal(calls, 1);
  assert.equal(response.body.locked, false);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { COOKIE_PREFERENCES_EVENT, requestCookiePreferences, consumeCookiePreferencesRequest } from '../lib/cookie-preferences.ts';

test('an early preferences click survives until the delayed dialog consumes it once', () => {
  const previous = globalThis.window;
  globalThis.window = new EventTarget();
  try {
    assert.equal(consumeCookiePreferencesRequest(), false);
    requestCookiePreferences();
    assert.equal(consumeCookiePreferencesRequest(), true);
    assert.equal(consumeCookiePreferencesRequest(), false);
  } finally { globalThis.window = previous; }
});

test('a mounted dialog handles the event immediately without leaving a stale request', () => {
  const previous = globalThis.window;
  globalThis.window = new EventTarget();
  try {
    let opens = 0;
    window.addEventListener(COOKIE_PREFERENCES_EVENT, () => {
      assert.equal(consumeCookiePreferencesRequest(), true);
      opens++;
    });
    requestCookiePreferences();
    requestCookiePreferences();
    assert.equal(opens, 2);
    assert.equal(consumeCookiePreferencesRequest(), false);
  } finally { globalThis.window = previous; }
});

test('server rendering cannot queue a browser preferences request', () => {
  const previous = globalThis.window;
  delete globalThis.window;
  try { requestCookiePreferences(); assert.equal(consumeCookiePreferencesRequest(), false); }
  finally { globalThis.window = previous; }
});

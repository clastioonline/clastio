import assert from 'node:assert/strict';
import { test } from 'node:test';
import { quotaAvailable } from '../lib/usage.ts';

test('spendable credits include grants and exclude queued reservations', () => {
  assert.equal(quotaAvailable({ used: 0, limit: 60, available: 80, reserved: 0 }), 80);
  assert.equal(quotaAvailable({ used: 0, limit: 60, available: 68, reserved: 12 }), 68);
  assert.equal(quotaAvailable({ used: 55, limit: 60, available: 0, reserved: 5 }), 0);
  assert.equal(quotaAvailable({ used: 0, limit: 0, available: 25 }), 25);
  assert.equal(quotaAvailable({ used: 10, limit: -1, available: null }), null);
  assert.equal(quotaAvailable({ used: 20, limit: 60 }), 40);
  assert.equal(quotaAvailable({ used: 70, limit: 60 }), 0);
});

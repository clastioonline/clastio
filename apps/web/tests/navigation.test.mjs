import assert from 'node:assert/strict';
import { test } from 'node:test';
import { adminLandingPath, safeInternalPath } from '../lib/navigation.ts';
test('sign-in redirects stay on this origin', () => {
  for (const value of ['//evil.example', '/\\evil.example', 'https://evil.example', 'javascript:alert(1)', '/\nevil.example', null]) {
    assert.equal(safeInternalPath(value, '/admin'), '/admin');
  }
  assert.equal(safeInternalPath('/lessons?tab=documents#latest'), '/lessons?tab=documents#latest');
});
test('staff landing pages respect permissions instead of forcing an analytics dashboard', () => {
  assert.equal(adminLandingPath(['analytics.view', 'users.view']), '/admin');
  assert.equal(adminLandingPath(['users.view', 'support.manage']), '/admin/users');
  assert.equal(adminLandingPath(['billing.view']), '/admin/billing');
  assert.equal(adminLandingPath(['support.manage']), '/admin/support');
  assert.equal(adminLandingPath([]), '/settings');
});

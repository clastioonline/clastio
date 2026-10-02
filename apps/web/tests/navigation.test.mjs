import assert from 'node:assert/strict';
import { test } from 'node:test';
import { safeInternalPath } from '../lib/navigation.ts';
test('sign-in redirects stay on this origin', () => {
  for (const value of ['//evil.example', '/\\evil.example', 'https://evil.example', 'javascript:alert(1)', '/\nevil.example', null]) {
    assert.equal(safeInternalPath(value, '/admin'), '/admin');
  }
  assert.equal(safeInternalPath('/lessons?tab=documents#latest'), '/lessons?tab=documents#latest');
});

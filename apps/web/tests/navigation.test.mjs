import assert from 'node:assert/strict';
import { test } from 'node:test';
import { adminLandingPath, safeInternalPath, safeSignInReturnPath, clerkCallbackPath, postSignInPath } from '../lib/navigation.ts';
test('sign-in redirects stay on this origin', () => {
  for (const value of ['//evil.example', '/\\evil.example', 'https://evil.example', 'javascript:alert(1)', '/\nevil.example', null]) {
    assert.equal(safeInternalPath(value, '/admin'), '/admin');
  }
  assert.equal(safeInternalPath('/lessons?tab=documents#latest'), '/lessons?tab=documents#latest');
});
test('gateway return parameters survive callback sign-in without granting access', () => {
  const destination = '/billing?status=success&session_id=synthetic-checkout#receipt';
  assert.equal(safeSignInReturnPath(destination), destination);
  const callback = new URL(clerkCallbackPath(destination), 'https://app.invalid');
  assert.equal(callback.pathname, '/auth/clerk');
  assert.equal(callback.searchParams.get('next'), destination);
  assert.equal(postSignInPath({ role: 'teacher', onboarding_completed: true }, destination), destination);
  assert.equal(postSignInPath({ role: 'teacher', onboarding_completed: false }, destination), '/onboarding');
  assert.equal(postSignInPath({ role: 'admin', permissions: ['billing.view'], onboarding_completed: true }, destination), '/admin/billing');
});
test('sign-in callbacks reject external destinations, raw APIs and authentication loops', () => {
  for (const value of ['https://outside.example', '//outside.example', '/\\outside.example', '/login?next=/billing', '/signup', '/auth/clerk', '/api/v1/me/export', '/session-expired', '/dashboard/../auth/clerk']) {
    assert.equal(safeSignInReturnPath(value), '/dashboard', value);
    const callback = new URL(clerkCallbackPath(value), 'https://app.invalid');
    assert.equal(callback.searchParams.get('next'), '/dashboard');
  }
  assert.equal(safeSignInReturnPath('/media?status=success'), '/media?status=success');
});
test('staff landing pages respect permissions instead of forcing an analytics dashboard', () => {
  assert.equal(adminLandingPath(['analytics.view', 'users.view']), '/admin');
  assert.equal(adminLandingPath(['users.view', 'support.manage']), '/admin/users');
  assert.equal(adminLandingPath(['billing.view']), '/admin/billing');
  assert.equal(adminLandingPath(['support.manage']), '/admin/support');
  assert.equal(adminLandingPath([]), '/settings');
});

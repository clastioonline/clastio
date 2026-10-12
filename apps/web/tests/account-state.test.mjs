import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';

// Resolve Next's extensionless import without changing or mirroring production logic.
const resolver = registerHooks({ resolve(specifier, context, nextResolve) {
  return nextResolve(specifier === './usage' && context.parentURL?.endsWith('/lib/account-state.ts') ? './usage.ts' : specifier, context);
} });
const { availableUsageResource, billingStateView, confirmedPaidAccess, safePaymentDestination } = await import('../lib/account-state.ts');
resolver.deregister();
const free = () => ({ plan: { code: 'free', name: 'Free' }, subscription: null, trial: null, pending_checkout: null, payments: [] });
const paid = () => ({ ...free(), plan: { code: 'pro', name: 'Pro' }, subscription: { status: 'active', provider: 'stripe', cancel_at_period_end: false, current_period_end: '2026-11-12T00:00:00Z' } });

test('only server-confirmed active online paid access establishes current paid access', () => {
  assert.equal(confirmedPaidAccess(paid()), true);
  assert.equal(confirmedPaidAccess({ ...paid(), subscription: { ...paid().subscription, provider: 'dodo' } }), true);
  for (const value of [free(), { ...free(), plan: paid().plan, trial: { active: true } },
    { ...paid(), subscription: { ...paid().subscription, provider: 'manual' } },
    { ...paid(), subscription: { ...paid().subscription, provider: 'unknown' } },
    { ...paid(), subscription: { ...paid().subscription, status: 'past_due' } },
    { ...paid(), plan: free().plan }, { ...paid(), pending_checkout: { status: 'processing' } }]) {
    assert.equal(confirmedPaidAccess(value), false);
    assert.equal(billingStateView('payment-success', value).title, 'Checking payment confirmation');
  }
});

test('a success query, fake checkout reference or paid label cannot certify payment', () => {
  const spoofed = { ...free(), status: 'paid', success: true, session_id: 'fake-checkout', verified: true };
  assert.equal(confirmedPaidAccess(spoofed), false);
  assert.equal(billingStateView('payment-success', spoofed).title, 'Checking payment confirmation');
  assert.equal(billingStateView('payment-failed', spoofed).title, 'Review your payment status');
  assert.equal(billingStateView('subscription-cancelled', { ...spoofed, cancelled: true }).title, 'Review cancellation status');
});

test('an existing active subscription describes current access without certifying this checkout', () => {
  const view = billingStateView('payment-success', paid());
  assert.equal(view.title, 'Your subscription is active');
  assert.match(view.description, /active Pro access/);
  assert.doesNotMatch(view.description, /payment (?:confirmed|successful)|checkout (?:paid|complete)/i);
  assert.equal(billingStateView('payment-failed', paid()).title, 'Your current subscription is active');
});

test('pending checkouts preserve current access and payment issues need server evidence', () => {
  const pending = { ...free(), pending_checkout: { status: 'open', id: 'current-checkout' } };
  assert.equal(billingStateView('checkout', pending).title, 'Resume your checkout');
  assert.equal(billingStateView('payment-failed', pending).title, 'Payment confirmation is pending');
  assert.equal(billingStateView('checkout', { ...pending, pending_checkout: { status: 'processing' } }).title, 'Payment confirmation is pending');
  for (const status of ['past_due', 'unpaid', 'incomplete']) assert.equal(billingStateView('payment-failed', { ...paid(), subscription: { ...paid().subscription, status } }).title, 'A payment needs attention');
  assert.equal(billingStateView('payment-failed', { ...free(), payments: [{ status: 'failed' }] }).title, 'A payment needs attention');
});

test('cancellation and trial states require server flags rather than local dates', () => {
  assert.equal(billingStateView('subscription-cancelled', { ...paid(), subscription: { ...paid().subscription, cancel_at_period_end: true } }).title, 'Cancellation is scheduled');
  assert.equal(billingStateView('subscription-cancelled', { ...paid(), subscription: { ...paid().subscription, status: 'canceled' } }).title, 'Your subscription is cancelled');
  assert.equal(billingStateView('subscription-expired', { ...paid(), subscription: { ...paid().subscription, current_period_end: '2001-01-01T00:00:00Z' } }).title, 'Current plan: Pro');
  assert.equal(billingStateView('trial-expired', free()).title, 'Check your trial status');
  assert.equal(billingStateView('trial-expired', { ...free(), trial: { ends_at: '2001-01-01T00:00:00Z' } }).title, 'Check your trial status');
  assert.equal(billingStateView('trial-expired', { ...free(), trial: { active: false, ended: true } }).title, 'Your trial has ended');
  assert.equal(billingStateView('trial-expired', { ...free(), trial: { active: true, ends_at: '2001-01-01T00:00:00Z' } }).title, 'Your trial is active');
});

test('allowances honor spendable grants and reservations instead of forcing an upgrade', () => {
  assert.equal(billingStateView('usage-limit', { ...free(), usage: { credits: { used: 55, limit: 60, available: 0, reserved: 5 } } }).title, 'Allowance is reserved for queued work');
  const grants = { ...free(), usage: { credits: { used: 0, limit: 0, available: 25 } } };
  assert.equal(billingStateView('upgrade-required', grants).title, 'Your allowance is available');
  assert.match(billingStateView('usage-limit', grants).description, /25 available/);
  assert.equal(billingStateView('usage-limit', { ...free(), usage: { credits: { used: 60, limit: 60, available: 0 } } }).title, 'This allowance is currently unavailable');
  assert.equal(billingStateView('usage-limit', free()).title, 'Check your plan allowance');
  assert.match(billingStateView('usage-limit', { ...free(), usage: { credits: { used: 0, limit: -1, available: null } } }).description, /unlimited/);
  assert.equal(availableUsageResource('not-an-allowance'), 'credits');
  assert.equal(availableUsageResource('storage_mb'), 'storage_mb');
});

test('payment redirects accept HTTPS custom providers and same-origin paths', () => {
  const origin = 'http://localhost:3005';
  assert.equal(safePaymentDestination('https://custom.checkout.example/pay?return=app', origin), 'https://custom.checkout.example/pay?return=app');
  assert.equal(safePaymentDestination('/billing?status=pending', origin), origin + '/billing?status=pending');
  assert.equal(safePaymentDestination(origin + '/billing', origin), origin + '/billing');
});

test('unsafe, credential-bearing or malformed payment redirects are rejected', () => {
  for (const value of ['', '   ', 'javascript:alert(1)', 'data:text/html,paid', 'file:///tmp/checkout', 'http://outside.example/pay', '//outside.example/pay', 'https://user:password@example.com/pay', 'https://example.com/\ncheckout', 'https://example.com/\rcheckout', 'https://example.com/\tcheckout', 'https://example.com/\u007fcheckout', '/\\outside.example/pay', 'https:\\outside.example/pay']) {
    assert.equal(safePaymentDestination(value, 'http://localhost:3005'), null, JSON.stringify(value));
  }
});

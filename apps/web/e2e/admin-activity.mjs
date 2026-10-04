import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

// All account, task and staff data are mocked. This must never exercise real accounts.
const base = process.env.BASE_URL || 'http://localhost:3100';
assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname), 'Use a localhost frontend for the admin activity regression.');
const browser = await launchBrowser();
const errors = [];
const now = new Date().toISOString();
const oldTasks = ['Pre-promotion lesson', 'Pre-promotion worksheet'].map((title, index) => ({
  id: `teacher-task-${index}`, type: 'lesson', label: 'Your lesson', title,
  href: `/lessons/old-${index}`, status: 'running', progress: 35, stage: 'Preparing slides',
  error: null, created_at: now, completed_at: null,
}));
const operational = ['/admin/audit', '/admin/system', '/admin/security', '/admin/billing', '/admin/support'];
const teacherLinks = ['/projects/new', '/lessons', '/assistant'];

async function fixture({ role = 'teacher', permissions = [] } = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const state = { role, permissions, tasks: oldTasks, auditFailure: false, auditAction: 'subscription.credit_grant', requests: [], profileSaves: 0, holdActivity: false };
  let release, started;
  state.heldStarted = new Promise(resolve => { started = resolve; });
  const held = new Promise(resolve => { release = resolve; });
  state.releaseActivity = release;
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await context.addInitScript(() => {
    localStorage.setItem('clastio:cookie-consent', JSON.stringify({ essential: true, analytics: false, marketing: false }));
    window.activityRegressionDocument = Math.random();
  });
  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    state.requests.push({ path, query: url.searchParams.toString(), method: request.method(), role: state.role });
    let data = { items: [], unread: 0, total: 0, active_count: 0 };
    if (path === '/auth/me') data = { user: {
      id: 'same-promoted-account', name: 'Activity Review', email: 'activity@example.com', role: state.role,
      permissions: state.permissions, admin_role: state.role === 'admin' ? 'super_admin' : null,
      admin_role_label: state.role === 'admin' ? 'Review staff' : null, status: 'active',
      email_verified: true, onboarding_completed: true, locale: 'en', timezone: 'Asia/Dubai',
    }, pending_legal: [] };
    if (path === '/activity') {
      if (state.holdActivity) {
        started();
        await held;
        data = { items: oldTasks.map(task => ({ ...task, status: 'succeeded', progress: 100, completed_at: now })), active_count: 0 };
      } else data = { items: state.tasks, active_count: state.tasks.filter(task => ['queued', 'running'].includes(task.status)).length };
    }
    if (path === '/me/profile') {
      if (request.method() === 'PUT') {
        state.profileSaves++;
        state.role = 'admin';
        state.permissions = ['audit.view', 'system.logs.view', 'security.view', 'billing.view', 'support.manage'];
        state.holdActivity = true;
      }
      data = { name: 'Activity Review', email: 'activity@example.com', school_name: 'Review School',
        curriculum: 'cbse', timezone: 'Asia/Dubai', class_duration_minutes: 40, subjects: ['Science'],
        grades: ['5'], working_days: [0, 1, 2, 3, 4], teaching_style: '', metadata_policy: {} };
    }
    if (path === '/me/consents') data = { consents: {}, marketing: { marketing_email: false, marketing_whatsapp: false } };
    if (path === '/me/usage' || path === '/billing/subscription') data = { plan: { code: 'free', name: 'Free' }, subscription: null, trial: null,
      usage: { credits: { used: 0, limit: 30, available: 30, reserved: 0 } }, trial_available: false };
    if (path === '/admin/system/health') data = { ready: { checks: { ai: { mode: 'live' } } } };
    if (path === '/admin/audit-logs') {
      assert.equal(url.searchParams.get('actor_id'), 'same-promoted-account', 'Staff activity must request only the signed-in actor.');
      assert.equal(url.searchParams.get('limit'), '20');
      assert.equal(url.searchParams.get('days'), '90');
      if (state.auditFailure) return route.fulfill({ status: 503, json: { error: { message: 'Audit temporarily unavailable' } } });
      data = { items: [{ id: 'own-staff-action', action: state.auditAction, target_email: 'teacher@example.com',
        target_type: 'user', reason: 'Requested credit adjustment', created_at: now }] };
    }
    await route.fulfill({ status: 200, json: data });
  });
  return { context, page, state };
}

async function noTeacherActions(page) {
  for (const href of teacherLinks) assert.equal(await page.locator(`a[href="${href}"]`).count(), 0, `Staff activity must not offer ${href}.`);
  assert.equal(await page.getByText('Create lessons', { exact: true }).count(), 0);
  assert.equal(await page.getByText('Create a worksheet', { exact: true }).count(), 0);
  assert.equal(await page.getByText('Explore an idea', { exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: /^Open activity/ }).count(), 0, 'The teacher activity modal trigger is absent for staff.');
  assert.equal(await page.getByRole('dialog', { name: 'Your activity' }).count(), 0);
  assert.equal(await page.getByText('Pre-promotion lesson', { exact: false }).count(), 0);
  assert.equal(await page.getByText('Pre-promotion worksheet', { exact: false }).count(), 0);
  assert.equal(await page.getByRole('link', { name: 'Open admin activity', exact: true }).locator('span').count(), 1, 'The admin activity link has its label and no teacher task badge.');
}

try {
  const { context, page, state } = await fixture();
  await page.goto(`${base}/activity`);
  await page.getByRole('button', { name: 'Open activity, 2 in progress', exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Pre-promotion lesson', exact: true }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'Build a lesson', exact: false }).getAttribute('href'), '/projects/new');
  await page.getByRole('button', { name: 'Open activity, 2 in progress', exact: true }).click();
  await page.getByRole('dialog', { name: 'Your activity' }).waitFor();
  await page.getByRole('button', { name: 'Keep exploring', exact: true }).click();
  state.tasks = [];
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('heading', { name: 'A little room for your next idea', exact: true }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'Create lessons', exact: true }).getAttribute('href'), '/projects/new', 'The teacher empty feed retains its lesson CTA.');
  state.tasks = oldTasks;
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('button', { name: 'Open activity, 2 in progress', exact: true }).waitFor();
  const documentMarker = await page.evaluate(() => window.activityRegressionDocument);
  await page.getByRole('link', { name: 'Settings', exact: true }).first().click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.getByRole('link', { name: 'Open admin activity', exact: true }).waitFor();
  assert.equal(state.profileSaves, 1);
  assert.equal(await page.evaluate(() => window.activityRegressionDocument), documentMarker, 'Promotion is observed in the same client document, with the existing activity cache.');
  await Promise.race([state.heldStarted, new Promise((_, reject) => setTimeout(() => reject(new Error('No delayed teacher request was issued during promotion.')), 5000))]);
  state.auditFailure = true;
  await page.getByRole('link', { name: 'Open admin activity', exact: true }).click();
  await page.getByRole('heading', { name: 'Admin activity', exact: true }).waitFor();
  state.releaseActivity();
  await page.getByRole('alert').filter({ hasText: 'your staff activity' }).waitFor();
  await noTeacherActions(page);
  const requestsAfterPromotion = state.requests.filter(request => request.path === '/activity').length;
  await page.evaluate(() => window.dispatchEvent(new Event('clastio:work-started')));
  await page.waitForTimeout(3200); // Longer than the old running-feed polling interval.
  assert.equal(state.requests.filter(request => request.path === '/activity').length, requestsAfterPromotion, 'Teacher work events and polling stop after promotion.');
  await noTeacherActions(page);
  for (const href of operational) assert.ok(await page.locator(`main a[href="${href}"]`).count(), `An allowed operational link is present: ${href}`);
  state.auditFailure = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await page.getByRole('cell', { name: 'subscription credit grant', exact: true }).waitFor();
  await page.getByRole('cell', { name: 'teacher@example.com', exact: true }).waitFor();
  assert.equal(await page.getByRole('alert').filter({ hasText: 'your staff activity' }).count(), 0);
  state.auditAction = 'support.ticket_reply';
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('cell', { name: 'support ticket reply', exact: true }).waitFor();
  await noTeacherActions(page);
  await context.close();

  for (const [permission, allowed] of [['billing.view', '/admin/billing'], ['support.manage', '/admin/support']]) {
    const limited = await fixture({ role: 'admin', permissions: [permission] });
    await limited.page.goto(`${base}/activity`);
    await limited.page.getByRole('heading', { name: 'Admin activity', exact: true }).waitFor();
    await limited.page.getByText('The audit log is available to staff with audit access.', { exact: false }).waitFor();
    assert.equal(limited.state.requests.filter(request => request.path === '/admin/audit-logs').length, 0, `${permission} does not fetch restricted audit data.`);
    assert.equal(limited.state.requests.filter(request => request.path === '/activity').length, 0, `${permission} does not fetch personal teacher tasks.`);
    assert.equal(limited.state.requests.filter(request => request.path === '/admin/system/health').length, 0, `${permission} does not fetch restricted system health.`);
    for (const href of operational) assert.equal(await limited.page.locator(`main a[href="${href}"]`).count(), href === allowed ? 1 : 0, `${permission} receives only permitted activity links.`);
    assert.equal(await limited.page.getByRole('button', { name: 'Refresh', exact: true }).count(), 0);
    await noTeacherActions(limited.page);
    await limited.context.close();
  }
  assert.deepEqual(errors, [], 'No client exceptions occurred.');
  console.log('Admin activity regression passed: teacher feed and empty CTA, same-document promotion with delayed task completion, cleared task count/modal/toasts, own staff audit and retry/refresh, and restricted billing/support links and requests.');
} finally { await browser.close(); }

import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

const base = process.env.BASE_URL || 'http://localhost:3101';
assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname), 'Run this mocked regression on localhost only.');
const browser = await launchBrowser();
const errors = [];
const state = { enabled: false, tasks: [], submissions: [], earned: 0, requests: [] };
const now = new Date().toISOString();
const program = () => ({ enabled: state.enabled, daily_credits: 20, monthly_credits: 60, lifetime_credits: 200, global_daily_credits: 500 });

async function fixture(role = 'teacher', permissions = [], paid = false, viewport = { width: 1440, height: 1000 }) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript(() => localStorage.setItem('clastio:cookie-consent', '{}'));
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/api/v1/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1', '');
    const body = request.method() === 'GET' ? null : request.postDataJSON();
    state.requests.push({ role, permissions, path, method: request.method(), body });
    let data = { items: [], unread: 0, total: 0, active_count: 0 };
    if (path === '/auth/me') data = { user: { id: role, name: 'Reward Review', email: 'review@example.com', role,
      permissions, status: 'active', email_verified: true, onboarding_completed: true, timezone: 'Asia/Dubai', locale: 'en',
      admin_role_label: role === 'admin' ? 'Review staff' : null }, pending_legal: [] };
    if (path === '/me/usage') data = { plan: { code: paid ? 'pro' : 'free', name: paid ? 'Teacher Pro' : 'Free' },
      subscription: null, trial: null, usage: { credits: { used: 0, limit: 60, available: 60 + state.earned, reserved: 0 } } };
    if (path === '/admin/rewards/program' && body) state.enabled = body.enabled;
    if (path === '/admin/rewards/tasks' && body) { state.tasks.push({ ...body, id: 'task-1' }); data = state.tasks.at(-1); }
    if (path === '/admin/rewards/tasks/task-1' && body) { state.tasks[0] = { ...body, id: 'task-1' }; data = state.tasks[0]; }
    if (path === '/rewards/tasks/task-1/submit' && body) {
      data = { id: 'submission-1', task_id: 'task-1', credits: 5, status: 'pending', submitted_at: now, reviewed_at: null, expires_at: null,
        user_id: 'teacher', email: 'review@example.com', proof: body.proof, task_title: state.tasks[0].title };
      state.submissions.push(data);
    }
    if (path === '/admin/rewards/submissions/submission-1/review' && body) {
      state.submissions[0] = { ...state.submissions[0], status: body.approve ? 'approved' : 'rejected', review_note: body.note, reviewed_at: now, expires_at: '2099-01-01T00:00:00Z' };
      if (body.approve) state.earned += 5;
      data = state.submissions[0];
    }
    if (path === '/admin/rewards') data = { program: program(), tasks: state.tasks, submissions: state.submissions.filter(row => row.status === 'pending') };
    if (path === '/rewards') data = { enabled: state.enabled, eligible: !paid, ineligible_reason: paid ? 'Rewards are available after your trial ends, while you use the Free plan.' : null,
      limits: program(), earned_this_month: state.earned, expires_at: '2099-01-01T00:00:00Z',
      tasks: state.enabled ? state.tasks.filter(row => row.published) : [], submissions: state.submissions };
    await route.fulfill({ status: 200, json: data });
  });
  return { context, page };
}

try {
  const mobile = await fixture('teacher', [], false, { width: 390, height: 844 });
  await mobile.page.goto(`${base}/rewards`);
  await mobile.page.getByRole('heading', { name: 'Earn lesson credits', exact: true }).waitFor();
  await mobile.page.getByRole('heading', { name: 'Tasks are coming soon', exact: true }).waitFor();
  assert.equal(await mobile.page.getByRole('button', { name: 'Complete task', exact: true }).count(), 0);
  assert.ok(await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile empty rewards page does not overflow.');

  const staff = await fixture('admin', ['billing.view', 'billing.modify', 'users.manage']);
  await staff.page.goto(`${base}/admin/rewards`);
  await staff.page.getByRole('heading', { name: 'Free-plan credit tasks', exact: true }).waitFor();
  await staff.page.getByRole('button', { name: 'Add task', exact: true }).click();
  const dialog = staff.page.getByRole('dialog', { name: 'Add credit task', exact: true });
  await dialog.getByLabel('Task title', { exact: true }).fill('Review lesson quality');
  await dialog.getByLabel('Instructions and evidence required', { exact: true }).fill('Describe confusing teaching examples and suggest a clearer classroom explanation.');
  const save = dialog.getByRole('button', { name: 'Save task', exact: true });
  assert.equal(await save.isDisabled(), true, 'Task policy acknowledgement is required.');
  await dialog.getByRole('checkbox', { name: 'Publish task', exact: true }).check();
  await dialog.getByRole('checkbox', { name: /This task asks for useful work/ }).check();
  await save.click();
  await staff.page.getByText('Task saved', { exact: true }).waitFor();
  await staff.page.getByRole('checkbox', { name: 'Enable published tasks', exact: true }).check();
  await staff.page.getByLabel('Reason for changing the program', { exact: true }).fill('Launch reviewed quality feedback tasks');
  await staff.page.getByRole('button', { name: 'Save program', exact: true }).click();
  await staff.page.getByText('Program saved', { exact: true }).waitFor();

  await mobile.page.reload();
  await mobile.page.getByRole('button', { name: 'Complete task', exact: true }).click();
  const taskDialog = mobile.page.getByRole('dialog', { name: 'Review lesson quality', exact: true });
  const submit = taskDialog.getByRole('button', { name: 'Submit for review', exact: true });
  assert.equal(await submit.isDisabled(), true);
  await taskDialog.getByLabel(/Describe your completed work/).fill('I reviewed the water cycle example and suggest showing condensation before the quiz.');
  await submit.click();
  await mobile.page.getByText('Submitted for review', { exact: true }).waitFor();
  assert.equal(await mobile.page.getByRole('button', { name: 'Awaiting review', exact: true }).isDisabled(), true);
  assert.equal(state.earned, 0, 'Submission alone does not award credits.');
  assert.ok(await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile task page does not overflow.');

  await staff.page.reload();
  await staff.page.getByRole('button', { name: 'Review proof', exact: true }).click();
  const review = staff.page.getByRole('dialog', { name: 'Review task evidence', exact: true });
  await review.getByText(/I reviewed the water cycle example/).waitFor();
  await review.getByLabel('Review note', { exact: true }).fill('Verified useful classroom quality feedback');
  await review.getByRole('button', { name: 'Approve 5 credits', exact: true }).click();
  await staff.page.getByText('Reward approved', { exact: true }).waitFor();
  await mobile.page.reload();
  await mobile.page.getByText('approved · 5 credits', { exact: true }).waitFor();
  assert.equal(state.earned, 5);
  assert.equal(await mobile.page.getByRole('button', { name: 'Reward approved', exact: true }).isDisabled(), true);

  const readOnly = await fixture('admin', ['billing.view']);
  await readOnly.page.goto(`${base}/admin/rewards`);
  await readOnly.page.getByRole('heading', { name: 'Free-plan credit tasks', exact: true }).waitFor();
  for (const name of ['Add task', 'Edit', 'Save program', 'Review proof']) assert.equal(await readOnly.page.getByRole('button', { name, exact: true }).count(), 0, `Read-only staff cannot ${name}.`);
  assert.equal(await readOnly.page.getByRole('checkbox', { name: 'Enable published tasks', exact: true }).isDisabled(), true);
  const paid = await fixture('teacher', [], true);
  await paid.page.goto(`${base}/rewards`);
  await paid.page.getByText('Rewards are available after your trial ends, while you use the Free plan.', { exact: false }).waitFor();
  assert.equal(await paid.page.getByRole('button', { name: 'Complete task', exact: true }).count(), 0);
  assert.equal(await paid.page.getByRole('link', { name: 'Earn credits', exact: true }).count(), 0, 'Paid teacher navigation has no Free reward link.');
  assert.deepEqual(errors, [], 'No client exceptions.');
  console.log('Free rewards browser regression passed: empty default, policy-confirmed admin task/program setup, mobile proof submission with no immediate credit, manual approval and balance state, paid/read-only eligibility and responsive layouts.');
} finally { await browser.close(); }

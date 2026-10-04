import assert from 'node:assert/strict';

// Seeded demo credentials and verification fixtures are only for an isolated local stack.
export function assertLocalTestBase(base) {
  const host = new URL(base).hostname;
  assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(host), 'Demo fixtures are restricted to an isolated localhost test stack.');
}

export async function verifyTestTeacher(browser, teacherContext, base) {
  assertLocalTestBase(base);
  const meResponse = await teacherContext.request.get(`${base}/api/v1/auth/me`);
  assert.equal(meResponse.status(), 200, 'New teacher session must be authenticated before preparing a fixture.');
  const { user } = await meResponse.json();
  assert.equal(user.role, 'teacher');
  assert.ok(user.email.endsWith('@example.com'), 'Only the generated example.com test teacher may be verified.');
  const staffContext = await browser.newContext();
  try {
    const login = await staffContext.request.post(`${base}/api/v1/auth/login`, {
      data: { email: 'admin@example.com', password: 'admin-demo-123' },
    });
    assert.equal(login.status(), 200, 'The isolated stack must be seeded with its demo administrator.');
    const verification = await staffContext.request.post(`${base}/api/v1/admin/users/${user.id}/verification`, {
      data: { action: 'mark_verified', reason: 'Isolated local browser test fixture' },
    });
    assert.equal(verification.status(), 200, await verification.text());
    assert.equal((await verification.json()).email_verified, true);
  } finally { await staffContext.close(); }
}

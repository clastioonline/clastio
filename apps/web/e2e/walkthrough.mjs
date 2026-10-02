import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
const base = process.env.BASE_URL || 'http://localhost:3000';
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
try {
  for (const role of ['teacher', 'admin']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 900 } });
    const page = await context.newPage();
    const login = await context.request.post(`${base}/api/v1/auth/login`, { data: { email: role === 'teacher' ? 'sara@example.com' : 'admin@example.com', password: role === 'teacher' ? 'teacher-demo-123' : 'admin-demo-123' } });
    assert.equal(login.status(), 200, await login.text());
    await page.goto(`${base}/${role === 'teacher' ? 'projects/new' : 'admin'}`);
    const cookies = page.getByRole('button', { name: 'Essential only' });
    await cookies.waitFor({ timeout: 15000 });
    await cookies.click();
    await page.getByRole('button', { name: 'Walkthrough', exact: true }).click();
    await page.getByRole('button', { name: 'Guide this page', exact: true }).click();
    await page.getByText(/Step 1 of/).waitFor();
    await page.getByRole('button', { name: 'Pause tour', exact: true }).click();
    await page.reload();
    await page.getByRole('button', { name: 'Walkthrough', exact: true }).click();
    await page.getByRole('button', { name: 'Resume walkthrough', exact: true }).click();
    await page.getByText(/Step 1 of/).waitFor();
    await page.keyboard.press('Escape');
    let writes = 0;
    page.on('request', req => { if (req.method() === 'POST' && /\/(courses|generate|chat|messages|media)(\?|$)/.test(req.url())) writes++; });
    await page.getByRole('button', { name: 'Walkthrough', exact: true }).click();
    await page.getByRole('button', { name: 'Tour the complete app', exact: true }).click();
    const total = role === 'teacher' ? 18 : 9;
    for (let step = 1; step <= total; step++) {
      await page.getByText(`Step ${step} of ${total}`, { exact: true }).waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${role} step ${step} fits mobile`);
      await page.getByRole('button', { name: step === total ? 'Finish walkthrough' : 'Next step', exact: true }).click();
    }
    assert.equal(writes, 0);
    await page.getByRole('button', { name: 'Walkthrough', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Resume walkthrough', exact: true }).count(), 0);
    await context.close();
    console.log(`${role}: mobile page guide, pause/resume, full tour, read-only behavior passed`);
  }
} finally { await browser.close(); }

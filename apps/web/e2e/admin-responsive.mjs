import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const base = process.env.BASE_URL || 'http://localhost:3000';
const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const context = await browser.newContext();
const page = await context.newPage();
fs.mkdirSync('e2e/screenshots', { recursive: true });
try {
  const login = await context.request.post(`${base}/api/v1/auth/login`, { data: { email: 'admin@example.com', password: 'admin-demo-123' } });
  assert.equal(login.status(), 200, await login.text());
  const failures = [];
  for (const width of [320, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['', '/users', '/plans', '/billing', '/api-usage', '/ai-costs', '/media', '/staff', '/support', '/announcements', '/security', '/audit', '/system', '/settings', '/legal']) {
      await page.goto(`${base}/admin${path}`);
      await page.locator('main h1').first().waitFor();
      await page.waitForTimeout(350);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (overflow > 1) {
        failures.push(`${path || '/admin'} at ${width}: ${overflow}px`);
        await page.screenshot({ path: `e2e/screenshots/admin-overflow-${path.replaceAll('/', '') || 'home'}-${width}.png`, fullPage: true });
      }
    }
  }
  assert.deepEqual(failures, []);
  console.log('✓ Admin pages fit phone, tablet and small desktop viewports.');
} finally { await browser.close(); }

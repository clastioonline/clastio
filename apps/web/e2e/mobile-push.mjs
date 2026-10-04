import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { launchBrowser } from './browser.mjs';

// All identity/enrollment/provider APIs are mocked. No push messages or subscription service calls are sent.
const base = process.env.BASE_URL || 'http://localhost:3101';
const browser = await launchBrowser();
const endpoint = 'https://fcm.googleapis.com/fcm/send/browser-fixture';
const endpointHash = createHash('sha256').update(endpoint).digest('hex');
const publicKey = Buffer.concat([Buffer.from([4]), Buffer.alloc(64, 1)]).toString('base64url');
const errors = [];
let devices = [], enrollmentRequests = 0, consentChanges = 0, configured = true;
let debugPage;
let categories = [
  { category: 'product', label: 'PPT and lesson completion updates', mandatory: false, in_app: true, email: false, push: true },
  { category: 'security', label: 'Sign-ins and account security', mandatory: true, in_app: true, email: true, push: true },
  { category: 'announcement', label: 'Product news and maintenance notices', mandatory: false, in_app: true, email: true, push: false },
];

async function fixture(context) {
  await context.addInitScript(({ endpoint, publicKey }) => {
    const state = { subscribed: false, subscribeCalls: 0, installCalls: 0 };
    window.__pushFixture = state;
    const subscription = { endpoint, toJSON: () => ({ endpoint, keys: { p256dh: publicKey, auth: 'YXV0aC1maXh0dXJlLW9ubHk' } }),
      unsubscribe: async () => { state.subscribed = false; return true; } };
    const registration = { pushManager: { getSubscription: async () => state.subscribed ? subscription : null,
      subscribe: async () => { state.subscribeCalls++; state.subscribed = true; return subscription; } } };
    Object.defineProperty(navigator, 'serviceWorker', { value: { register: async () => registration, ready: Promise.resolve(registration), controller: { postMessage: () => {} } } });
    Object.defineProperty(Notification, 'permission', { get: () => 'granted', configurable: true });
    localStorage.setItem('clastio:cookie-consent', 'essential');
  }, { endpoint, publicKey });
  await context.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    const method = route.request().method();
    let data = { items: [], unread: 0, active_count: 0, total: 0 };
    if (path === '/auth/me') data = { user: { id: 'push-teacher', role: 'teacher', name: 'Push Teacher', email: 'push@example.com', permissions: [], status: 'active', email_verified: true, onboarding_completed: true, locale: 'en', timezone: 'Asia/Dubai' }, pending_legal: [] };
    if (path === '/me/profile') data = { name: 'Push Teacher', email: 'push@example.com', school_name: 'Example school', curriculum: 'cbse', subjects: ['Maths'], grades: ['5'], working_days: [0, 1, 2, 3, 4], class_duration_minutes: 45, timezone: 'Asia/Dubai' };
    if (path === '/me/usage') data = { plan: { code: 'free', name: 'Free' }, usage: { credits: { used: 0, limit: 30, available: 30 } } };
    if (path === '/me/consents') data = { consents: {}, marketing: { marketing_email: false, marketing_whatsapp: false } };
    if (path === '/me/notification-preferences') {
      if (method === 'PUT') {
        for (const [category, changes] of Object.entries(route.request().postDataJSON().categories)) categories = categories.map(item => item.category === category ? { ...item, ...changes } : item);
      }
      data = { items: categories };
    }
    if (path === '/me/push') data = { configured, public_key: configured ? publicKey : null, items: devices };
    if (path === '/me/push/subscriptions' && method === 'POST') {
      enrollmentRequests++;
      const payload = route.request().postDataJSON();
      assert.equal(payload.endpoint, endpoint);
      assert.equal(payload.marketing_enabled, false, 'product news is not preselected');
      devices = [{ id: 'device-one', endpoint_hash: endpointHash, device_name: payload.device_name, marketing_enabled: false, consent_at: new Date().toISOString(), active: true }];
      data = { id: 'device-one', enabled: true };
    }
    if (path === '/me/push/subscriptions/device-one') {
      if (method === 'PATCH') { consentChanges++; devices[0].marketing_enabled = route.request().postDataJSON().marketing_enabled; }
      if (method === 'DELETE') devices = [];
      data = { removed: true, updated: true };
    }
    await route.fulfill({ status: 200, json: data });
  });
}

try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await fixture(context);
  const page = await context.newPage();
  debugPage = page;
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') console.error('Browser console:', message.text()); });
  await page.goto(`${base}/settings`);
  await page.getByText('Clastio on your phone', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Enable on this device', exact: true }).waitFor();
  assert.equal(enrollmentRequests, 0, 'loading settings cannot enroll a browser or request permission');
  assert.equal(await page.evaluate(() => window.__pushFixture.subscribeCalls), 0);
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    event.prompt = async () => { window.__pushFixture.installCalls++; window.dispatchEvent(new Event('appinstalled')); };
    event.userChoice = Promise.resolve({ outcome: 'accepted' });
    window.dispatchEvent(event);
  });
  await page.getByRole('button', { name: 'Install Clastio', exact: true }).click();
  await page.getByText('Clastio is installed on this device.', { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => window.__pushFixture.installCalls), 1);
  await page.getByRole('button', { name: 'Enable on this device', exact: true }).click();
  await page.getByRole('button', { name: 'Turn off on this device', exact: true }).waitFor();
  assert.equal(enrollmentRequests, 1);
  assert.equal(await page.evaluate(() => window.__pushFixture.subscribeCalls), 1);
  await page.getByRole('switch', { name: 'Product news on this device (optional)', exact: false }).click();
  await page.waitForFunction(() => document.querySelector('#device-notifications [role=switch]')?.getAttribute('aria-checked') === 'true');
  assert.equal(consentChanges, 1);
  assert.equal(await page.getByLabel('Sign-ins and account security: email', { exact: true }).isDisabled(), true);
  assert.equal(await page.getByLabel('Sign-ins and account security: push', { exact: true }).isDisabled(), false);
  await page.getByLabel('Sign-ins and account security: push', { exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('input[aria-label="Sign-ins and account security: push"]')?.checked);
  await page.getByRole('button', { name: 'Turn off on this device', exact: true }).click();
  await page.getByRole('button', { name: 'Enable on this device', exact: true }).waitFor();
  assert.equal(devices.length, 0);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, '390px settings does not overflow');
  configured = false;
  await page.reload();
  await page.getByText('Device notifications are not available yet. Your in-app and email settings still work.', { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Enable on this device', exact: true }).count(), 0);

  configured = true;
  const ios = await browser.newContext({ viewport: { width: 390, height: 844 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1' });
  await fixture(ios);
  const iphone = await ios.newPage();
  iphone.on('pageerror', error => errors.push(error.message));
  await iphone.goto(`${base}/settings`);
  await iphone.getByText('On iPhone or iPad, open the browser Share menu, choose Add to Home Screen, then open Clastio using the new icon.', { exact: true }).waitFor();
  await iphone.getByText('Add Clastio to your Home Screen and open the installed app before enabling notifications.', { exact: false }).waitFor();
  assert.equal(await iphone.getByRole('button', { name: 'Enable on this device', exact: true }).count(), 0);
  const manifestResponse = await page.request.get(`${base}/manifest.webmanifest`);
  assert.equal(manifestResponse.status(), 200);
  const manifest = await manifestResponse.json();
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.scope, '/');
  assert.ok(manifest.icons.some(icon => icon.sizes === '192x192'));
  assert.ok(manifest.icons.some(icon => icon.sizes === '512x512'));
  assert.deepEqual(errors, []);
  console.log('Mobile installation and push opt-in browser journey passed (no real subscriptions or deliveries).');
} catch (error) {
  console.error('Mocked mobile test diagnostics:', errors, await debugPage?.locator('body').innerText());
  throw error;
} finally { await browser.close(); }

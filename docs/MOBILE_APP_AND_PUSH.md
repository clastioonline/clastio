# Install Clastio and enable device notifications

Clastio now includes an installable Progressive Web App (PWA). In **Settings → Clastio on your phone**, Chrome on Android and desktop can offer **Install Clastio** when the browser's install criteria are met. The browser's **Install app / Add to Home Screen** menu remains a fallback. On iPhone/iPad, use the browser Share menu, choose **Add to Home Screen**, and launch the new icon. Web Push on iOS/iPadOS requires a Home Screen app and version 16.4 or later. See the [WebKit implementation requirements](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/) and [Chrome installation prompt guidance](https://web.dev/learn/pwa/installation-prompt).

The app requires an internet connection for signed-in pages, teacher files, lessons and generation. Its service worker caches only the two fixed public brand icons, with cookies omitted from preload requests. It never caches authenticated HTML, API responses, uploaded material, generated PPTs or signed download URLs.

## Enable push on Railway

1. Deploy the API migrations, including `f206push01`, and the Render frontend containing `/manifest.webmanifest` and `/sw.js`. Apply the newest migration if later features have extended the migration chain.
2. Generate a VAPID key pair locally, in the API environment:

   ```sh
   cd apps/api
   python -m app.services.push_keys --output /private/tmp/clastio-web-push.env --subject mailto:notifications@clastio.online
   ```

   Use the activated virtual environment or its Python executable. The command creates a new file with owner-only permissions, refuses to overwrite files, and prints no keys. Use an operating-system temporary directory appropriate to your deployment workstation. Keep the file out of source control and delete it after securely storing the values in your provider's environment settings.
3. Copy all three variables from that file to **both the Railway API service and the dedicated scheduler service**:

   ```dotenv
   WEB_PUSH_PUBLIC_KEY=YOUR_GENERATED_PUBLIC_KEY
   WEB_PUSH_PRIVATE_KEY=YOUR_GENERATED_PRIVATE_KEY
   WEB_PUSH_SUBJECT=mailto:notifications@clastio.online
   ```

   Render does not need these environment variables: the authenticated `/api/v1/me/push` response supplies only the public key. The private key must remain on the backend. Keep the same pair across deployments; changing it requires existing devices to unsubscribe and enroll again.
4. Redeploy the API and scheduler. Run one dedicated scheduler using:

   ```sh
   python -m app.worker --scheduler-only
   ```

   This drains push and email outboxes every minute. Generation workers can use `--no-scheduler` to avoid duplicate scheduling work.
5. Sign in on your own test account, open **Settings → Device notifications**, press **Enable on this device**, and accept the browser permission prompt. The app requests permission only after that button press. Load-time registration does not request notification permission or enroll the browser.
6. Generate a test PPT and verify the device notification opens the correct lesson. Test a payment/trial reminder only using a fixture/test account. Check a second device separately; enabling one browser does not enroll other devices. Finally, turn the device off and verify it stops receiving notifications.

No push delivery has been performed against production as part of development. Blank, malformed, or mismatched VAPID settings leave push unavailable with clear UI text. Existing in-app and email delivery still operate. Queued push waits without consuming attempts when provider configuration is missing; messages older than 24 hours are suppressed.

## Consent, retries and account changes

- **Notifications → Push** chooses categories independently from in-app and email delivery. Push can be turned off even for categories whose required in-app/security emails remain on.
- Product news starts off. It needs both the category's Push checkbox and the device's separate **Product news on this device** consent. Transactional lesson-ready messages and reminders require device enrollment and their category preference.
- Signing out, revoking the app session, disabling categories, removing a device, or deactivating/deleting the account suppresses queued notifications. Ordinary expiry of an app sign-in token does not withdraw the device's notification consent: reminders can still arrive while the user is away. After explicit sign-out, sign in and opt in again to resume device delivery.
- A browser switching to another account enrolls only through an explicit button press; enrollment removes the old account's queued payloads. Promoted admins do not receive old teacher-generation, usage or review pushes.
- Delivery rechecks account state, explicit session revocation, category choices and per-device product-news consent. Browser endpoints returning HTTP 404/410 are removed. Temporary failures retry with exponential backoff and stop after five attempts. Other permanent errors stop immediately.
- The database outbox deduplicates each event per device. Delivery is at least once across a process crash: a stable provider Topic and notification tag replace repeated visible notifications. Completed/suppressed outbox records are removed after 30 days.
- The backend only accepts known Chrome/Firefox/Apple/Windows push-service origins and expected URL paths, checks all DNS results are public, pins the validated IP with the correct Host/TLS SNI, disables environment proxies and never follows redirects. It stores only sanitized failure classes/HTTP status codes, never provider response bodies or endpoint/key-bearing exception text.

Push delivery remains subject to device/browser notification permissions, operating-system Focus settings and connectivity. These are not guaranteed-delivery messages; the durable in-app notification and configured email channel remain available.

## Verification included in the codebase

`apps/api/unit_tests/test_web_push.py` checks origin restrictions, IP pinning, real payload encryption/VAPID signing with throwaway keys, consent/session/status suppression, retries, expiry cleanup and stable notification tags. `apps/api/tests/test_push_notifications.py` uses an isolated database to test authenticated enrollment, ownership, account switching, event deduplication and logout. `apps/web/tests/pwa.test.mjs` verifies caching boundaries and notification links. `apps/web/e2e/mobile-push.mjs` tests the mobile installation and settings journey using mocked browser subscriptions and API responses, without calling browser push providers.

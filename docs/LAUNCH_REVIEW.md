# Launch review — updated 1 October 2026

This review improves deployment safety and verifies local behavior. It does not certify a live production deployment or external integrations.

## Changes

- Removed provider credentials from the tracked example environment file. Rotate the exposed OpenAI, Gemini and Dodo keys before deployment. Private `.env` values were not changed.
- Added production startup checks for signing secrets, secure cookies, a public HTTPS origin and separate background workers.
- Made health probes independent of application settings; readiness now checks the installed migration revision. Docker waits for readiness and binds the API to loopback by default.
- Prevented caching authenticated API responses and closed a cookie CSRF bypass involving non-Bearer authorization headers.
- Disabled WhatsApp simulation in production and hid its controls there.
- Passed the public domain into Docker web builds for sitemap and social metadata.
- Fixed immediate upload completion failing to notify onboarding. Polling now avoids overlapping requests and cancels when the component unmounts.
- Added onboarding preference error feedback, a custom missing-page screen and a retry screen for page errors.
- Fixed an assistant crash caused by implicitly returning a browser scroll result from an effect and added conversation-load error feedback. The web assistant now queues durable replies, allowing navigation and conversation switching while replies finish.
- Fixed assistant stream callback failures being invoked twice, released stream readers, and corrected request handling for false JSON bodies.
- Used ordinary links for signed file downloads to avoid framework prefetches.
- Added an Activity center and background worker processing for long-running tasks, allowing the user to navigate away without interrupting generation.
- Added an Activity dashboard with active counts, progress, status filters, result links, completion toasts and persistent in-app notifications. Assistant replies survive closing and reopening the browser.
- Added explicit background continuation to worksheet creation and onboarding, recovery of active lesson jobs after reload, and meaningful titles and direct links for generated documents.
- Made dialogs keyboard-accessible with labelled headings, focus containment, Escape dismissal and focus restoration; verified Activity at mobile width.
- Refreshed the shared session cache after signup, password login and magic-link login, preventing a stale signed-out state from redirecting authenticated users back to login.
- Fixed analysis and rendering of PowerPoint files with multiple slide masters. The previously affected local upload completed successfully after retry.
- Updated the deprecated upload proxy configuration, preserving the existing 100 MB setting. See [Next.js configuration](https://nextjs.org/docs/pages/api-reference/config/next-config-js/proxyClientMaxBodySize).
- Added backend security regressions and frontend API tests, enabled frontend tests in CI, and guarded destructive database tests against non-test database names.

## Validation

- API lint passed.
- Full API suite: 162 tests passed against isolated PostgreSQL/pgvector and LibreOffice, using the validated API Docker image with current source mounted (1 October). Includes durable assistant jobs, owner isolation, activity ordering, safe failure messages and multiple slide masters.
- Frontend API tests: 3 passed.
- Production Next.js build, including TypeScript validation, passed.
- Background browser regression passed with a deliberately paused worker: prompt request acceptance, navigation and reload while queued, closing the browser context, reopening saved replies and documents, persistent notifications and mobile Activity. This regression now runs in CI.
- Fresh Alembic migration and model drift check passed.
- Compose configuration validation passed.
- Backend Docker image rebuilt successfully with the pinned runtime dependencies; dependency consistency check and all 12 launch-safety tests passed against the rebuilt image.
- Browser end-to-end validation passed on 1 October with the current production web build and separate worker: signup, onboarding, upload/style analysis, lesson generation, PPTX download, slide editing, worksheet creation, saved assistant replies, Activity, teacher pages, support, notifications, sessions, mobile layout and admin workflows. No browser errors were reported. The background regression also passed again against this build with the worker running normally. Screenshots are in `apps/web/e2e/screenshots/` (ignored by Git).

Runtime Python dependencies are pinned in `apps/api/constraints.txt` to the versions used by the tested Docker image. Docker, CI and the local setup instructions apply those constraints. The backend image was rebuilt successfully. Base images and operating-system packages are not pinned by the Python constraints.

## Required before public launch

1. Rotate the exposed provider keys and configure the real domain, HTTPS proxy and production environment using `DEPLOYMENT.md`.
2. Exercise live AI generation with an approved model configuration and inspect teaching quality, exported slides and actual cost. Automated generation used the offline provider.
3. Verify SMTP delivery and password reset, payment checkout and webhook handling in provider test mode, and each enabled OAuth/WhatsApp/storage integration. Credentials alone do not establish that an integration works.
4. Replace illustrative curriculum data and review published policies and business details for the intended market. Arabic UI coverage remains partial.
5. Configure backups and monitoring, perform a restore drill, and measure concurrent generation capacity on the deployment hardware.

No production deployment or live provider purchase was performed.

## Local preview

The review preview is running at http://localhost:3008 with offline AI and isolated demo data. It uses Docker containers `pptgenie-review-api`, `pptgenie-review-worker` and `pptgenie-review-db` on the `pptgenie-review` network, shared persistent storage, and a local Next.js production server on port 3008. API requests queue work with `RUN_JOBS_INLINE=false`. It does not use the private `.env` credentials.

Uploaded files must finish transferring before the browser closes. Once a task is accepted, the worker processes it independently. Completion notifications are available inside the app; browser push notifications are not implemented.

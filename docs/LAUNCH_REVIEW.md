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

## Additional product and reliability review

The implementation order and release gates are recorded in [PRODUCTION_PLAN.md](PRODUCTION_PLAN.md).

- Template changes now save atomically with a queued preview job. Concurrent refreshes are rejected; Activity tracks completion. Versioned image paths prevent stale preview caching, and a failed render preserves the previous previews.
- Added template name/colour/font-size validation, read-only ownership feedback, action errors, missing-template recovery, image fallbacks, search and type/default filters.
- Template detail uses a single column until a wide layout fits; form controls, cards and headers handle small screens. Preview images retain their full aspect ratio.
- Added a persistent offline indicator and retry states for projects, library tabs, dashboard, weekly calendar and teacher memory. Fixed Teacher Memory overflow on narrow screens and added feedback for failed note/preference actions.
- Restricted sign-in return paths to the application origin, rejecting protocol-relative and backslash redirects.
- Expanded the landing page with three interactive illustrative lesson examples, output descriptions, background-work guidance, FAQs and mobile navigation. Removed unsupported absolute layout and school-compliance promises.
- Added responsive/template, production UX and admin viewport checks to CI. Admin panels and payment controls wrap on narrow displays; wide data tables remain scrollable inside their panels.

## Validation

- API lint passed.
- Full API suite: 167 tests passed against isolated PostgreSQL/pgvector and LibreOffice, using the validated API Docker image with current source mounted (1 October). Includes durable assistant jobs, owner isolation, activity ordering, safe failure messages and multiple slide masters.
- Frontend tests: 4 passed, including safe sign-in redirects.
- Production Next.js build, including TypeScript validation, passed.
- Landing interactions, mobile navigation, offline feedback and simulated API failure/retry checks passed. Landing and template pages fit 320–1920px; the expanded teacher screen checks passed at 320, 768 and 1024px. Template upload, queued editing, validation, deletion and missing-template recovery passed.
- Background browser regression passed with a deliberately paused worker: prompt request acceptance, navigation and reload while queued, closing the browser context, reopening saved replies and documents, persistent notifications and mobile Activity. This regression now runs in CI.
- Admin responsive regression passed across 15 admin screens at 320, 768 and 1024px after fixing the three overflowing layouts.
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

## Product video

Added a 30-second doodle-style product tour to the landing page, with a 1920×1080 website export and a separately composed 1080×1920 social export. Both are H.264/AAC with an original synthesized soundtrack and on-screen captions. Posters, WebVTT/SRT captions, editable animation source, storyboard and suggested social copy are included under `assets/product-video/` and `apps/web/public/videos/`. No social publishing was performed.

The supplied Clastio logo now replaces the provisional mark in the app, favicon metadata, video headers, closing cards and regenerated posters. The original PNG is retained unchanged at `apps/web/public/brand/clastio-original.png`; display windows reuse its symbol and wordmark without redrawing them.

## AI spending controls — implementation update

Added atomic USD reservations for all paid AI entry points, bounded provider attempts, uncertain-charge holds, invoice reconciliation, admin controls/token diagnostics, tenant-isolated cache keys, and live teacher credit estimates. See [AI cost controls](AI_COST_CONTROLS.md) for defaults, configuration, operational limits and migration instructions. Paid calls default to paused and require approved model price cards. Local validation uses offline or fake providers; live pricing/quality still requires a small account-authorized benchmark before launch.

Validation for the AI controls: **185 backend tests passed**, Ruff passed, production web build passed, **4 web tests passed**, full browser E2E passed, responsive admin checks passed, and the dedicated AI-budget browser check passed. `alembic upgrade head` and `alembic check` passed on the local review database (head `b174cafe0124`). No paid AI calls were made. Invoice imports remain manual; approved pricing and a small live quality/cost benchmark are still required before enabling paid generation.

## Supplied PowerPoint local regression test

Tested the root-folder Grade 1 addition/subtraction deck end to end. Fixed duplicate slide parts caused by master navigation links, false visual-QC success when rendering failed, stale PDF downloads after rendering failure, and false overflow detections on master text. All 187 backend tests, web build, 4 web tests and the full supplied-deck browser workflow passed. Offline content remains sample-only, not classroom-validated. See [local PPT report](LOCAL_PPT_TEST_REPORT.md) for evidence, exports and the pending live accuracy test.

## Walkthrough and production capacity — 2 October 2026

- Added teacher and permission-aware administrator tours, page-specific chapter/lesson guides, browser-local pause/resume and Tutorials replay. Mobile Chrome checks completed both full tours (18 teacher / 9 super-admin steps) and confirmed they did not submit generation or messaging requests.
- Production Compose configuration for `clastio.online` validates with non-secret placeholder values. HTTPS edge routing, private backend ports, persisted Redis, bounded database pools, replicated workers and a separate scheduler are prepared. Production startup requires Redis; migration seeding avoids demo accounts and paid embeddings.
- Added renewable shared AI-call capacity leases, job heartbeats, serial owner-limit claim checks and bounded asynchronous password hashing. Existing rate limits are retained.
- Backend regression: 221 tests passed before the additional concurrent-user/worker tests. Local 100-session regression completed 200 authenticated requests in 4.50 seconds against real PostgreSQL (offline ASGI; not a deployment throughput benchmark).
- Next.js production compilation, TypeScript and all 46 routes passed using webpack. The local Turbopack build failed on an OS port-binding restriction; the production build command now selects webpack explicitly.
- No paid AI calls, domain/DNS changes or public deployment were performed. Hosting is not yet purchased. See [production setup and remaining release checks](PRODUCTION_CAPACITY.md).
- Additional capacity checks: six passed, covering shared Redis limits/renewal/cancellation, fail-closed behavior, nonblocking password checks, competing owner-limited claims, job heartbeat renewal and the 100-session request regression. TypeScript and Ruff passed.

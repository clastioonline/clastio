# Clastio launch readiness — 12 October 2026

**Release decision: complete the production checks below before opening public registration or paid marketing.** Local checks verify deterministic/offline workflows and mocked provider boundaries. Two bounded, synthetic live OpenRouter schema checks also passed. This review does not certify the public Render/Railway deployment or the complete production teacher workflow. Evidence is saved in [`artifacts/launch-audit-20261012`](../artifacts/launch-audit-20261012/).

### Current changes and defects found

- Teacher presentation settings add an optional teacher-name footer at the bottom right and an independent page-number toggle. Both are off by default. Editable PowerPoint and real rendered PDF checks verify these options. The audit caught and fixed a legacy template number surviving both toggle states; the final exported PDFs contain no legacy numeric footer text. Existing template credits/logos remain design content.
- Onboarding teaching subjects/classes are used to limit lesson and presentation selectors. Teachers can change their teaching scope in Settings. Saved content remains accessible; this is personalization, not an authorization boundary between teachers.
- The book catalogue provides 10 source collections and 31 named UAE/British textbook references, prioritizing the teacher's selected curriculum and relevant subjects/stages. It links official/publisher and openly licensed sources; restricted commercial textbooks remain references and PDF sharing requires explicit rights confirmation. These counts describe the starter catalogue, not 31 imported textbook PDFs or complete coverage of every book.
- The audit fixed staff book-catalogue navigation: staff with `settings.modify` can open the `/books` publication controls; other staff retain their existing restrictions.
- The audit fixed device notifications stopping when an ordinary sign-in session expires. Explicit sign-out/session revocation, account state, category consent, staff permissions and marketing opt-in still stop delivery.
- The audit found and fixed deterministic daily lesson generation missing required teaching layouts, truly empty scanned-PDF pages being treated as content, and design-guidance prompt JSON being truncated mid-entry. The production content validator remains strict.
- Compatible dependency updates fix the three npm advisories found in Next.js, sharp and source-map-js. The current npm scan reports zero vulnerabilities. The pinned Python production dependency scan checks 88 dependencies with zero known advisories and zero skipped dependencies.

### Verification and scope

| Check | Current evidence | Scope |
| --- | --- | --- |
| API standalone unit suite | All 607 passed within the combined run | Offline/fake AI and mocked providers; no user database |
| Frontend unit tests | 17 passed | Request handling, redirects, private PWA behavior, credits and teaching-scope helpers |
| Teacher settings, slide editor and teaching-scope browser checks | Passed optional footer/page-number defaults and saved settings, slide selection/drag/undo/redo/keyboard controls, scoped PPT/demo choices, onboarding classes and educator screens at four viewport widths | Mocked API boundaries against the final local web build; no teacher account/database writes |
| TypeScript, API Ruff and whitespace checks | Passed | Final source validation |
| Fresh audit-stack migrations | Applied through `i209educator01`; `alembic check` reports no new upgrade operations; services healthy | Separate local Postgres, Redis and storage volumes; no live keys |
| Combined backend regression | 908 passed and one incorrect cross-user push-test assertion failed in 625 seconds; after scoping it to the revoked device, both affected modules pass all 14 checks, including a new real-DB expiry regression | Original 909 cases plus the new expiry case: 910 unique checks validated across these runs, comprising 607 units and 303 integration checks. Separate `_test` database and audit Redis; real Postgres/pgvector/LibreOffice; providers offline or mocked |
| Background browser workflow | Passed | Prompt submission; worksheets/assistant survive navigation, reload and browser closing; Activity/notifications and mobile layout |
| Mocked launch browser workflow | Passed | Consent, onboarding/activity, explicit trial, coupon checkout, licenses, pending-payment recovery, retry feedback and read-only staff |
| Complete teacher/admin browser workflow | Passed signup/verification/onboarding, explicit trial, uploaded design analysis, first-PPT approval before the next lesson, slide editing, real exports, worksheet/assistant, notifications/support/sessions, mobile and admin screens/search; no browser errors | Separate local synthetic accounts, real API/worker/exports, offline AI. Every edited slide preview present; visual inspection completed with zero visual QC errors |
| Book browser workflow | Passed teacher catalogue/filter/import/chapter selection and permission-scoped staff publication on the final image; no mobile overflow | Fully mocked book/AI requests; no remote book download |
| Real footer export check | Passed enabled and disabled settings; native editable footer text and PDF text checked; legacy numeric spans absent | Uploaded sample design, two-slide PPTX/PDF, sidecar LibreOffice; no AI |
| Bounded live OpenRouter smoke | Passed exactly two HTTP 200 responses finishing normally; eight teaching blocks and three slides satisfy all 22 schema/content/layout/outcome assertions; total settled cost USD 0.03843675 | Synthetic prompts only, no uploaded/private material, no teacher artifacts or settings changed. Does not exercise the complete live worker/export pipeline or native-image route |
| Public hosting and other real integrations | Not exercised in this review | No production signup, payment, delivered email, push/WhatsApp receipt or public deployment |

The local audit stack uses ports 3012/8012 and separate data. The existing teacher stack on 3005 is never used for mutating browser tests. Read-only runtime checks used non-secret flags, credential presence, published-contact placeholder presence and aggregate status counts. The separately authorized live smoke wrote only normal AI usage/reservation records and settled both reservations; it saved no teacher artifacts and changed no configuration. Secret values are absent from this report and evidence artifacts.

Relevant evidence: [combined regression log](../artifacts/launch-audit-20261012/backend-regression-final.log), [passing affected-module XML](../artifacts/launch-audit-20261012/backend-push-ordering.xml), [complete browser log](../artifacts/launch-audit-20261012/browser-core-complete.log), [book browser log](../artifacts/launch-audit-20261012/browser-books.log), [footer export proof](../artifacts/launch-audit-20261012/footer-exports/evidence.json), [rendered footer](../artifacts/launch-audit-20261012/footer-exports/footer-enabled.png), [npm advisory scan](../artifacts/launch-audit-20261012/npm-production-audit.json), [Python advisory scan](../artifacts/launch-audit-20261012/python-production-advisories.json), [live schema smoke](../artifacts/launch-audit-20261012/live-openrouter-smoke.json), and [migration drift check](../artifacts/launch-audit-20261012/migrations-check.txt).

The final [educator browser check](../artifacts/launch-audit-20261012/browser-educator-final.log) covers four viewport widths and the saved onboarding scope. The focused browser fixtures are [`presentation-preferences.mjs`](../apps/web/e2e/presentation-preferences.mjs), [`slide-canvas.mjs`](../apps/web/e2e/slide-canvas.mjs), [`onboarding-teaching-scope.mjs`](../apps/web/e2e/onboarding-teaching-scope.mjs) and [`educator-workspace.mjs`](../apps/web/e2e/educator-workspace.mjs).

### Production checks still required

1. **Production configuration and a traceable release.** The current local runtime remains `development`, uses the default development signing key, HTTP localhost, insecure cookies, local file storage and version `dev`. It fails the existing production validator for signing key, cookie security and public origin. Configure a fresh strong shared signing key, `ENVIRONMENT=production`, HTTPS public origin, secure cookies, `SEED_DEMO=false`, private backend ports and an actual release identifier. Compose supplies Redis even though the local `.env` has no Redis value. Confirm frontend/API/worker/scheduler use the same intended revision and migrations.
2. **Usable verified sign-in and application email.** Local Resend/SMTP and Clerk credentials are unset; local mail is logged instead of delivered. Configure the chosen authentication/email provider and verified sender, run the scheduler, and prove verification/reset/login, sign-out/revocation and one delivered application notice. Enable `require_email_verification_for_generation` before public free generation. Mock tests do not prove inbox delivery.
3. **Payments if paid plans are offered.** Stripe/Dodo credentials and signed-webhook settings are unset locally. Complete provider test-mode checkout, failure/recovery, duplicate webhook, activation, receipt, portal, cancellation and renewal before switching live products. Hide/disable purchases until configured; do not infer success from a return URL.
4. **A complete live teacher benchmark.** The configured OpenRouter teaching-material and deck-batch routes pass the two small synthetic checks above with no truncation. The complete live worker, source-grounded chapter, native-image route and editing/export pipeline remain unverified as a combined workflow. Review price cards and spend ceilings, generate one small real lesson through the worker, inspect factual accuracy/source coverage and editable PPTX/PDF output, perform one edit, and inspect actual provider cost. Earlier source warnings still require teacher review.
5. **Storage, backups and operations.** S3/R2 and error-monitoring credentials are unset locally. For separately hosted API/workers, configure the same private object storage; prove a source upload, private download and cross-teacher rejection. Establish off-host database/file backups and restore to a separate database. Verify worker/scheduler behavior, queued email, delayed/failed jobs, provider/payment logs and usage alerts. Measure actual hosted capacity; health/readiness checks do not measure throughput or worker progress.
6. **Public business/content information.** The [focused legal-page audit](LEGAL_PAGES_AUDIT.md) confirms all five core routes work, but the actual published versions retain legacy PPT Genie templates and an `.example` contact. Replace the business/contact details, verify provider/training and cookie statements, establish copyright/public-contact coverage, and resolve the source-inspected data-deletion and partial-export gaps before relying on the privacy promises. Publish reviewed new document versions; reseeding preserves existing published rows. Review the advertised curriculum coverage; starter outcome codes remain illustrative. Keep official/authorized/open textbook references distinct from PDFs the platform has permission to store and share.
7. **Optional integrations only when verified.** WhatsApp and Web Push credentials are unset locally. Do not advertise real message/device delivery until consent, provider credentials, scheduler operation and a real-device receipt are verified. Optional tools need not delay launch when disabled and described accurately.

Use the [Render/Railway runbook](RENDER_RAILWAY_LAUNCH_GUIDE.md), [AI spending controls](AI_COST_CONTROLS.md), [book library workflow](BOOK_LIBRARY_WORKFLOW.md) and [mobile notification guidance](MOBILE_APP_AND_PUSH.md). The following historical evidence describes older revisions and dates; it does not replace the current results above.

## Historical audit — 4 October 2026

**Release decision: complete the production gates below before paid marketing.** The audited fixes are committed in release `a0bbcfd`. A fresh public check now confirms migration `e205checkout01` and healthy dependencies on both API origins. The public version remains `dev`, so matching frontend, API, worker and scheduler revisions still need confirmation. A healthy homepage or API does not establish that checkout, email, background generation or storage works for a teacher.

The subsequent admin activity correction, mobile push, reviewed Free credit tasks, UAE templates and content-quality checks remain local until committed, pushed and deployed to Render and Railway. The new local migration head is `g207credits01`; the last public production check below predates these changes.

## Local follow-up — 5 October 2026

- Expired seven-day trials return to Free without an automatic payment or a fresh same-month allowance. Saved lessons remain. Signed first-party browser claims deter trials across different emails, alongside normalized-email history and verified eligibility. Clearing cookies, incognito or another browser can bypass this deterrent; shared school devices have an audited exception for a teacher's own first trial.
- Free teachers have an Earn credits page, and billing staff can create tasks and manually approve proof. The program starts disabled with no tasks. Approval uses transactional account/browser claims, current eligibility and bounded daily, monthly, lifetime and platform budgets. Credits expire at the next Free month.
- The installable PWA provides Chrome installation and iPhone/iPad Home Screen guidance. Optional per-device Web Push uses encrypted payloads, category consent, a durable outbox and retries. The service worker caches only public brand icons. Live delivery requires matching VAPID settings on the API and scheduler plus explicit teacher opt-in.
- Twelve new UAE classroom designs bring the library to fifteen. Suggestions use stated subject, grade, curriculum, language and saved/uploaded school design, preserving teacher choices. Private uploads shared without an organisation are excluded. Themes do not claim official school branding or curriculum endorsement.
- Content generation now checks requested counts, learning goals, quiz structure and answer keys, narrowly scoped exact arithmetic, assessment completeness and supplied outcome codes. Bounded repairs cannot hide invalid quizzes or invent curriculum codes. Failed essential checks stop publication and release reserved teacher credits. These checks do not replace factual teacher review or refund already-incurred provider costs.

Setup notes: [Free trials and credit tasks](FREE_TRIAL_AND_CREDIT_TASKS.md), [mobile installation and push](MOBILE_APP_AND_PUSH.md), [UAE templates](UAE_TEMPLATES.md), and [content quality](CONTENT_QUALITY.md).

Follow-up validation: fresh migrations through `g207credits01` match the models with no schema drift. The combined backend regression and targeted proxy/Redis reruns gave 541 passing cases across those runs before the final guard refinements. The final quality, push and browser-device units pass all 77 cases; nine database-backed generation/edit/export cases pass with real LibreOffice PPT/PDF output. The latest frontend build passes for 69 routes, all eleven frontend unit cases pass, and all four browser journeys pass against the production build: mobile/push settings, Free rewards, UAE templates and admin activity. Backend lint and whitespace checks pass. These tests used offline AI, test accounts and mocked push providers; no production messages or paid generation were performed.

Current export regression evidence is `/private/tmp/clastio-final-followup/content-quality-final-junit.xml`. Earlier temporary artifacts may have been removed between local sessions.

## Public production checks

Read-only checks against `https://clastio.online` on 4 October 2026:

| Check | Observed result |
| --- | --- |
| `/api/v1/ready` | HTTP 200 through both Clastio and Railway origins; PostgreSQL, Redis and deployed schema ready; migration `e205checkout01`; version `dev` |
| AI readiness | Live mode; OpenAI listed; does not establish approved model routing, paid-call admission or output quality |
| Subscription catalogue | Teacher AED 149, Teacher Pro AED 249, Genie Assistant AED 399 per month |
| Online checkout | **Disabled**; payment provider `null` |
| Trial | **Disabled**; configured duration 7 days and allowance 50 credits |
| `/login`, `/signup` | HTTP 200; a fresh browser rendered actual Clerk cards without page exceptions in the earlier check |
| Public pages | Homepage, pricing, FAQ, how-it-works, schools, solutions, status and principal legal pages returned HTTP 200 |
| Legal terms | Published content has no former template notice |
| Search assets | `/favicon.ico`, `/brand/favicon.png`, `/robots.txt`, `/sitemap.xml` returned HTTP 200 |

No production accounts, subscriptions, database rows or provider configuration were changed. No real email, checkout purchase or paid AI call was made. Public readiness cannot establish the presence of the Railway worker or scheduler.

## Bugs fixed in this release

| Area | Result |
| --- | --- |
| Clerk access | Trusted Clerk public metadata controls staff roles; promotions persist, staff skip teacher onboarding and land on a page allowed by their permissions. Privileged sessions require Clerk sign-in. Banned/deleted identities revoke app sessions when detected; active teachers refresh at most once per minute, staff and account refresh check immediately. |
| Billing integrity | Unpaid/incomplete payments do not grant paid access. An unresolved subscription keeps its portal/recovery path and blocks another purchase or manual grant. Expired payment grace no longer grants access indefinitely. |
| Checkout concurrency | One durable pending reservation per teacher, enforced by PostgreSQL locking and a unique index. Repeated requests resume the same checkout. Stripe uses stable idempotency and confirmed expiry; uncertain responses stay held for reconciliation. Trials, licenses and manual grants cannot overlap a pending purchase. |
| Prices and payment records | Dodo recurring prices and one-time packs must match the AED catalogue and product type. Stripe uses decimal minor-unit conversion. A failed payment recovered later becomes paid and issues its receipt/reward once. Annual and multi-month grants reset allowances monthly. |
| Free and trial choice | New teachers begin on Free. Eligible verified teachers explicitly start a trial, including after onboarding. Public copy matches this behavior. Signup does not silently consume the trial. |
| License keys | Staff creation/revocation and teacher redemption are present. Only a key hash is stored; the full key is displayed once. Permission, expiry, single-use and concurrent redemption checks are enforced. |
| Credit balances | Admin grants and queued reservations appear in spendable balances; progress never displays negative usage. Whole-trial warnings do not promise a monthly reset. |
| Email and reminders | Missing production mail configuration leaves recoverable queued messages. Delivery rechecks consent, preferences, current recipient and active-account status. Bad headers cannot stop the whole batch. Dismissed reminders preserve deduplication; renewed grants receive period-specific expiry reminders. Review invitations follow the selected notification channels. |
| Privacy | Logs redact nested credentials, private prompts and SQL parameter dumps. Sentry excludes request bodies and exception locals and applies redaction to errors/traces. |
| Railway proxy handling | The API image explicitly trusts Railway's `100.64.0.0/10` edge peers alongside its private proxies; public peers cannot forge forwarded client addresses. The cross-provider Render client-IP chain still requires the deployment check below. |
| Stock images | Downloads reject non-public destinations and unsafe URLs, validate every redirect and enforce a streaming size limit. Connections use the validated IP with the original HTTP host/TLS SNI, preventing DNS changes from bypassing validation. Environment proxies and cross-host connection reuse are disabled. |
| Web resilience | Account and billing errors have retry states; temporary backend errors do not log teachers out. Public cookie choices avoid authenticated consent requests. Read-only staff cannot see prohibited mutation controls. Onboarding activity works. |
| Admin activity follow-up | Staff see their own recorded staff actions and permitted operational links. Personal teacher jobs, task badges, completion toasts and teaching actions stop after promotion; the stored teaching history is preserved. The API also returns an empty personal teaching feed for staff. |
| Public discovery | Canonicals for pricing, status and legal pages; invalid legal pages return 404; production Clerk CSP is narrower; logo/favicon metadata and guide pages checked. |
| Regression automation | CI now includes backend unit tests as well as database tests, uses explicit offline AI for browser tests, and runs launch and discovery regressions. Browser fixtures match Free-first signup, explicit trials and current controls. |

## Validation evidence

- Fresh isolated PostgreSQL/pgvector migrations through `e205checkout01` applied successfully. `alembic check` reported no new upgrade operations.
- Seven real PostgreSQL checkout/license concurrency cases passed in the first full database run. They exercise simultaneous checkout requests, conflicting plan choices, unique pending reservations, confirmed expiry, and single-use licenses.
- Combined backend run: **406 passed, 1 skipped, 0 failures** against isolated PostgreSQL/pgvector with real LibreOffice exports. The skipped Redis capacity test then passed against the dedicated audit Redis, giving **407 passing cases** across those runs. The later seven proxy-boundary cases also passed, giving **414 passing backend cases overall**.
- Backend lint for `app`, `tests` and `unit_tests` passes; Python compilation and `git diff --check` pass.
- Production Next.js build passes for 66 routes; **6 frontend unit tests** and type checking pass.
- Admin activity follow-up: all six backend activity tests pass, including promotion and preserved history; the browser regression passes for an in-place promotion with a delayed teacher response, audit retry/refresh and restricted support/billing staff. Type checking and the production build pass. CI includes the new browser regression.
- Mocked launch and SEO/assistant browser regressions passed, including pending purchase recovery, grants/reservations, Free-first onboarding, explicit trial, coupons, licenses, staff permissions, request retries, 13 guides, mobile/desktop layout, metadata, favicon and clarify-before-image-replacement behavior.
- Targeted scans found no embedded provider keys in tracked source. The private `.env` remains ignored.
- npm production advisory scan: 0 known vulnerabilities across 37 production dependencies. Python advisory scans: 0 known vulnerabilities across 90 installed packages and all 77 production constraint pins, without skipped packages. Compatibility check passes. These are advisory results, not proof against undiscovered vulnerabilities.

All six final browser suites passed: the complete teacher/admin journey, mocked launch recovery, SEO/assistant interaction, AI budget estimates, production error/offline UX, and 45 admin page/viewport combinations. The real local journey exercised Free signup, verification, explicit trial, uploaded style analysis, 20 generated slides, PPT download, targeted rebuild, six worksheet/answer-key exports, assistant, notifications, support, account/session controls and admin navigation without browser exceptions. AI used the offline provider and local sample accounts.

Saved evidence: `/private/tmp/clastio-final-backend-tests.log`, `/private/tmp/clastio-final-backend-junit.xml`, `/private/tmp/clastio-final-capacity-tests.log`, `/private/tmp/clastio-launch-browser.log`; screenshots and a generated PPT in `/private/tmp/clastio-launch-e2e`. Temporary Docker audit services are stopped and removed after validation. Previous test counts in `LAUNCH_REVIEW.md` describe older revisions.

## Production gates, in order

1. **Rotate the secrets already exposed in chat:** OpenAI key, Clerk secret key, and Cloudflare/R2 token and S3 credentials. Revoke the old values and enter replacements directly in provider dashboards and deployment environment settings. Clerk's publishable key is public; keep secret keys out of `NEXT_PUBLIC_*`. Inspect provider usage for unexpected activity.
2. **Confirm matching deployments of the audited release.** The audited changes are committed as `a0bbcfd`, and both public API origins now report migration `e205checkout01` and readiness HTTP 200. Confirm the API, worker, scheduler and Render service all use the intended release. Take a backup before further deployment or migration changes. Use the API pre-deploy command below when deploying, then start dependent services. Set `APP_VERSION` to the release identifier so a deployment can be identified.
   The local follow-up requires migration `g207credits01` and the updated template seed. Deploy the API, worker, scheduler and frontend together. Enable **Require verified email to generate** in Admin → Settings & flags → Platform before opening Free generation to marketing traffic.
3. **Verify Clerk as two real users.** Use a teacher and the owner. Confirm verified sign-in, terms acceptance, Free onboarding, sign-out and sign-in again. Set the owner's Clerk Public metadata to `{"role":"admin","admin_role":"super_admin"}` and confirm the admin skips teacher setup. Confirm demotion/banning removes access. Configure Clerk auth-email delivery separately from application Resend mail.
4. **Enable the intended seven-day trial.** In Admin → Plans & trial, enable it and review finite allowances. Confirm a new teacher can remain Free or explicitly start the trial, and a spent/expired allowance is enforced. Check that existing paid/license/pending-purchase accounts cannot claim overlapping grants.
5. **Configure and verify payments.** Select Stripe or Dodo, configure matching AED products/prices and signed webhooks, and enable online checkout. First exercise provider test mode: coupon success/refusal, successful and failed payment, duplicate webhook, receipt, referral reward, portal, cancellation, renewal and pending-checkout recovery. Check the final gateway total, tax and fees. Activate live mode only after this journey works.
6. **Verify application mail and scheduled work.** Run a worker and one dedicated scheduler with the same DB, Redis, signing key, private R2 storage and provider settings. Configure a verified Resend domain and purpose-specific senders. Send a consented app email and confirm the outbox is `sent` and the message arrives. Verify a payment reminder, PPT-ready update and review invitation with teacher preferences. A Resend API key alone does not prove delivery.
7. **Benchmark a small live PPT.** Approve actual available model IDs, price cards and spending ceilings in Admin → AI costs; then enable paid calls deliberately. Test source/image upload, playground questions, reviewed brief, hybrid/stock images, generation through the worker, editable PPTX/PDF downloads and one targeted edit. Inspect teaching accuracy and actual provider cost. Offline output proves the workflow, not classroom accuracy or margin.
8. **Prove recovery and privacy.** Test another teacher's private URLs are rejected, a production R2 upload/download works, and a database backup restores into a separate database. Inspect resolved API/security-log client addresses from two independent clients: Railway edge trust is fixed, but Render's public egress hop may still group teachers under one IP rate-limit bucket. If it does, add an authenticated frontend-to-API client-IP forwarding boundary; never use wildcard proxy trust to bypass it. Monitor API/worker errors, delayed jobs, outbox failures, payment webhook delivery and AI spend. Measure capacity on the actual Render/Railway service sizes before increasing ads.
9. **Submit discovery assets.** Verify Search Console/Bing ownership and submit the sitemap. Inspect branded search snippets after recrawling. The app supplies a valid square logo/favicon and structured metadata; Google chooses display and ranking. Do not promise first-place ranking, universal AI-detector results or official curriculum compliance based on these checks.

### Exact API pre-deploy command

```sh
sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'
```

The explicit shell wrapper ensures both migration and seed run. Do not seed demo accounts or paid embeddings in production. Worker: `python -m app.worker --concurrency 2 --no-scheduler`. Scheduler: `python -m app.worker --scheduler-only` (one instance).

For Stripe, subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`. Match test/live webhook secrets and product IDs.

## Deliberate limits and follow-up work

- A lost Dodo checkout-creation response can leave an uncertain reservation without a URL. Reconcile it with the provider before releasing it; blindly retrying could duplicate a charge. Confirmed sessions can be resumed and expiry is verified against the provider. Stripe supports explicit closing of an unpaid open checkout.
- Clerk account bans/deletions are checked as described above. Revoking one Clerk session alone does not immediately revoke an independently issued app session; use Clastio session controls to terminate that app session. A provider session/webhook revocation bridge is separate work.
- `/ready` checks dependencies/schema, not worker or scheduler heartbeats. Functional job and email tests are required.
- Real SMTP/Resend, Stripe/Dodo, Clerk identity exchange, private R2 permissions, backup recovery and paid AI costs are not certified by mocked/offline tests. No live credentials were read or copied for this audit.
- Initial curriculum outcomes are illustrative starter data; import/review the authoritative material for what you advertise. Arabic coverage remains partial. Browser push is implemented locally; actual production device delivery still requires configuration, deployment and a real-device check.
- Refund/reversal referral clawbacks and automated provider-invoice cost imports are not implemented. Staff adjustment and manual cost reconciliation remain necessary.

Use [the deployment runbook](RENDER_RAILWAY_LAUNCH_GUIDE.md), [email/billing feature notes](ENGAGEMENT_AND_BILLING.md) and [AI cost controls](AI_COST_CONTROLS.md) for the exact settings. This report describes evidence and practical release conditions; it is not a promise of zero remaining bugs.

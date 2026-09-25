# PPT Genie platform: security, operations and admin

This covers the production SaaS layer: accounts, sessions, roles, audit, limits, billing safety, notifications,
legal and the admin console. Status is labelled throughout:

- **Implemented**: in the code, and covered by tests where noted.
- **Configured**: works once you set an environment variable or an admin setting.
- **Recommended**: not built; do it before or after launch.

Test suite: `apps/api/tests` has 144 backend tests. `apps/web/e2e/run.mjs` drives a real browser through sign-up,
generation, notifications, support, settings and every admin page.

## 1. Architecture

```
Browser ── Next.js (apps/web) ── /api/* proxy ──► FastAPI (apps/api) ──► Postgres 16 + pgvector
                                                        │                 (jobs, ledger, audit, logs)
                                                        ├─► Redis (optional, shared rate limits)
Worker (python -m app.worker) ─ jobs, email outbox, reminders, retention, account purge, alerts
```

- The browser only talks to the web origin. Session cookie: `ata_session`, HttpOnly, SameSite=Lax, and Secure
  when `COOKIE_SECURE=true`.
- The request pipeline is in `app/core/http.py`. In order:
  1. request id (`req_…`);
  2. CSRF origin check;
  3. maintenance mode;
  4. rate limits;
  5. idempotency replay;
  6. the route itself;
  7. security headers;
  8. one `api_requests` row per request (metadata only).
- Errors always use the same shape, `{"success": false, "error": {code, message, details, requestId}}`. They never
  include stack traces or database messages. Users see the request id as a "ref", which support pastes into
  **Health & logs → Request trace**.

## 2. Accounts and authentication (implemented, tested)

**Account statuses**
- Stored statuses: `active`, `suspended`, `banned`, `pending_deletion`, `deleted`.
- "Email unverified" is derived from `email_verified`.
- Only `active` accounts can use the API. The check runs on every request.

**Passwords**
- Stored as Argon2 hashes, never in plain text. Staff can't see or set them; they can only send a reset link.
- Minimum 8 characters, with a common-password and email-local-part check.

**Sessions**
- Every sign-in creates a `user_sessions` row, and the token carries its `sid`.
- Revocation takes effect immediately in each of these cases:
  - logout;
  - "sign out everywhere";
  - revoking one device;
  - a password change (other devices);
  - a password reset (all devices);
  - staff force-logout;
  - suspension or ban;
  - a role change;
  - an account deletion request.

**Email verification**
- The token is signed, typed `verify`, and valid for 48 hours.
- An optional setting requires a verified email before generating content.

**Password reset**
- The token lasts 30 minutes and is single-use: it is bound to the current password hash.
- The forgot-password response is identical whether or not the account exists.

**Sign-in signals**
- New-device detection covers browser, OS and IP prefix. It creates a security event, an in-app notice and an
  email.
- Failed logins and rate-limit hits are recorded as security events.

**Other auth features**
- Optional Cloudflare Turnstile CAPTCHA on sign-up (configured by `TURNSTILE_*`).
- Google and Microsoft OAuth link to an existing account only if the provider says the email is verified.

**Not implemented:** 2FA/TOTP. The session model supports adding it as a step before `start_session`.

## 3. Roles and permissions (implemented, tested)

- Staff roles are `super_admin`, `admin`, `support`, `analyst`, `finance` and `moderator`. Their permissions are
  listed explicitly in `app/core/permissions.py`, and the console shows the full matrix under **Staff & roles**.
- Every admin endpoint uses `require("<permission>")` on the server. The UI hides controls the role lacks, but it
  is never the enforcement point.
- Staff can't act on their own account.
- Only `admins.manage` (super admin) can change or suspend other staff.
- The last active super admin can't be demoted.
- Teachers can't reach another teacher's resources: the API returns 404, so ids can't be probed. Staff need
  `users.content` to open teachers' content. Covered by `test_authorization.py`.

## 4. Audit, security events and data access (implemented, tested)

**Audit log (`audit_logs`)**
- Records who did it, the action, the target, before/after values, the reason, IP, user agent and request id.
- Append-only, enforced by a Postgres trigger (`app/core/evidence.py`). A legally required purge must set
  `app.allow_evidence_purge` inside its transaction.

**Consent records (`consents`)** are append-only in the same way.

**Security events** are classified info, warning or critical. Critical events alert staff with `security.view`.

**Data access log**
- Opening a teacher's profile in the console writes a `data_access.user_profile` audit entry.
- Every CSV/JSON export writes `data.export`.
- Exports never include password hashes, and CSV cells are protected against formula injection.

## 5. Usage, limits and billing safety (implemented, tested)

**Credit checks**
- Credits are checked under a per-user Postgres advisory lock.
- Queued and running jobs reserve their expected cost (`credits_reserved`), so parallel requests can't overspend.
- Actual usage is written to the typed credit ledger. Event types: `CREDIT_USAGE`, `CREDIT_REFUND`,
  `CREDIT_PURCHASE`, `CREDIT_ADMIN_GRANT`, `CREDIT_ADJUSTMENT`, `CREDIT_EXPIRATION`. Each entry records the actor
  and the request id.

**Per-plan runtime limits**
- Daily generations, jobs running at once (applied by the worker's claim query) and upload size.
- Set in **Settings & flags** (the `plan_limits` setting). Monthly credits and storage live on the plan itself.

**Platform switches**
- Maintenance mode returns 503 to teachers; staff are exempt.
- The AI generation kill switch.
- Registration on/off.

**Rate limits**
- Per IP, per user, plus a tighter per-user bucket for AI endpoints.
- Responses carry `X-RateLimit-Limit/Remaining`; a 429 includes `Retry-After`.
- Violations become security events, throttled to one per minute.
- Redis makes the limits shared across instances (configured). Without Redis they are per process.

**Idempotency**
- `Idempotency-Key` on POST replays the stored response for 24 hours.
- A key reused with a different body gets a 422.
- The web client sends keys for ticket, message and admin actions.

**Webhooks (Stripe, Dodo)**
- Signatures are verified; a bad signature is recorded as a security event.
- Every delivery is stored with its payload hash, status, result, error and retry count.
- Duplicates are skipped. Tampered replays (same id, different payload) are rejected as critical events.
- A failure is stored, then retried by the gateway.

**AI providers**
- Timeouts per SDK, provider fallback, and a circuit breaker per provider: 5 consecutive failures, then 60 s open,
  then half-open.
- Breaker state is visible under **Health & logs**.

**Uploads**
- File type is detected from content.
- Files are streamed with the plan's size cap and checked against the storage quota.
- Local file downloads use signed, expiring URLs with a path-traversal guard.
- The original file is never modified.

## 6. Notifications (implemented, tested)

`app/services/notifications.py` holds the catalog. Each event creates an in-app notice (bell and
`/notifications`) and, depending on the teacher's preferences, a queued email. The worker sends email with backoff;
without `SMTP_URL`, messages are marked "logged".

| Group | Events |
|---|---|
| Trial & plan | trial ends in 3 days / 1 day, trial ended, renewal in 3 days (7 for annual), cancelled plan ending, granted plan expiring (7 days / 1 day) |
| Payments | payment receipt, payment failed (with gateway reason), follow-up reminders at 3 and 7 days past due, subscription confirmed/cancelled |
| Usage | 50/75/90/100% of monthly credits (email at 90/100), media credits running low |
| Your work | unit planned, lesson ready/failed, document ready/failed, media ready/failed |
| Security | new-device sign-in, password changed, account suspended/restored |
| Support & news | ticket replies, announcements (optional broadcast), policy updates |
| Staff alerts | new ticket, failed payment, critical security event, AI provider circuit open, webhook failure, ≥5 failed jobs/hour |

**Delivery rules**
- Scheduled reminders run hourly. Each one is de-duplicated per subscription and period, so nobody gets it twice.
- Teachers choose in-app and email delivery per category. Security, failed-payment and legal notices can't be
  turned off.
- Staff alerts go only to roles that hold the matching permission.

## 7. Legal and consent (implemented, tested)

**Documents**
- Terms, Privacy, Acceptable Use, Cookie and Refund documents are versioned in `legal_documents`.
- Published versions are immutable; older versions stay viewable at `/legal/<type>`.
- The shipped texts are **templates that must be reviewed by a lawyer before launch**, and each document says so.

**Sign-up consent**
- A required checkbox covers Terms + Acceptable Use and acknowledges Privacy.
- A separate, unticked marketing checkbox follows.
- Each consent is recorded with the exact version, time, IP, user agent and method.

**Updated terms**
- Publishing a version marked "requires acceptance" shows teachers a blocking prompt and sends them a notice.

**Cookies**
- The cookie banner offers essential-only, accept-analytics or customise.
- The app itself sets only the essential session cookie. No analytics scripts are included; add them only behind
  this consent.

**Account deletion**
- Deletion locks the account and signs it out now. A paid plan is cancelled at period end.
- After 30 days the purge job removes content and anonymises the user row. Payments, subscriptions, the credit
  ledger, consents, audit and security records are kept.

**Data export** is available from Settings as JSON.

## 8. Admin console

| Area | Page | What it covers |
|---|---|---|
| Overview | `/admin` | DAU/WAU/MAU, MRR/ARR, trial→paid conversion, failed payments, API error rate, generation health, AI spend |
| Users | `/admin/users` | Teachers: search, filters, sort, cursor paging, export |
| Users | `/admin/users/[id]` | Account page with tabs: overview, billing & credits, sessions & security, activity timeline, notes & audit. Actions (each needs a reason and is audited): suspend, ban, restore, force sign-out, verification, reset link, credits, plan, staff role |
| Users | `/admin/staff` | Staff list and permission matrix |
| Billing | `/admin/billing` | Payments and subscriptions |
| Billing | `/admin/plans` | Plans and trial |
| Billing | `/admin/media` | Media packs |
| Usage | `/admin/api-usage` | Requests per day and per endpoint, P50/P95/P99, errors, 429s, busiest users, AI calls/tokens/cost by model, AI failure causes |
| Usage | `/admin/ai-costs` | AI costs |
| Support | `/admin/support` | Tickets and feature requests, internal notes, assignment |
| Support | `/admin/announcements` | Announcements |
| Security | `/admin/security` | Security events |
| Security | `/admin/audit` | Audit log with before/after |
| System | `/admin/system` | Readiness, providers, queue, jobs (retry), webhooks, emails (retry), request trace |
| System | `/admin/settings` | Maintenance, kill switch, registration, feature flags, plan limits, rate limits, retention |
| System | `/admin/legal` | Legal documents: drafts, preview, publish |

Global search (⌘K) finds emails, names, user/job/payment ids, ticket numbers and `req_…` ids.

## 9. Operations

**Health endpoints**
- `/api/v1/health`: liveness, no dependencies.
- `/api/v1/ready`: database, migration, Redis and AI mode; returns 503 when not ready.
- `/api/v1/status` feeds the public `/status` page.

**Logs and monitoring**
- Logs are structured JSON with request, job and user ids, `env` and `version`. Keys that look secret are redacted.
- Sentry covers the API and worker when `SENTRY_DSN` is set (configured).

**Retention (worker, hourly)**

| Data | Default retention |
|---|---|
| API request log | 90 days |
| Security events | 365 days |
| Analytics | 400 days |
| Read notifications | 180 days |
| Sent email records | 90 days |
| Idempotency keys | 24 hours |

All of these are editable in Settings. Audit and consent records are never auto-deleted.

**Migrations** are managed by Alembic. `alembic check` is clean at head (`89c637411250`).

**Web security**
- CSP, HSTS in production, `X-Frame-Options: DENY`, `nosniff`.
- `noindex` on the signed-in app.
- `robots.txt`, `sitemap.xml` and Open Graph metadata for public pages.

## 10. Production checklist

1. Set `ENVIRONMENT=production`, a random `SECRET_KEY` of 32+ characters, `COOKIE_SECURE=true`,
   `PUBLIC_WEB_URL`, `NEXT_PUBLIC_SITE_URL` and `APP_VERSION`.
2. Run `alembic upgrade head`, then `python -m app.seed` (plans, templates, legal v1.0). Don't seed demo accounts.
3. Set `ADMIN_EMAILS` for the first super admin, sign up, then remove it. Grant other staff roles in the console.
4. Configure `SMTP_URL` and `EMAIL_FROM`. Without them, verification, reset and reminder emails are not
   delivered.
5. Configure the payment gateway keys and webhook secret, then send a test webhook. It should appear as
   "processed" under Health & logs → Webhooks.
6. Set `REDIS_URL` if you run more than one API instance.
7. Set `SENTRY_DSN`. Point uptime monitoring at `/api/v1/ready`.
8. Have a lawyer review and publish your own Terms, Privacy, Acceptable Use, Cookie and Refund texts.
9. Optional: add Turnstile keys to protect sign-up from bots.
10. Set up database backups (below) and test a restore.
11. Run the worker (`python -m app.worker`). Reminders, email, retention and purges depend on it.

## 11. Not implemented / recommended

- **2FA (TOTP/WebAuthn)**: recommended for staff accounts at least.
- **Staff impersonation**: deliberately not built. Support uses the read-only account page instead.
- **Multi-tenant school organisations**: the `organizations` table exists, but there is no org admin UI or org
  isolation layer.
- **Public API keys / API versioning beyond `/api/v1`**: there is no public API. Add keys with hashing, scopes
  and per-key limits if you open one.
- **Automated backups**: not included. Use managed Postgres point-in-time recovery or scheduled `pg_dump` to
  object storage, and rehearse restores.
- **Malware scanning of uploads**: files are type-checked but not virus-scanned. Add ClamAV or a scanning
  service if teachers share files.
- **SMS/WhatsApp marketing sends**: consent is recorded, but no marketing sender is built. Transactional
  WhatsApp uses the official Cloud API only.
- **CSP nonces**: scripts currently need `'unsafe-inline'` for Next.js inline scripts; move to nonces for a
  stricter policy.
- **Independent security review / penetration test**: recommended before launch. This document describes
  controls; it is not a compliance certification.

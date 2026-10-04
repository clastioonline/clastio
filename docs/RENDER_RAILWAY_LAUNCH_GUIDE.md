# Clastio: complete Render + Railway deployment guide

This guide matches this repository and the public domain `clastio.online`. The current API hostname supplied for this deployment is `clastio-production.up.railway.app`; use the actual public API hostname if it changes. Follow the steps in order. If a service already exists, configure that service rather than creating a second database accidentally.

This document is a deployment runbook. Writing it does not deploy code, create provider resources, update DNS or verify production credentials.

See [the latest launch audit](LAUNCH_AUDIT.md) for verified results and remaining release checks. The older launch review describes previous revisions and does not certify the current production deployment.

## 1. What runs where

```text
Teachers → https://clastio.online → Render Next.js web service
                                      │ /api/* proxy over HTTPS
                                      ▼
                            Railway API (FastAPI)
                              │        │        │
                           Postgres   Redis    Private R2 bucket
                           +pgvector           (uploads, PPTX, PDF, images)
                              ▲        ▲        ▲
                              └ Railway worker ─┘
                                Railway scheduler

Clerk: sign-in/sign-up         Resend: application email
Stripe OR Dodo: checkout, recurring billing and signed webhooks
Configured AI providers: text, vision, embeddings and optional generated images
```

Render does not connect directly to PostgreSQL. Railway's API, worker and scheduler share the same database, Redis, storage and application secret. Only the API needs a public domain; database, Redis, worker and scheduler can remain private. Keep the backend services and dependencies in the same Railway project/environment. Use the database's private network connection. [Railway pgvector deployment guidance](https://docs.railway.com/guides/embeddings-pipeline)

## 2. Publish the correct code revision

Use a GitHub repository and branch containing the latest local changes, including the favicon, launch pricing and new public pages. Connect Render and Railway to that branch. Review and commit your intended changes, then push them before deploying; dashboards cannot build changes that exist only in the local workspace.

Do not commit a real `.env` or credential file. The templates below contain placeholders:

- Frontend: `deploy/render-web.env.example`.
- Backend: `deploy/hosted-backend.env.example`.

Replace placeholders directly in hosting dashboards. Import the frontend template on Render and the backend template on Railway, not the reverse.

## 3. Create or confirm PostgreSQL with pgvector and Redis

In your Railway production project:

1. Add a **pgvector-enabled PostgreSQL** service/template if you do not already have one. Its database files need a persistent volume. Ordinary PostgreSQL images do not necessarily include the vector extension.
2. Add Redis if it does not already exist.
3. Wait for both services to run successfully.
4. Find PostgreSQL's private connection URL and Redis's `REDIS_URL` in their Variables/connection settings.
5. Enable database backups and test restoring to a separate database. Railway database templates require you to manage their configuration and maintenance. [Railway PostgreSQL documentation](https://docs.railway.com/databases/postgresql)

The app's initial migration runs `CREATE EXTENSION IF NOT EXISTS vector`. If it fails with an unavailable `vector.control` file, the database image lacks pgvector; retrying migrations will not install it. Choose a pgvector-enabled image/template or migrate the existing database deliberately. Do not delete an existing database to resolve this error.

### Database URL for this Python app

The application uses SQLAlchemy's asyncpg driver. Copy the PostgreSQL service's connection URL and change only `postgresql://` or `postgres://` to `postgresql+asyncpg://`:

```text
postgresql+asyncpg://USER:URL_ENCODED_PASSWORD@PRIVATE_HOST:5432/DATABASE
```

Preserve the actual user, encoded password, host, port and database. Do not use `localhost` or an HTTP URL. Do not blindly add another driver's SSL query parameters. The private hostname works from Railway runtime/pre-deploy containers, not from your laptop or Render.

For Redis, use a reference to the actual service:

```env
REDIS_URL=${{Redis.REDIS_URL}}
```

`Redis` is the service name in this example; replace it if yours differs. Railway supports reference variables so services can share dependency values. [Railway variable documentation](https://docs.railway.com/variables)

## 4. Create private object storage

Use the existing R2 bucket if correctly configured, or create a private bucket named `clastio` in Cloudflare R2.

Create R2 S3 credentials with Object Read & Write access scoped to that bucket. Copy the **Access Key ID**, **Secret Access Key**, and S3 endpoint. An ordinary Cloudflare account API token is not the same as the S3 secret key. The endpoint is `https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com`; the bucket name is a separate field. [Cloudflare R2 setup](https://developers.cloudflare.com/r2/get-started/s3/)

Set these on all three Railway application services:

```env
STORAGE_BACKEND=s3
S3_BUCKET=clastio
S3_REGION=auto
S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=YOUR_R2_S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY=YOUR_R2_S3_SECRET_ACCESS_KEY
SIGNED_URL_TTL_SECONDS=900
```

Keep the bucket private. The app authorises file access and issues signed URLs. Do not rely on separate local container disks: the API and worker must read the same uploaded files and generated exports. Verify an upload and a download after deployment.

## 5. Create the three Railway application services

Create three services from the same repository, or configure your existing services:

| Service | Repository root | Build | Public domain | Role |
| --- | --- | --- | --- | --- |
| API | `/apps/api` | Existing `Dockerfile` | Yes | Browser/API requests |
| Worker | `/apps/api` | Existing `Dockerfile` | No | PPT generation, rendering and other queued jobs |
| Scheduler | `/apps/api` | Existing `Dockerfile` | No | Email outbox, reminders, recovery and scheduled maintenance |

Railway should detect `apps/api/Dockerfile` after setting the root directory to `/apps/api`. Leave custom build commands empty. If using a custom Dockerfile path relative to that root, use `Dockerfile`, not `apps/api/Dockerfile`. The image installs LibreOffice and fonts required for PPT/PDF rendering.

If the log says Railpack cannot determine how to build the app, check the root and Dockerfile detection. [Railway monorepo instructions](https://docs.railway.com/deployments/monorepo)

### Shared backend variables

Import the backend template into the API, worker and scheduler, then replace its placeholders. All three need these values:

```env
ENVIRONMENT=production
PUBLIC_WEB_URL=https://clastio.online
CORS_ORIGINS=["https://clastio.online"]
COOKIE_SECURE=true
SECRET_KEY=YOUR_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
DATABASE_URL=postgresql+asyncpg://USER:URL_ENCODED_PASSWORD@PRIVATE_HOST:5432/DATABASE
REDIS_URL=${{Redis.REDIS_URL}}
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_S=30
RUN_JOBS_INLINE=false
SEED_DEMO=false
AI_OFFLINE_MODE=true
OPENVERSE_ENABLED=true
AI_MAX_CONCURRENCY=2
AI_GLOBAL_CONCURRENCY=4
LOG_LEVEL=INFO
```

Generate a secret once on your own machine, then store the same value on the three services:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Also import the storage settings from step 4 and the Clerk/Resend settings below. Do not regenerate `SECRET_KEY` on each deployment; changing it invalidates existing application sessions. Set `APP_VERSION` to a release identifier if you want health responses and logs to identify the deployed revision.

### API commands

Start Command:

```sh
sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --limit-concurrency 200'
```

Pre-deploy Command:

```sh
sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'
```

Healthcheck Path:

```text
/api/v1/ready
```

Run migrations on the API service only. Railway executes pre-deploy commands with the service's environment and private network access; a failed command blocks that deployment. [Railway pre-deploy documentation](https://docs.railway.com/deployments/pre-deploy-command)

Keep the explicit `sh -c` wrapper: both migration and seeding must run. Confirm seed output in the deployment logs; seeing only Alembic output does not establish that plans and templates were seeded.

The API image explicitly trusts Railway's `100.64.0.0/10` edge peers for forwarded HTTPS/client headers. After deployment, inspect API/security logs from two independent clients. If both resolve to Render's public egress IP, teacher IP limits are still shared and need authenticated frontend-to-API forwarding. Do not set `FORWARDED_ALLOW_IPS=*` or trust arbitrary public proxies. See [Railway edge networking](https://docs.railway.com/networking/edge-networking) and [Render proxy guidance](https://render.com/articles/fastapi-production-best-practices).

Generate/confirm the API's public HTTPS domain under Networking. For this deployment it is:

```text
https://clastio-production.up.railway.app
```

### Worker and scheduler commands

Worker Start Command:

```sh
python -m app.worker --concurrency 2 --no-scheduler
```

Scheduler Start Command:

```sh
python -m app.worker --scheduler-only
```

Deploy them after the API migration succeeds. Do not configure HTTP readiness probes on these background processes. Keep one dedicated scheduler instance. Start the worker with lower concurrency if its memory is insufficient for simultaneous LibreOffice jobs; test actual exports before increasing capacity. A successful API healthcheck does not prove a worker or scheduler is running.

The dedicated scheduler drains application emails. Running a worker with `--no-scheduler` alone is not enough to send emails or billing reminders.

## 6. Configure Clerk production authentication

Create/select a Clerk production instance for `clastio.online`. Complete the exact DNS records shown by Clerk and verify its domain. Enable your desired sign-in methods and verified email requirements. Use keys from the same production instance. [Clerk production deployment](https://clerk.com/docs/guides/development/deployment/production)

Configure sign-in/sign-up URLs as `/login` and `/signup` on `https://clastio.online`. Allow the app's production redirect URL `https://clastio.online/auth/clerk` where Clerk requires a redirect allowlist. The application sends Clerk sign-in completion to `/auth/clerk` and establishes an application session after verification.

On **Render**:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_YOUR_KEY
CLERK_SECRET_KEY=sk_live_YOUR_KEY
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/signup
```

On **Railway backend services**:

```env
CLERK_SECRET_KEY=sk_live_YOUR_KEY
CLERK_ISSUER=https://YOUR_PRODUCTION_CLERK_ISSUER
CLERK_JWT_KEY=YOUR_CLERK_RSA_PUBLIC_KEY_PEM
```

Copy the issuer and PEM from the production instance; do not assume the issuer from a guessed URL. Multiline PEM values and literal `\n` escapes are supported by this app. Never place a secret key in a variable beginning `NEXT_PUBLIC_`.

Existing app users should use the existing-account connection flow described in `deploy/HOSTED_SETUP.md`, rather than creating a second identity with unrelated account data. A Clerk webhook is not required for the current sign-in exchange; payment webhooks are a separate integration.

### First administrator: Clerk metadata only

In Clerk **Users → your verified owner → Public metadata**, set:

```json
{
  "role": "admin",
  "admin_role": "super_admin"
}
```

Save, then sign in through Clerk or refresh the application account. The backend reads this metadata directly from Clerk, persists the role, and bypasses teacher onboarding. Other supported `admin_role` values are `admin`, `support`, `analyst`, `finance`, and `moderator`; their landing pages follow their permissions.

With Clerk configured, `ADMIN_EMAILS`, local role edits, and database bootstrap edits do not establish staff access. Staff must have a Clerk-authenticated application session. Do not put privileges in `unsafe_metadata`, which is client-editable. Removing the trusted role in Clerk removes staff permissions on the next authenticated staff request.

## 7. Configure Resend email

Add `clastio.online` to Resend Domains, publish the exact SPF/DKIM records shown and wait for verification. Preserve existing mail-provider DNS records. [Resend domain instructions](https://resend.com/docs/dashboard/domains/introduction)

On Railway API, worker and scheduler:

```env
RESEND_API_KEY=YOUR_RESEND_KEY
EMAIL_FROM=Clastio <notifications@clastio.online>
EMAIL_FROM_BILLING=Clastio Billing <invoices@clastio.online>
EMAIL_FROM_ALERTS=Clastio Alerts <alerts@clastio.online>
EMAIL_FROM_NOTIFICATIONS=Clastio Notifications <notifications@clastio.online>
EMAIL_FROM_UPDATES=Clastio Updates <updates@clastio.online>
EMAIL_FROM_REMINDERS=Clastio Reminders <reminders@clastio.online>
```

Redeploy those services after changing environment values. Resend here sends application welcome/reminder/billing emails; Clerk's own authentication emails are configured in Clerk. Confirm the scheduler runs, a queued email becomes `sent`, and the test message is received. Without a verified sender domain and an active scheduler, the email pipeline is not ready.

Purpose-specific senders are optional and fall back to `EMAIL_FROM`. All sender addresses need a verified domain. Daily PPT-ready updates and review invitations follow teacher email preferences; promotional updates also require marketing consent. Without Resend/SMTP configured, production messages remain queued instead of being marked delivered.

## 8. Configure Render and the custom domain

Use a **Node Web Service** for the Next.js frontend. This app uses a server-side `/api` proxy; configure it as a web service, not a static-site export. [Render Next.js deployment](https://render.com/docs/deploy-nextjs-app)

| Setting | Value |
| --- | --- |
| Root Directory | `apps/web` |
| Build Command | `npm ci && npm run build` |
| Start Command | `npx next start --hostname 0.0.0.0 --port $PORT` |

Import `deploy/render-web.env.example`, including the Clerk values from step 6:

```env
NODE_ENV=production
NODE_VERSION=22
API_URL=https://clastio-production.up.railway.app
NEXT_PUBLIC_SITE_URL=https://clastio.online
```

`API_URL` is the API origin only: no `/api` suffix, no trailing slash, no Railway private hostname. PostgreSQL/Redis/R2/payment/AI credentials belong on Railway rather than the frontend. Clerk's Render secret is intentionally server-only.

Add/confirm `clastio.online` in Render's custom-domain settings. Follow the exact DNS records Render displays, then verify the domain and HTTPS. If using `www`, configure its DNS and redirect so the primary canonical domain remains `clastio.online`. [Render custom-domain instructions](https://render.com/docs/custom-domains)

Select **Save, rebuild, and deploy** after changing `API_URL`, the public Clerk key or site URL. A restart alone does not rebuild the Next.js proxy configuration or public browser variables. [Render environment instructions](https://render.com/docs/configure-environment-variables)

## 9. Verify connections before enabling paid generation

Open these two URLs:

```text
https://clastio-production.up.railway.app/api/v1/ready
https://clastio.online/api/v1/ready
```

Both must return HTTP 200 with `status: ready`, database `ok: true`, Redis `ok: true` and schema `ok: true`. AI mode may still be `offline` at this stage. `/api/v1/health` only checks process liveness.

Then verify:

- Teacher signup, verified sign-in, terms acceptance, onboarding and sign-out.
- Owner sign-in goes to `/admin`.
- Upload a source and a teacher image; download an authorised stored file.
- Create a small offline test lesson. Confirm the job moves from queued to succeeded, previews render and PPTX/PDF download.
- Confirm the scheduler sends an application email.

Offline output is labelled test/demo output. It is not evidence of live AI quality or live-provider availability.

## 10. Enable live AI deliberately

Configure the provider keys used by your chosen routes on Railway API/worker/scheduler: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and/or `GEMINI_API_KEY`. Choose actual model IDs available in your provider account; do not assume all source defaults are available to your account.

In **Admin → AI costs & model routing**:

1. Set planning, content, fast, vision, QC, embedding and image routes needed by the enabled features.
2. Approve current price cards and request ceilings for each model, including fallbacks.
3. Set daily/monthly platform, per-user, per-job and per-call spending controls.
4. Enable paid calls only after these are configured.

Set `AI_OFFLINE_MODE=false` on all three Railway application services and redeploy. Both live mode and the app's paid-call switch are required. Keep `EMBEDDING_DIM=1536` for the existing vector schema. Confirm the embedding route returns that dimension.

Keep `OPENVERSE_ENABLED=true` and the Openverse feature flag enabled for Hybrid/stock-only images. Hybrid searches licensed stock first; AI fallback still requires a valid image route, budget and image allowance. Test a small live lesson, inspect provider usage and measure the actual completed cost. See `docs/AI_COST_CONTROLS.md` for the detailed cost configuration; unknown/unapproved models are intentionally blocked.

## 11. Configure subscription payments

Choose **Stripe or Dodo** as the active gateway in app admin billing settings. Begin with test-mode credentials and test purchases; switch to live credentials/products/webhook secrets only when the entire checkout and webhook flow works. Stripe and Dodo IDs are separate and must not be mixed.

| Plan code | Name | Monthly AED | Annual AED |
| --- | --- | ---: | ---: |
| `teacher` | Teacher | 149 | 1,490 |
| `pro` | Teacher Pro | 249 | 2,490 |
| `assistant` | Genie Assistant | 399 | 3,990 |

For an existing database, apply these catalogue prices once in the deployed API environment:

```sh
python -m app.seed --skip-embeddings --update-plan-prices
```

Normal seeding does not overwrite old catalogue rows. This explicit flag updates paid prices only; existing subscriptions and limits are preserved. For a one-time rollout you can temporarily add the flag to the API pre-deploy seed command, then remove it. Do not leave it permanently if admins will customise prices later.

### Stripe

Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` on Railway backend services. Create AED recurring monthly/yearly prices, and set `STRIPE_PRICES` as JSON with the relevant `teacher_monthly`, `teacher_yearly`, `pro_monthly`, `pro_yearly`, `assistant_monthly` and `assistant_yearly` IDs. When there is no mapped price ID, the app uses its catalogue amount to create an inline recurring checkout price.

Register this HTTPS webhook endpoint with **snapshot** event payloads:

```text
https://clastio.online/api/v1/webhooks/stripe
```

Subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`. Include the asynchronous events when delayed payment methods are enabled. Expiry events clear confirmed expired checkout reservations. Copy the endpoint's own signing secret, not a local CLI listener secret. Enable the Stripe customer portal for payment management. [Stripe webhook instructions](https://docs.stripe.com/webhooks)

### Dodo

Set `DODO_PAYMENTS_API_KEY`, `DODO_PAYMENTS_WEBHOOK_KEY`, and `DODO_PAYMENTS_ENVIRONMENT=test_mode` or `live_mode`, matching the credentials/products. Create the six recurring AED products and map their IDs in `DODO_PRODUCTS` or app admin billing settings with `teacher_month`, `teacher_year`, `pro_month`, `pro_year`, `assistant_month`, and `assistant_year` keys. One-time media-credit packs need separate product IDs if enabled.

Register:

```text
https://clastio.online/api/v1/webhooks/dodo
```

Subscribe to `subscription.active`, `subscription.renewed`, `subscription.updated`, `subscription.plan_changed`, `subscription.on_hold`, `subscription.cancelled`, `subscription.expired`, `subscription.failed`, `payment.succeeded`, and `payment.failed`. Set the endpoint's signing secret in `DODO_PAYMENTS_WEBHOOK_KEY`. [Dodo webhook documentation](https://docs.dodopayments.com/developer-resources/webhooks)

### Payment verification

The app verifies mapped gateway amount/currency/billing frequency against the catalogue and rejects stale mappings with `billing_price_mismatch`. Dodo media packs also require the exact displayed AED price and a fixed one-time product. Configure the final tax treatment in the gateway and verify the final total. Test successful checkout, verified webhook receipt, plan activation, coupon application, cancellation and duplicate event delivery in test mode. Confirm a duplicate event does not create another payment/reward.

Subscription checkout persists one pending reservation per teacher and resumes its existing URL, even across repeated requests. Trials, licenses and manual grants cannot overlap a pending purchase. Stripe uses a stable idempotency key; provider-confirmed expiry releases the reservation. If Dodo might have created a checkout but its response was lost, staff must reconcile it with Dodo before releasing the hold. The app intentionally avoids a blind second purchase that could double-charge the teacher.

A browser return to the success URL alone does not prove a paid subscription was activated. Check the webhook and subscription state. Existing gateway subscriptions are not repriced by changing the catalogue. Keep historical provider products/mappings where existing renewals need them. See `docs/ENGAGEMENT_AND_BILLING.md` for fee scenarios and rollout details.

## 12. Trial, engagement and optional integrations

In **Admin → Plans & trial**, enable the seven-day trial and confirm finite credit/image allowances. New teachers begin on Free. They can explicitly choose Start free trial after verification, or remain on Free and start an eligible trial later from billing. No card is required for the trial; an active or unresolved paid subscription blocks overlapping grants. In admin settings, confirm referrals, reminders, feature flags and the active payment gateway. Payment reminders and email delivery require the scheduler. Referral rewards require a verified account and a qualifying signed paid-payment webhook.

WhatsApp is optional. If you want live WhatsApp, configure `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, and a non-default `WHATSAPP_VERIFY_TOKEN` on Railway. Configure the Meta webhook at `https://clastio.online/api/v1/webhooks/whatsapp`, the phone number, approved templates and messaging permissions for your Meta account. If not using WhatsApp, leave its provider credentials unset and do not promise live WhatsApp service. Its feature flag is not a global scheduler kill switch: the scheduler still runs its WhatsApp tick and processes any verified, opted-in contacts. Review existing opt-ins before launch. The current app still contains simulator/navigation surfaces; removing those pages or fully disabling scheduled WhatsApp work requires separate implementation.

Video generation, media-credit packs and other paid features should be enabled only with their provider routes, budgets and checkout products configured.

## 13. Final launch verification

Use separate owner/admin and teacher accounts. Complete this journey on the actual public domain:

1. Open the homepage, pricing, FAQ and one guide on mobile and desktop. Confirm new monthly prices, annual totals and a working `/favicon.ico`.
2. Create an eligible teacher account, confirm it starts on Free, explicitly start the trial, and confirm seven-day status and finite allowances. Confirm the Clerk administrator skips teacher onboarding.
3. Upload a source and image, discuss a lesson in the playground, approve the plan and generate a small live PPT.
4. Verify text, calculations, diagram details, sources, preview and editable PPTX/PDF downloads.
5. Make a manual correction, then an AI single-slide edit. Discuss an image change, review its brief and confirm one replacement. Check credit usage and memory consent.
6. Complete a gateway test purchase and check the signed webhook, active plan and payment record. Test a coupon and cancellation.
7. Confirm welcome/reminder emails and the scheduler logs. Check worker errors and provider spend.
8. Confirm another teacher cannot open your private lesson/file URLs. Enable database backups and verify a separate restore.
9. Open `/sitemap.xml` and `/robots.txt`. Verify Search Console/Bing ownership and submit `https://clastio.online/sitemap.xml` using your own accounts. Public guides support discovery; first-place ranking is not guaranteed.

Do not mark the app ready solely because the frontend loads or `/ready` succeeds: those checks do not exercise payments, workers, exports, email or live AI. This workspace's passing local tests use mocks for providers/payment checkout and do not substitute for this live journey.

## 14. Troubleshooting by symptom

| Symptom | What to check |
| --- | --- |
| Railway works, Clastio `/ready` fails | Render `API_URL`, public domain, exact origin and rebuild. |
| Both return `503 not_ready` | Railway database/Redis/schema checks and API deployment logs. A backend JSON response through Clastio proves the proxy is reaching the API. |
| Database `ok: false` | Correct asyncpg URL, running database, same environment, encoded credentials, migration/configuration errors. |
| Redis `ok: false` | Redis running; service reference and password; same environment/private network. |
| `vector` extension unavailable | PostgreSQL image lacks pgvector; choose a compatible image or migrate deliberately. |
| Railpack cannot build | Root `/apps/api`, Dockerfile detection and no doubled Dockerfile path. |
| Jobs stay queued | Worker running with the same database and correct code revision; queue logs. |
| Previews/export fail | Docker image with LibreOffice/fonts; worker memory; private R2 access; render logs. |
| Emails stay pending | Dedicated scheduler, verified Resend sender, correct key and delivery logs. |
| Clerk token/sign-in rejected | Same production instance keys, exact issuer/PEM, verified DNS, redirect origin and current API dependencies. |
| Paid AI is blocked or still demo | Live-mode env on API/workers, paid-call switch, approved model price cards, budgets and provider availability. |
| Checkout price mismatch | New catalogue price versus stale gateway product/price ID, AED currency and billing interval. |
| Payment succeeded but plan did not change | Correct test/live webhook endpoint secret, snapshot events for Stripe, delivery response and app payment/subscription logs. |
| `/favicon.ico` is 404 | Deploy the latest frontend commit containing `apps/web/app/favicon.ico`; confirm the deployed revision. |

## 15. Later deployments and rollback

Deploy the API migration before dependent workers. Keep the API/worker/scheduler on compatible code revisions. Rebuild Render when proxy/public configuration changes. After each release, verify readiness, one completed job, a download, sign-in and the scheduler.

Before a schema-changing release, take a database backup. Rolling back application code does not automatically roll back the database or gateway configuration; use a tested compatible release and a deliberate restore/migration plan. Monitor API/worker errors, queue delays, storage, database capacity, payment webhooks and AI spend. Size services from measured resource usage rather than a guessed user count.

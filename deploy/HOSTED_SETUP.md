# Render frontend + Railway backend

For the complete ordered launch procedure, see [the Render/Railway launch guide](../docs/RENDER_RAILWAY_LAUNCH_GUIDE.md). Check [the latest launch audit](../docs/LAUNCH_AUDIT.md) before opening paid registration.

These templates match the current code. They contain placeholders, not deployable credentials.

## Render frontend

Create a Node web service with root directory `apps/web`, build command `npm ci && npm run build`, and start command `npx next start --hostname 0.0.0.0 --port $PORT`. Import `render-web.env.example`; replace API_URL with the public HTTPS Railway API origin, without `/api` or a trailing slash. This URL must be reachable from Render; Railway private hostnames are not accessible across providers. Rebuild after changing API_URL because Next.js rewrites are built into the deployment. Attach `clastio.online` as a custom domain and follow Render's DNS instructions.

## Backend services

Use `apps/api/Dockerfile` for the API, worker and scheduler so LibreOffice and rendering dependencies are available. Import the same backend environment template into all three. Use the private PostgreSQL/Redis connection addresses when these services run together on Railway. The database must have pgvector available. URL-encode database credentials. The application uses asyncpg for DATABASE_URL; migrations derive a psycopg URL. Do not copy SSL query options for another driver blindly.

Run `sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'` once as the release/migration step before starting services. API command: `sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --limit-concurrency 200'`. API health path: `/api/v1/ready`. Worker command: `python -m app.worker --concurrency 2 --no-scheduler`. Scheduler command: `python -m app.worker --scheduler-only` (one instance). A small pilot can use one worker; this is not the previously described 100-user server capacity profile. Render background workers require paid hosting.

## Required values

- Actual API HTTPS hostname, database URL and Redis URL.
- A random application signing SECRET_KEY shared by API/worker/scheduler.
- R2 S3 Access Key ID and Secret Access Key scoped to the private `clastio` bucket. The supplied bucket URL is not an API key. The endpoint excludes `/clastio`; bucket name is separate. Keep the bucket private; the application checks file ownership and uses signed downloads.
- A Resend API key in RESEND_API_KEY and a verified EMAIL_FROM sender domain. The dedicated scheduler sends queued emails through the Resend API, with retries and an outbox ID as the idempotency key. SMTP_URL remains an optional fallback when RESEND_API_KEY is unset.
- Provider credentials and approved live AI configuration when moving out of offline test mode.

## Clerk production authentication

Create/select a Clerk **production** instance using `clastio.online` as its domain. Complete the exact DNS records Clerk shows, then verify the domain. Enable your desired sign-in methods and require verified email addresses. Use production `pk_live_...` and `sk_live_...` keys from that same instance.

In Clerk Paths, set sign-in to `https://clastio.online/login` and sign-up to `https://clastio.online/signup`.

On **Render**, import the updated `render-web.env.example`, replacing API_URL and both Clerk keys. CLERK_SECRET_KEY is server-only; never prefix it with NEXT_PUBLIC. Rebuild and redeploy the frontend.

On the **Railway API**, set CLERK_SECRET_KEY, CLERK_ISSUER (copy the issuer from the production instance, normally `https://clerk.clastio.online`), and CLERK_JWT_KEY (API Keys → Show JWT public key → PEM public key). Railway supports multiline values; literal `\n` escapes are also accepted. Never paste HTML escapes or a trailing backslash. Redeploy the API with the updated dependencies.

Clerk login redirects to `/auth/clerk`. The API verifies the RS256 signature, issuer, expiration and allowed origin, then reads the verified primary email from Clerk's server API. New users explicitly accept Clastio terms before provisioning. Clerk identities use the existing OAuth account table. Apply all current migrations for the separate license and billing features before starting the application. Staff roles come only from server-managed Clerk public metadata when Clerk is configured; the application enforces permissions and content ownership. Set the owner metadata to `{"role":"admin","admin_role":"super_admin"}` in Clerk, then sign in through Clerk. Staff skip teacher onboarding. `ADMIN_EMAILS` and local role edits do not establish Clerk staff access.

**Existing users:** choose “Sign in to an existing Clastio account”, sign in with the existing password, then complete Clerk sign-in with the same verified email. This connects identities only after proving access to the original account. Users without a password can establish their original application session using their existing Google/Microsoft provider from `/login?legacy=1`. After the legacy OAuth callback reaches the dashboard, revisit `/login` to connect Clerk. Already connected accounts sign in directly with Clerk.

The resulting application session retains the app's device list, suspension checks, revocation and expiry. Clerk logout also runs on app sign-out. Revoking a Clerk session alone does not revoke an already established application session; use Clastio's session controls to end it. Existing password/OAuth endpoints remain available for migration.

## Resend production emails

Add `clastio.online` in Resend Domains. Copy the exact SPF/DKIM and any other records from Resend into your DNS provider, then wait for **Verified**. Preserve existing mail-provider records; do not invent record values. Set `RESEND_API_KEY` and `EMAIL_FROM=Clastio <notifications@clastio.online>` on **Railway API, worker and scheduler**, and redeploy them. Do not put the Resend key in Render or a NEXT_PUBLIC variable. The dedicated scheduler (`python -m app.worker --scheduler-only`) is required to drain the email outbox; a worker using `--no-scheduler` does not drain it. Clerk's verification/password emails are configured in Clerk; RESEND_API_KEY here sends Clastio application emails.

After deployment, test a new signup, verified login, terms acceptance, onboarding, existing-account linking, app sign-out, and a queued welcome email. Confirm delivery in Resend and that the outbox row becomes `sent`. These steps require actual dashboard access and production credentials.

References: [Clerk Next.js setup](https://clerk.com/docs/getting-started/quickstart), [Clerk token verification](https://clerk.com/docs/guides/sessions/manual-jwt-verification), [Resend idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys).

WhatsApp credentials are omitted, but the simulator/navigation still exist. Removing those surfaces and disabling WhatsApp scheduling is separate code work, not an environment flag in the current version.

Rotate secret keys shared in chat; enter replacement secrets directly into provider dashboards. No secrets from chat have been copied into these templates. Configure backups, usage limits and actual deployment testing before opening registration.

Sources: [Render environment import](https://render.com/docs/configure-environment-variables), [Render port binding](https://render.com/docs/web-services), [Resend SMTP](https://www.resend.com/changelog/smtp-service).

## Railway build detection fix

If the build log says `Railpack could not determine how to build the app` and lists `apps/` at the top level, the service is analyzing the repository root. For each API/worker/scheduler service, set **Settings → Source → Root Directory** to `/apps/api`. Railway should then detect the existing `Dockerfile` automatically. Remove a custom Dockerfile path pointing to `apps/api/Dockerfile` when using this root; that would repeat the directory. Leave custom build commands empty and confirm the next log uses Docker instead of Railpack. Do not create a root `start.sh` for this issue: it would not install the rendering dependencies.

For the API set **Start Command** to `sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --limit-concurrency 200'`, and set **Pre-deploy Command** to `sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'`. Worker and scheduler start commands are listed above; run migration on the API service only. Save the settings and redeploy. This resolves the observed build-detection failure; actual connection credentials and runtime readiness must still pass afterward.

Reference: [Railway monorepo root directories](https://docs.railway.com/deployments/monorepo).

## Local validation of this change

Frontend production builds passed both without Clerk and with a synthetic Clerk publishable key (build only). Seven provider boundary tests passed: signature/issuer/origin/expiration/status checks and Resend payload/retry handling. Run `cd apps/api && python -m pytest unit_tests/test_provider_validation.py -q` for those tests. Database integration tests in `tests/test_clerk_resend.py` require a dedicated `_test` PostgreSQL database with pgvector; they could not run on the available local PostgreSQL installation. Live sign-in and delivery remain to be tested after keys and DNS are configured.

## Readiness fails after connecting Render to Railway

A response from `https://clastio.online/api/v1/ready` containing the backend's `status`, `version` and `checks` JSON confirms the Render proxy is reaching Railway. `503 not_ready` with database/Redis checks false means backend dependency readiness failed; changing CORS will not repair those connections. The database check also covers migration discovery, so check API logs to distinguish connection failures from migration/configuration failures.

1. Ensure PostgreSQL (with pgvector) and Redis are running in the same Railway environment as the API, worker and scheduler.
2. Set `DATABASE_URL` on each backend service from the PostgreSQL connection URL. Replace its `postgresql://` or `postgres://` scheme with `postgresql+asyncpg://` for this application's async driver. Preserve the URL-encoded credentials, host, port and database. Do not use localhost, placeholder values or Render's API_URL as database URLs.
3. Set `REDIS_URL` using a Railway reference to the actual Redis service, for example `${{Redis.REDIS_URL}}` if that service is named Redis. The API/worker/scheduler should reference the same Redis.
4. Run the existing API pre-deploy command `sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'`, then deploy the API and workers. If migration fails, fix the logged error before proceeding.
5. Compare `https://clastio-production.up.railway.app/api/v1/ready` with `https://clastio.online/api/v1/ready`. Both should return HTTP 200 with status ready. `/api/v1/health` is only liveness and does not prove dependencies work.

A missing `/favicon.ico` is separate from API readiness. The frontend now includes `apps/web/app/favicon.ico` from the existing Clastio logo; deploy the updated frontend to make it available.

## Launch prices on an existing Railway database

The code defaults are Teacher AED 149/month, Teacher Pro AED 249/month and Genie Assistant AED 399/month; yearly prices are AED 1,490 / 2,490 / 3,990. Ordinary seeding does not overwrite existing plans. After deploying the new API code, run `python -m app.seed --skip-embeddings --update-plan-prices` once in the Railway API environment to update only paid catalogue price fields. Keep existing limits and subscriptions. Align the Stripe price-ID or Dodo product mappings with the new recurring AED amounts before enabling new checkouts; mismatches are now refused. Existing provider subscriptions are not repriced by this command. See `docs/ENGAGEMENT_AND_BILLING.md` for the fee scenarios and full rollout details.

# Deployment

The cheapest production setup that works is one Linux VM running the Docker Compose stack behind a TLS reverse proxy. Everything in it (Postgres, the job queue, pgvector, file storage) scales out later without code changes.

## 1. Single server (recommended to start)

**Server:** 4 vCPU and 8 GB RAM (LibreOffice rendering is the memory-heavy part), 80 GB disk, Ubuntu 24.04, Docker Engine with the Compose plugin. Pick a region close to your teachers; for the UAE that is the Middle East regions of the major clouds (for example AWS me-central-1 or Azure UAE North), which also keeps personal data in-country.

```bash
git clone <this repo> ai-teacher-assistant && cd ai-teacher-assistant
cp .env.example .env
```

Edit `.env`. At minimum:

```ini
ENVIRONMENT=production
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
PUBLIC_WEB_URL=https://teach.example.com
COOKIE_SECURE=true
POSTGRES_PASSWORD=<long random password>
SEED_DEMO=false
ANTHROPIC_API_KEY=...          # and/or OPENAI_API_KEY, GEMINI_API_KEY
OPENAI_API_KEY=...             # default provider for embeddings and images
ADMIN_EMAILS=["you@example.com"]
# Keep the API off the public internet; only the web app is exposed through the proxy.
API_PORT=127.0.0.1:8000
WEB_PORT=127.0.0.1:3000
```

Start it:

```bash
docker compose up -d --build --wait
```

The `migrate` service applies database migrations and seeds plans, templates and curricula on every start, so upgrades are `git pull && docker compose up -d --build --wait`.

**TLS reverse proxy.** Put Caddy (automatic HTTPS) or nginx in front of the web app. Caddy example (`/etc/caddy/Caddyfile`):

```
teach.example.com {
    encode gzip
    reverse_proxy 127.0.0.1:3000
}
```

The proxy must set `X-Forwarded-For` to the client address (Caddy does by default; with nginx use `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`). The web app forwards it unchanged and the API trusts it only from private-network proxies (`FORWARDED_ALLOW_IPS`, set in the API image). This is what makes per-IP rate limits and the audit log see real client addresses. Set generous proxy timeouts (≥ 120 s) and turn off response buffering for `/api/v1/jobs/*/events` and `/api/v1/assistant/messages` so server-sent events stream.

Sign up with an address listed in `ADMIN_EMAILS` to get the admin role.

## 2. Configure integrations

Everything below is optional. Each integration switches on as soon as its credentials are present.

### AI providers
Add keys for the providers you want. The defaults route planning to `claude-opus-5`, writing and QC to `claude-sonnet-5` and `claude-haiku-4-5`, and embeddings and images to OpenAI. Change routing in **Admin → AI costs** without a redeploy; the same page shows spend per model and per task. Keep `EMBEDDING_DIM` at 1536 unless you also migrate the vector columns.

### Dodo Payments (recommended for the UAE and India)
Dodo Payments is a merchant of record: it charges customers, handles VAT/GST and supports cards, UPI and local methods. When both gateways are configured, **Admin → Payments & media** decides which one checkout uses ("Automatic" prefers Dodo).

1. In the Dodo dashboard, create an API key (Developer → API keys) and set `DODO_PAYMENTS_API_KEY`. Use `DODO_PAYMENTS_ENVIRONMENT=test_mode` with test keys and `live_mode` with live keys.
2. Add a webhook endpoint `https://teach.example.com/api/v1/webhooks/dodo` and set its signing secret as `DODO_PAYMENTS_WEBHOOK_KEY`. Subscribe to `subscription.active`, `subscription.renewed`, `subscription.updated`, `subscription.plan_changed`, `subscription.on_hold`, `subscription.cancelled`, `subscription.expired`, `subscription.failed`, `payment.succeeded` and `payment.failed`. Signatures are verified with Standard Webhooks, and repeat deliveries are ignored.
3. Create products:
   - one **subscription** product per paid plan and interval (Teacher, Teacher Pro, AI Teaching Assistant × monthly/yearly), priced in the dashboard;
   - one **one-time** product per media credit pack (Starter, Creator, Studio by default).
4. Paste the product ids (`pdt_…`) into **Admin → Payments & media**: plan products under "Dodo product ids for plans", pack products in each pack row. A plan or pack without a product id is not offered for online payment.

The customer portal (the "Manage payment" button) and cancellation at the end of the period work through the Dodo API.

### Stripe (alternative)
1. Create products and monthly/annual prices for the paid plans. Put their ids in `STRIPE_PRICES`, e.g. `{"teacher_monthly":"price_…","pro_monthly":"price_…","assistant_monthly":"price_…"}`.
2. Add a webhook endpoint `https://teach.example.com/api/v1/webhooks/stripe` for `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Put its signing secret in `STRIPE_WEBHOOK_SECRET`.
3. Enable the Customer Portal in the Stripe dashboard (used by "Manage payment" on the billing page).

Media packs sold through Stripe use each pack's AED price from the admin page. Plan limits and prices shown in the app are rows in the `plans` table, so change them there, not in code.

### Media studio (paid add-on)
Teachers generate images and short videos on the **Media studio** page, paid with *media credits*, a wallet separate from lesson credits. Everything is set in **Admin → Payments & media**: on/off, credits per image and per video second, allowed video lengths, styles, the image and video models, credit packs and their prices, and manual credit grants (audit-logged). A plan can also include a monthly allowance through its `media_credits_monthly` limit.

- Images use the image tier (OpenAI `gpt-image-1-mini` by default, Gemini as fallback); videos use `MODEL_VIDEO` (OpenAI `sora-2` by default, or Gemini Veo). Both need the matching provider key; without one, the studio produces labelled demo placeholders.
- Credits are charged when a request starts and refunded automatically if generation fails or the provider declines it.
- Files are stored exactly as the provider returns them, so embedded provenance data (such as C2PA content credentials) is kept. Items are labelled "AI-generated" in the app and in their download names.

### WhatsApp (official Cloud API only)
1. In Meta for Developers, create an app with the WhatsApp product, add and verify the business phone number, and create a permanent system-user token. Set `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_APP_SECRET`.
2. Webhook URL: `https://teach.example.com/api/v1/webhooks/whatsapp`, verify token = `WHATSAPP_VERIFY_TOKEN`; subscribe to the `messages` field.
3. Submit the utility templates `daily_plan_morning` and `reflection_checkin` for approval, with the bodies in `apps/api/app/services/whatsapp.py`. (`tomorrow_ready` and `job_complete` are defined there too but not sent yet.)

Teachers link their number from the WhatsApp page with a one-time `LINK <code>` message. The worker sends morning plans and after-class check-ins at each teacher's local time, outside quiet hours.

### Sign-in and email
- Google / Microsoft: create OAuth clients with redirect URI `https://teach.example.com/api/v1/auth/oauth/google/callback` (or `…/microsoft/callback`) and set the client id and secret.
- Email (magic links, notices): set `SMTP_URL`. Without it, links are written to the API log.

### File storage
Local storage lives in the `storage` Docker volume. For anything beyond one server, use S3-compatible storage (AWS S3, Cloudflare R2, MinIO): `STORAGE_BACKEND=s3` plus the `S3_*` settings. Downloads are always short-lived signed URLs.

## 3. Operations

- **Health:** `GET /api/v1/health` reports the database and AI mode. Compose health checks use it.
- **Logs:** JSON lines with `request_id` and `job_id` (`docker compose logs -f api worker`). Set `SENTRY_DSN` for error tracking.
- **Backups:** nightly `docker compose exec -T db pg_dump -U postgres -Fc teacher_assistant > backup-$(date +%F).dump`, copied off the server, plus the `storage` volume (or bucket versioning on S3). Test a restore before you need one.
- **Jobs:** failed jobs keep their error, and teachers can rebuild a failed lesson from the project page. Admin shows job and AI-call failure counts.
- **Data requests:** teachers export or delete their own data from Settings (UAE PDPL, India DPDP).

## 4. Scaling out

| Pressure | Change |
|---|---|
| More teachers generating at once | Add worker replicas (`docker compose up -d --scale worker=3`) or dedicated workers per queue: `--queues ai`, `--queues render,docs`. The morning-message scheduler is safe to run in several workers because an advisory lock serialises it. |
| Several API instances | Stateless: run more behind the proxy and set `REDIS_URL` so rate limits are shared. |
| Database | Move to managed Postgres 16 with the `vector` extension (RDS, Cloud SQL, Azure Flexible Server, Neon, Supabase). Point `DATABASE_URL` at it. |
| Files | S3-compatible storage as above; required once API and workers run on different machines. |
| Cost | Watch Admin → AI costs. Cheaper routing (for example the `content` tier on a smaller model) is a settings change. |

## 5. Security checklist

- [ ] `ENVIRONMENT=production` with a random `SECRET_KEY` of at least 32 characters (the API refuses to start otherwise)
- [ ] HTTPS only, `COOKIE_SECURE=true`, API and database ports not exposed publicly
- [ ] `SEED_DEMO=false` (demo accounts are never created in production anyway)
- [ ] Strong `POSTGRES_PASSWORD`; backups encrypted and stored off the server
- [ ] Stripe and WhatsApp webhook secrets set (unsigned webhooks are rejected)
- [ ] Optional: ClamAV (`CLAMD_HOST`) for upload scanning
- [ ] Provider keys only in `.env` on the server, never in the web app or the repository

# Clastio production setup

Domain: `clastio.online`. Configuration is prepared locally; DNS and public deployment have not been changed.

## Walkthrough

The compass button in the signed-in header opens a page guide or the complete tour. Teachers get 18 steps, administrators get up to nine according to their permissions. Lesson pages explain the manual editor and after-class reflection. Pause/resume is stored on that browser separately for each account; finishing returns to the page where the tour started. Tutorials & help can also start the complete tour. The guide never clicks generation, billing or messaging actions.

## Capacity profile

The production override uses two API processes, two worker containers with two job slots each, and one scheduler. PostgreSQL pools are bounded per process. Redis coordinates a global maximum of eight live provider calls, with renewable leases and cleanup after cancellation. Workers update job heartbeats; claiming a job serializes the brief owner-capacity check so competing workers cannot exceed that owner's limit. Password hashing runs on a bounded thread pool. Structured AI results are cached in Redis across processes.

This supports a queue for many teachers, rather than rendering 100 presentations simultaneously. It is a starting configuration, not a measured throughput guarantee. An initial server estimate is 8 vCPU / 16 GB RAM, SSD storage; measure the actual deployment before admitting 100 active teachers. Model latency, slide count, LibreOffice rendering and image generation affect waiting times. The single-host storage volume must be backed up; moving to several hosts requires shared object storage.

Existing abuse limits remain unchanged: 300 requests/minute per IP, plus route/user limits. A school sharing one public IP can hit these limits. Do not raise them without reviewing the intended traffic and abuse exposure.

The concurrent-user regression exercises 100 distinct signed-in sessions and 200 authenticated requests against real PostgreSQL using the offline ASGI application. It does not measure HTTPS, networking, multiple API processes, real provider response times or 100 simultaneous PPT jobs. Separate dedicated Redis tests check real Lua acquisition, lease renewal, cancellation cleanup and fail-closed behavior.

## Prepare the server

1. Install Docker Engine with Compose >= 2.24.4. Allow public ports 80/443, restrict administrative access, and keep database/Redis private.
2. Copy `deploy/production.env.example` to `.env.production`. Set `APP_ENV_FILE=.env.production`, `APP_DOMAIN=clastio.online`, unique random `SECRET_KEY`, a strong PostgreSQL password and the required provider/email credentials. Do not copy development/demo credentials. Keep this file private and outside version control.
3. Point the domain's A record to the server. Add AAAA only if working IPv6 is configured. Caddy obtains HTTPS certificates once DNS points to this server and ports 80/443 are reachable.
4. Review the effective configuration without printing secrets:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.production.yml config --quiet
   ```

5. After deployment approval, build/start the reviewed stack:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.production.yml up -d --build
   ```

Migrations seed platform configuration without demo accounts or paid embeddings. Live AI still needs approved model pricing, spending budgets, feature flags and provider credentials. A Gemini key is optional if another configured provider supplies images.

## Before opening registrations

Verify domain/HTTPS, administrator bootstrap, email delivery, password reset, payment sandbox webhooks and enabled integrations. Run a real-provider lesson/image acceptance review with an explicitly approved budget. Measure 100-user traffic on the actual server, including job queue depth, p95 response latency, memory, CPU, database connections and paid-call concurrency. Add external uptime/error monitoring and disk alerts.

Back up PostgreSQL and the storage volume on a schedule to a separate destination, protect/encrypt backups, and test restoration in a separate environment. Redis persistence preserves shared coordination/cache across normal restarts but is not a substitute for database backups. Check worker shutdown/recovery during a queued generation batch. Never test destructive restore commands against production.

Reference: [Uvicorn deployment controls](https://www.uvicorn.org/settings/) and [SQLAlchemy connection pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html).

## Suggested hosting

For the initial single-host deployment, use Hetzner Cloud in Singapore with an x86 Linux server, Ubuntu 24.04 LTS, at least 8 vCPU / 16 GB RAM and 160 GB SSD, plus separate backups. This size is an engineering starting estimate; actual 100-user throughput needs a server benchmark. Shared CPU is suitable for a pilot; dedicated CPU gives steadier rendering capacity when generation remains busy. Check the selected region's current price and traffic allowance before buying. Provider source: [Hetzner Singapore](https://www.hetzner.com/cloud-singapore/). No hosting purchase has been made.

The production web build uses Next.js's documented webpack option; the local Turbopack build failed while binding a processing port. The webpack production build and TypeScript validation passed.

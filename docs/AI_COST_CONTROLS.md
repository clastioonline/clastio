# AI cost controls and launch configuration

The app now has two independent controls: teacher plan credits and a USD admission ledger for provider calls. Administrators are subject to USD limits too. Offline generation does not contact paid providers or consume a USD reservation.

## Before enabling paid AI

1. Run `alembic upgrade head` with the release, then restart the API and workers. The migration adds a reservation ledger and a link to usage reports; existing resources and credit history are preserved.
2. Configure provider keys on the server. Keep `AI_OFFLINE_MODE=true` for local/offline testing. To run live, use `AI_OFFLINE_MODE=false` and enable paid calls in **Admin → AI costs & model routing → AI spending controls**. Both switches are required; enabling the admin switch cannot override offline mode.
3. Configure exact `provider:model` routes and approve a price card for every model that may be tried, including fallback models and embeddings. Unknown models are blocked. Existing legacy price estimates do **not** authorize spending.
4. Enter current account-specific prices, pricing source, and a conservative `ceiling_usd` for each allowed request. Token fields `input`, `output`, `cached`, `cache_write` are USD per million tokens. Include reasoning, cache-write duration, long-context premiums and allowed image/video options when determining ceilings. The single cache-write rate must cover the cache lifetime used by the adapter. Media retains its ceiling pending invoice reconciliation.
5. Set daily/monthly platform, monthly user, per-job and per-call USD limits. Defaults are deliberately conservative: $10/day, $100/month, $5/user/month, $2/job and $1/call. These are starting policy values, not pricing or profitability forecasts. Input defaults to 120,000 bytes (including images/schema); output is capped at 24,000 tokens. Adjust for your tested document and vision workloads. Each job allows at most 60 provider attempts, including retries across workers.
6. Run a small explicitly authorized live benchmark, compare the ledger with provider billing, and measure quality and cost per completed lesson before raising quotas. No paid benchmark was run as part of this implementation.

## How spending is enforced

Every live call acquires a durable reservation before contacting the provider. PostgreSQL serializes admission across API and worker processes, so simultaneous requests cannot each spend the same remaining allowance. The reservation uses the approved per-call ceiling. Actual reported token cost releases the unused amount when the call finishes. Pricing is snapshotted per call so later edits cannot change historical charges.

If the connection is interrupted, final usage is missing, or media billing cannot be calculated from token rates, the full reservation remains held. Holds carry forward across UTC day/month boundaries. A worker retry cannot silently repeat a job with an unresolved charge from an earlier attempt. Administrators reconcile these calls against an invoice/provider request reference; active jobs cannot be reconciled and unfinished calls must be at least 24 hours old. Adjustments are audited and update linked usage reports.

This enforces admission against configured ceilings, not a contractual provider billing cap. A ceiling or price card that understates provider charges can still produce an overrun on an already-admitted call. A reported charge above its ceiling automatically pauses new paid calls. Provider invoices remain authoritative. Existing historical usage is shown in the older reports; the new admission ledger starts when installed.

## Waste reduction and user experience

- At most two provider attempts per text/structured/embedding/media operation; one attempt per stream. SDK generation retries and Anthropic server-side fallback are disabled. Video status polling is still needed to retrieve an existing generation.
- Unknown charges and refusals do not trigger automatic retries. Failed validation/truncated responses retain reported token usage. Output limits are never doubled automatically.
- Offline output is only returned in explicitly configured offline mode. Provider outages in live mode surface as errors, rather than substitute demonstration content.
- Structured caching includes the user, provider, model, schema, prompt version, effort, token limit, image hashes and offline context. Calls without a user do not share cached answers. Course plans and lesson decks opt into result caching. Entries expire after 24 hours. With REDIS_URL configured, results are shared across API/worker processes; otherwise a bounded process-local cache is used. Redis failures fall back to normal generation. This reuses application results rather than providing a provider batch discount.
- Course and assessment forms show server-configured credit estimates and available credits. Course estimates account for planning-only versus slide generation. Course forms show the billing reset date. Existing job reservations, refunds and background progress remain in use.
- Admin monitoring separates settled spending, unresolved holds, remaining budget, forecast, failed-call cost, input/output, cache reads/writes and reasoning tokens. Reasoning is a breakdown of output tokens, not a second charge. An 80% threshold shows a dashboard warning. Forecast excludes unresolved holds.

The API exposes `GET /admin/ai-budget`, audited `POST /admin/ai-budget/{call_id}/reconcile`, and teacher-facing `GET /usage/estimates`. Budget editing and reconciliation require `settings.modify`; viewing the ledger requires `api_usage.view`.

## Provider reference

The OpenAI adapter requests final streaming usage and retains holds if it is missing. OpenAI documents that interrupted streams may omit that final usage chunk: [Chat Completions reference](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create). Reasoning is tracked within completion/output totals: [Counting tokens](https://developers.openai.com/api/docs/guides/token-counting).

Automatic provider invoice imports, provider batch submission and account-specific price synchronization are not implemented. Reconciliation is explicit and manual, and paid services remain disabled until configured.

## Validation commands

- Backend: `ruff check app tests` and `python -m pytest -q` from `apps/api`, against a dedicated PostgreSQL database ending in `_test` (the fixture deletes its tables).
- Web: `npm run build` and `npm test` from `apps/web`.
- Browser: `BASE_URL=http://localhost:3008 CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run e2e:ai-budget` from `apps/web`. This checks admin layouts and teacher estimates without enabling paid calls or changing budgets. Use the other `e2e` scripts for complete generation and admin regression checks.
- Deployment schema: `alembic check` after `alembic upgrade head`.


## Teaching scope and lower-cost visuals

The shared web/WhatsApp conversation service checks teaching relevance before running actions, retrieving context or streaming a response. Clear personal requests and greetings receive a local redirect without an AI call. Other messages use the fast-tier intent classifier with teaching, out_of_scope and needs_context relevance. Unrelated or unclear requests receive a classroom-focused redirect; classifier failures also redirect. The response system prompt reinforces this scope, and chat output is capped at 1,500 tokens. Educational subject explanations remain allowed. Ambiguous messages should include a topic or grade. Semantic classification can make mistakes; this is a product boundary rather than a guarantee of detecting every adversarial request.

Charts use editable native PowerPoint bar, line or pie charts with an embedded spreadsheet, units and a source label. Category/series lengths, finite numbers and pie totals are validated. Prompts require supplied/verified data and explicitly labelled classroom examples. Tables, counting diagrams and uploaded images remain reusable without image-generation calls. Long uploaded decks send relevant text snippets plus opening goals and closing checks; reference JSON is compact and limited at complete page boundaries. Source image sheets remain included when interpretation requires them.

No paid live calls validated this update. Batch processing and a compact replacement for the full slide response schema remain future work.

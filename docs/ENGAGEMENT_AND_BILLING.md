# Trial, referrals, coupons, and payment reminders

These changes are local. Redeploy the Render frontend and Railway API, worker, and scheduler to activate them. Referral attribution uses existing user fields, but licenses and durable checkout tracking require the latest migrations through `e205checkout01`.

For the current release evidence and production gates, see [the launch audit](LAUNCH_AUDIT.md).

## Free trials

New teachers start on Free and explicitly choose their eligible trial; signup does not start it automatically. When enabled by an administrator, the trial defaults to 7 days of Pro features with no card required. The new allowance defaults are **50 lesson credits, 5 AI images, and 20 WhatsApp messages for the entire trial**. Limits never exceed the corresponding paid-plan allowance. They are enforced by the same server checks and queued-job reservations as paid-plan limits. Trial expiry returns users to Free automatically; existing content remains accessible. One trial per normalized email is still enforced.

Administrators can adjust duration and allowances in `/admin/plans`. Duration affects new trials; allowance changes affect active trials too. Trial days remaining use rounding up, so a partial day does not appear as an ended trial. The app banner, Plan & billing, and public pricing display the allowance. Existing usage warnings use the trial allowance and now explain trial exhaustion rather than promising a monthly reset.

## Referrals

Teachers can copy or share an invite link in `/billing`. New signups attribute the link through password signup, Clerk signup, or legacy Google/Microsoft signup. The invite is remembered for the browser session. Existing accounts cannot attach a referrer retrospectively. Self-referral and matching normalized emails are rejected.

After the referred teacher has a verified email and a positive subscription payment confirmed by a signature-verified Stripe or Dodo webhook, both teachers receive **25 media credits** by default. Credits are usable in Media studio and are separate from lesson credits. Zero-value invoices and media-pack purchases do not qualify. Suspended and admin accounts are excluded. A transaction lock and ledger check grant one reward per referred account even across repeated payment events. Reward notifications respect the existing billing preferences.

Administrators can enable/disable referrals and change the reward in `/admin/settings`. Changes apply to future awards. The billing page shows joined accounts, qualified accounts, earned media credits, and completed-task milestones, without exposing invitees' personal details. Awards are not automatically clawed back after later refunds; staff can adjust media credits using existing controls.

## Coupon codes

Create coupons in the active payment provider's dashboard. Configure expiration, eligible products, redemption caps, customer restrictions, and duration there. The application does not invent discounts or adjust payment amounts locally.

Teachers enter a code before choosing a plan. Stripe resolves the active promotion code and supplies it to Checkout without the conflicting `allow_promotion_codes` flag. Dodo receives `discount_codes` and enables its hosted discount field. The provider applies its eligibility rules and shows the final total. Invalid or ineligible codes produce an error; users can edit or remove the code. Provider discounts are also available in hosted checkout.

References: [Stripe Checkout discounts](https://docs.stripe.com/payments/checkout/discounts), [Dodo Checkout integration](https://github.com/dodopayments/skills/blob/main/dodo-payments/checkout-integration/SKILL.md).

## Reminders

Existing trial-ending reminders run at 3 days and 1 day, followed by an expiry notice. Upcoming monthly renewals are announced within 3 days and annual renewals within 7 days. Cancelled and school-granted plans also receive expiry notices. Failed-payment follow-ups now run at 1, 3, and 7 days, with deduplication scoped to the subscription period. Failed-payment alerts are mandatory; ordinary billing reminders follow notification preferences. The dedicated scheduler runs reminders hourly and drains queued email through Resend/SMTP. These services must be running for emails to arrive.

## Validation and launch checks

- Production frontend build passed.
- 18 provider/engagement unit tests passed, including trial caps and reservations, duplicate/self-referral prevention, setting validation, and Stripe/Dodo coupon payloads.
- Mocked browser checks passed for trial usage, referral/progress panels, coupon submission/error handling, and mobile/desktop layouts.
- Database integration remains unverified locally because the available PostgreSQL setup lacks the application's dedicated test database and pgvector. Unit and browser checks do not substitute for live signed-webhook testing.

Commands: `cd apps/api && python -m pytest unit_tests/test_engagement.py unit_tests/test_provider_validation.py -q`; start the web app on port 3100, then `cd apps/web && node e2e/engagement.mjs` (set CHROME if needed).

Before production launch, test a referral signup and first paid subscription in the gateway sandbox, repeat the webhook to confirm one award, confirm both media balances and notification preferences, test valid/expired/ineligible coupons, exhaust trial credits with concurrent queued jobs, and check scheduler/Resend delivery. Use the gateway's sandbox/test mode for payment verification.


## Natural classroom PPTs with stock photos

New lessons in the web app have an **AI / Humanize** button toggle, defaulting to **Humanize**. Humanize selects natural teacher wording; AI selects standard lesson wording. The independent image selector defaults to Hybrid, with stock-only and AI options available. The writing instructions request concrete examples, varied explanations and layouts, practical speaker notes, and age-appropriate language without inventing personal experiences or statistics. The existing deck-generation call handles this style; no separate paid rewriting pass is added.

Teachers can additionally select their own uploaded photos in stock mode. Stock mode searches Openverse for CC0, public-domain, and CC BY images, stores attribution and source links, and includes credits in slide notes. It disables paid image generation, excludes cached AI assets and template source-image reuse from the image resolver, and keeps these rules when slides are rerendered. If a suitable stock image is unavailable or invalid, it uses a text slide with a note for the teacher, rather than generating an image or placeholder. Editable diagrams/charts remain available.

Set `OPENVERSE_ENABLED=true` on the Railway API and workers and enable the Openverse feature flag in admin settings. The backend environment example now enables it. Redeploy the API/workers and Render frontend. Existing courses retain their saved image choices.

API clients can use `POST /api/v1/courses` with `writing_style: "natural"` and `image_mode: "stock"`. Direct API calls retain the existing defaults unless these options are supplied.

This improves writing quality and avoids image-generation charges. It does not guarantee a classification from Panogram or any other AI detector. Text generation still uses AI and incurs its normal token charges. Openverse search and fallback behavior were tested with mocked responses; production retrieval still needs a live check.


## Hybrid images and PPT playground

New web courses default to `image_mode: "hybrid"`. The resolver reuses uploaded source visuals or cached licensed Openverse assets, searches licensed Openverse images (including diagram queries), then generates when no matching downloadable image is found and AI allowance is available. Cached AI assets do not bypass the search. Attribution remains in slide notes. If the provider or allowance is unavailable, the existing placeholder fallback applies. Search uses query/size/license matching, not an independent semantic or scientific accuracy verification; teachers should review visuals. Stock-only continues to prohibit paid image generation.

Open **PPT playground** in the assistant or from New chapter (`/assistant?mode=playground`). Conversations persist with `channel=playground` in the existing table; no database migration is required. Queued replies use the existing assistant worker, limits and provider cost tracking. Planning mode bypasses executable intent routing, asks focused questions, and saves a validated draft only once topic, grade, subject and learning goals are clear. Teacher context and available indexed source context inform the discussion. Offline/demo mode explicitly asks for details rather than inventing a completed brief.

**Review PPT draft** transfers the latest assistant brief into New chapter, including lesson count, slides, duration, language, style and content instructions. The teacher can attach sources and edit the settings. Automatic generation is off for this handoff, so the teacher reviews the chapter plan before building lessons. Subsequent corrections should be discussed in the playground before reopening Review draft. Planning conversation tokens still have normal AI costs.

Verification: `cd apps/api && ./.venv312/bin/python -m pytest unit_tests/test_playground.py unit_tests/test_stock_presentations.py -q`; frontend typecheck and production build. External Openverse and production AI availability require deployment checks. Deploy both the Railway API/workers and Render frontend with Openverse enabled.


## Teacher-provided images

New chapter now includes **Your images**: upload up to five PNG, JPEG or WebP images and describe their content or intended placement. The existing `/slide-images` endpoint verifies format, dimensions, upload size and storage allowance. Selection and captions are saved in course options; the API rejects images owned by another user or non-upload assets. Course planning and slide generation receive the image catalog, captions and the actual image references. The model is instructed to prefer relevant supplied images via exact catalog keys; irrelevant images need not appear.

Supplied pictures precede internet search and generation in Hybrid, AI and stock-only modes and use no AI image-generation allowance. Standard content/vision token costs and storage still apply. For exact placement, teachers can upload or replace an image in the existing slide editor. Uploaded images also remain available on rebuilds in stock mode. Removing an image from the chapter selection does not delete its stored asset.

Verification: `cd apps/api && ./.venv312/bin/python -m pytest unit_tests/test_teacher_images.py unit_tests/test_stock_presentations.py unit_tests/test_playground.py -q`, frontend typecheck and production build. Redeploy Railway API/workers and Render frontend; no migration is required.

## Editing PPTs without regenerating everything

Use the slide editor for small changes. Manual text, layout, timing and uploaded-image edits, and restoring a previous slide version, consume **0 generation credits**. The PPT/PDF is rendered again without an AI rewrite. AI quick actions or custom instructions rewrite only the selected slide, at the admin-configured `credit_costs.slide` rate (default 1); a complete lesson rebuild uses that rate times the lesson's slide count. Both costs are now displayed before the teacher starts.

**Keep existing images** is on by default for AI slide rewrites. The backend preserves the complete visual, asset reference and sources even if the model tries to replace them. Disable it when changing the visual structure, or use the manual image uploader for precise replacements. These edit rebuilds do not request paid AI image generation. Selected chapter sources inform the rewrite for consistency. Only one update runs on a lesson at a time; identical pending slide requests return the existing job, and conflicting changes are blocked. Frontend controls are disabled while an update runs.

If the validated/budgeted rewrite is identical to the original, the worker returns without rerendering or consuming credits. Changed slides are charged the cost reserved at submission, after output saves successfully. User-specific rewrite caching avoids repeated identical provider calls when the input/context is unchanged. Slide-edit jobs make one worker attempt, avoiding repeated paid rewrites if rendering fails; the teacher can retry after failure. Provider tokens may still be incurred for an unchanged result; 0 teacher credits does not mean 0 infrastructure cost.

Suggested teacher instruction: “Slide 4 only: shorten the explanation to three bullets, keep the example and image, and move the detail to speaker notes.” Combine related changes into one instruction rather than requesting repeated rewrites. Review the updated slide and use version restore for undo. Full lesson rebuilds are appropriate when the topic, grade or lesson sequence changes substantially.

Verification: `cd apps/api && ./.venv312/bin/python -m pytest unit_tests/test_efficient_edits.py unit_tests/test_teacher_images.py unit_tests/test_stock_presentations.py unit_tests/test_playground.py -q`, frontend typecheck and production build. Database locking tests use mocked sessions here; production workers and concurrent requests need a deployment smoke test.

## Launch catalogue: AED 149 / 249 / 399

Monthly launch prices (before checkout taxes) are Teacher AED 149, Teacher Pro AED 249 and Genie Assistant AED 399. Annual prices remain ten monthly payments: AED 1,490 / 2,490 / 3,990 for twelve months. The Free plan, seven-day trial and existing credit/image/class/storage limits are retained. Credits measure usage, not a promise of unlimited-length PPTs. The current rates in the app determine actual generation estimates.

| Plan | Monthly price | Annual price | Monthly credits | AI-image allowance | After a 2% fee | After a 5% fee |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Teacher | AED 149 | AED 1,490 | 800 | 30 | AED 146.02 | AED 141.55 |
| Teacher Pro | AED 249 | AED 2,490 | 2,000 | 100 | AED 244.02 | AED 236.55 |
| Genie Assistant | AED 399 | AED 3,990 | 4,000 | 200 | AED 391.02 | AED 379.05 |

Fee columns are arithmetic scenarios on the base subscription price, not profit or a gateway quote. They exclude fixed transaction charges, payment fees on tax-inclusive totals, tax, FX, refunds, billing add-ons, AI generation, infrastructure, trial usage, coupons and marketing. Stripe's published UAE standard card fee is 2.9% + AED 1, with additional charges possible: https://stripe.com/ae/pricing . Use the actual contracted gateway fee in the business model. Do not assume a plan is profitable merely because its subscription price increased.

A practical contribution calculation is: base subscription revenue minus actual gateway charges, per-customer AI usage, allocated hosting/support and discount/refund costs. Marketing acquisition cost should be assessed against the number of paid months a customer stays, rather than charged entirely against every month's recurring revenue. Measure real usage and conversion before changing limits or adding discounts.

### Roll out to an existing deployment

Normal seeding still preserves existing admin-edited plans. Deploy the API code, then run this explicit catalogue update once in the Railway API environment:

```sh
python -m app.seed --skip-embeddings --update-plan-prices
```

This sets only the three paid plan price fields. It does not alter limits, custom features, subscription rows or existing gateway subscription amounts. Repeating it is safe when prices already match; do not keep the flag in a permanent pre-deploy command if admins will customise prices later. Fresh databases receive the new defaults during normal seeding.

Create matching monthly/annual recurring prices or products in the active payment gateway. For Stripe, replace the relevant `STRIPE_PRICES` mappings; when no price ID is mapped, checkout uses the catalogue's inline AED recurring price. For Dodo, update `DODO_PRODUCTS` or the admin billing product map. Keep old gateway products and historical mappings available where needed for existing renewals/webhooks. No gateway products were changed from this workspace.

Checkout now reads mapped Stripe prices and Dodo products and verifies the AED base amount and billing frequency before opening a session. Stale, inactive or incompatible mapped prices return `billing_price_mismatch` rather than charging a different base price. Discounts remain applied by the checkout coupon mechanism. Verify tax treatment and the final total in a real checkout before rollout; the amount guard does not configure taxes or change existing subscriptions.

Deploy Render after the API catalogue is updated. Pricing cards read the backend catalogue, display explicit loading/error/retry states and show actual annual totals. The Yearly tab no longer promises a fixed discount for admin-customised annual prices.

## Email senders, completion updates and teacher reviews

Configure optional `EMAIL_FROM_BILLING`, `EMAIL_FROM_ALERTS`, `EMAIL_FROM_NOTIFICATIONS`,
`EMAIL_FROM_UPDATES` and `EMAIL_FROM_REMINDERS` on Railway application services.
Each falls back to `EMAIL_FROM`. Use addresses under a Resend-verified domain.
Keep `RESEND_API_KEY` on Railway. The dedicated scheduler runs
`python -m app.worker --scheduler-only` and drains emails every minute; reminder checks run hourly.

Teachers enable PPT completion emails under Settings → Notifications → PPT and lesson completion updates.
Successful lesson generation queues a link to the completed lesson, respecting their preference.
Payment receipts use the billing sender; renewal, trial and overdue reminders use the reminder sender.
Existing reminder deduplication prevents repeat sends for the same subscription period/reminder step.
Product announcement emails require both announcement email preference and marketing-email consent.

After a completed PPT, teachers receive an optional in-app review invitation at most once per calendar month.
Help & support includes a 1–5 rating and suggestions form. Reviews are saved as support tickets of kind
`review`, visible to staff in the support queue and available for replies. These are private feedback,
not automatically published testimonials. Disable invitations under notification preferences.

## Explicit onboarding plan selection

New accounts now start on Free, without automatically consuming their trial.
After teaching-profile setup, onboarding shows current plans, a coupon field and secure provider checkout,
plus Continue on Free and Start free trial actions. Trial activation uses POST /api/v1/auth/trial with
per-email uniqueness, active-subscription checks and rate limits. Existing trials/subscriptions are preserved.
Coupons are provider-backed: configure Stripe promotion codes or Dodo discount codes; the app forwards and
validates them through checkout. Paid access activates through verified provider webhooks, not the browser return.

## Plan license keys

Admin → Plans & trial includes creation and revocation of single-use plan licenses.
Choose Teacher, Pro or Assistant and 1–36 months. Keys expire for redemption after 90 days;
plan access starts at redemption and expires independently. Keys are displayed once and stored
only as SHA-256 digests. Share the key privately with the intended teacher.
Teachers redeem under Plan & billing. Verified teacher accounts are required; an active subscription
blocks redemption to avoid overlapping paid access or ongoing recurring charges. An unused revoked,
expired or redeemed key cannot be used. Issuing/revoking a key is audited. Revocation applies to
unused keys only; existing grants continue until their end date.
Deploy migration `d204license01` using `alembic upgrade head` before using these screens.

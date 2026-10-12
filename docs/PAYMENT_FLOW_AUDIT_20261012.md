# Payment-flow review — 12 October 2026

**Core payment behavior has local regression coverage, but the live money-to-entitlement flow is not fully verified.** The public site currently advertises Dodo checkout enabled; the owner confirmed **live mode**. This review found and corrected payment-dependent display/recovery gaps and a Dodo portal plan-change bug. The fixes are local and require deployment to the public frontend/API/worker. No live checkout, charge, cancellation, refund, product edit or webhook replay was performed.

## Configuration actually observed

| Environment | Read-only result |
| --- | --- |
| `https://clastio.online/api/v1/billing/plans` | HTTP 200, `online_payments: true`, `payment_provider: dodo`, AED catalogue. Live mode is owner-confirmed; the public endpoint does not expose mode or prove signing-secret/product setup. |
| `http://localhost:3005/api/v1/billing/plans` | HTTP 200, online checkout disabled, provider null. |
| Local API configuration | No Stripe or Dodo API/signing keys or environment product mappings are present. Values were not printed. This does not describe the live server's secret settings. |

A provider being enabled proves that the app selects it; it does not prove that a particular checkout charged the right product or that its webhook reached the correct API. The public hosting revision, live product mappings, webhook subscription/delivery results and receipts were not inspected through a provider dashboard.

## Implemented payment behavior and evidence

| Flow | Current implementation and evidence boundary |
| --- | --- |
| Checkout and return | Backend creates a gateway checkout and a same-site billing/media return URL. Frontend validates new checkout/portal destinations. Return parameters trigger status refresh; they do not grant paid access or credits. Mocked browser and pure unit checks pass. |
| Subscription activation | Signature-verified subscription/payment handlers update the server subscription. Unpaid/incomplete/pending states do not grant initial paid access. Existing paid access and a new transaction are different facts. Tested with mocked provider responses and earlier isolated database regressions. |
| Plan lesson/image allowances | `/me/usage` reads the current server plan, usage, grants and reservations. A subscription provides a configured period allowance; it is not an accumulating one-time media-credit purchase. Paid annual/manual allowances reset monthly; the trial is one allowance. Boundary units pass. |
| Dodo portal plan changes | **Fixed:** the signed current product's valid plan mapping now overrides stale original checkout plan/interval metadata. Upgrade, downgrade, annual interval, actual selected-plan allowance, unpaid state and unknown/invalid mappings have focused unit coverage. |
| Media-credit packs | Verified paid events add a ledger purchase once per payment reference. Earlier isolated integration cases cover Dodo pack credits and repeated deliveries. The frontend now polls delayed balances without claiming that the return URL certifies a purchase. |
| Duplicate or uncertain subscription checkout | One durable pending reservation per teacher, stored URL reuse, database constraint and provider-aware expiry. Uncertain Dodo creation remains held rather than silently opening another purchase. Stripe retries use the original provider idempotency key. Focused units and earlier real-PostgreSQL tests cover these cases. |
| Webhook authentication and replay | Stripe/Standard Webhooks signatures are checked. Provider/event IDs and payload hashes are stored; already processed deliveries are ignored and failed handling rolls back. Earlier isolated signature/lifecycle/media regressions exist. Live signed delivery and concurrent/out-of-order delivery behavior still need operational verification. |
| Renewal, failed payment and cancellation | Current handlers support paid/failed invoices or Dodo subscription/payment events, paid-period grace boundaries and end-of-period cancellation. Existing focused units and earlier isolated lifecycle tests cover the logic; a real renewal/cancellation has not been observed here. |
| Receipt, reminders and referral rewards | Receipt/reward code is tied to confirmed payments and deduplication; outbox delivery needs a configured sender and running scheduler. No delivered live receipt or referral reward was verified in this review. |
| Refunds and disputes | Automatic refund/dispute reconciliation, credit/entitlement reversal and referral clawbacks are not implemented in the billing handlers. They require a defined business policy and provider/staff handling; the Refund Policy page does not execute a refund. |

## Corrections made

1. **Media return messaging:** removed “Payment received” inferred solely from `?status=success`. The page shows the current server balance, polls for up to 45 seconds, offers refresh/help and handles failed API refreshes. A balance change alone is not attributed to a particular checkout.
2. **Payment-dependent display freshness:** job completion, failure and cancellation refresh `/me/usage`, `/usage/estimates` and `/billing/subscription`. Paid, failed, pending and other payment-history states now use matching badge tones.
3. **Sign-in recovery:** expired sessions preserve the original billing/media return query. Clerk sign-in/signup components pass a sanitized return through `/auth/clerk`; the callback and password sign-in use role/onboarding-aware destinations. External URLs, raw API destinations and authentication loops are rejected. The real hosted Clerk exchange remains a separate integration check.
4. **Dodo changed-plan entitlements:** current mapped `product_id` takes priority over old checkout metadata, with an existing-plan check and month/year validation. This updates the plan and interval used by server allowance lookup without activating an unpaid subscription.

## Validation

- **56 focused backend payment tests passed**: entitlement/status boundaries, checkout reservations/retries/expiry, AED price guards, monthly allowance boundaries and seven new Dodo plan-change cases. They ran on Python 3.12 in a network-disabled container with mocked database/provider objects and no credentials. Backend lint and whitespace checks pass.
- **70 frontend unit tests passed**, including safe return/callback routing and existing payment-state, quota and destination guards. TypeScript and the production frontend build pass.
- [Payment-dependent browser checks](../artifacts/payment-flow-20261012/frontend/evidence.json): **9 scenarios passed**, covering delayed balances, bounded polling, explicit refresh/retry, unsafe checkout rejection, valid server destination, payment status badges, and balance refresh for successful/failed/cancelled work. All API requests are intercepted; real gateway requests and account mutations are zero.
- [Account/billing browser regression](../artifacts/system-pages-20261012/account/evidence.json): **16 scenarios passed** on the rebuilt frontend, including explicit checkout/portal/cancel actions, server-confirmed states, false-success URLs, staff restrictions and allowances. All mutations are mocked.
- [Payment-return authentication checks](../artifacts/payment-flow-20261012/auth-return.json): both billing and media return queries survive an expired session and mocked password sign-in, including the original transaction reference. Neither flow creates a gateway request or infers payment from its URL. Clerk callback destinations have unit/type/build coverage; actual hosted Clerk exchange is not simulated by this password fixture.
- API and frontend production images build successfully. The local worker/API were idle before restart; no migration, seed, account grant or provider configuration change was performed.

Final local state: API and frontend are healthy, worker is running, and `/api/v1/ready` returns HTTP 200. [Validation record](../artifacts/payment-flow-20261012/validation.json).

These results establish local behavior, not a successful live Dodo purchase. The earlier [launch audit](LAUNCH_AUDIT.md) records the wider database test coverage and its limits; earlier “checkout disabled” observations are historical and are superseded by the live public observation above.

## Remaining live verification

Use a separate Dodo test-mode/staging setup, or review an already-authorized real payment and its delivery logs. Do not switch the live app's mode or submit a real charge just to fill this evidence gap.

Verify the complete chain: the intended mapped product and final total → hosted checkout → correct HTTPS return → successful signed webhook delivery → correct account/plan and available allowance → successful permitted generation → recorded payment and delivered receipt. Repeat the delivery safely in staging to check that credits/receipts/rewards are not duplicated; test delayed/failing payments, renewal, portal plan change and end-of-period cancellation there too.

Dodo's [webhook documentation](https://docs.dodopayments.com/developer-resources/webhooks) covers signing, subscribed events, delivery monitoring/retries and replay tools. Its [event guide](https://docs.dodopayments.com/developer-resources/webhooks/intents/webhook-events-guide) defines the supported payment/subscription lifecycle. Match the dashboard endpoint and signing secret to the intended deployed backend. The relevant app endpoint is `/api/v1/webhooks/dodo`; the deployment runbook identifies the API host. Do not paste secrets or card details into chat.

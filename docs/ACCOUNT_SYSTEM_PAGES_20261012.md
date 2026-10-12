# Account and billing system pages — 12 October 2026

The recovery pages use the shared SystemStateLayout and check account state through the existing same-origin API. The nineteen routes are excluded from indexing. No account, subscription, email consent or deletion state is inferred from a URL query. Viewing a route does not submit a change.

## Routes and evidence

| Routes | Source of truth and available action |
| --- | --- |
| `/session-expired` | `/auth/me`; sign in with a sanitized internal return path. An active session can continue. |
| `/account-suspended`, `/account-deactivated` | `/auth/me`; a generic restricted-access response offers support. The API cannot identify the specific restriction through these pages. |
| `/account-deleted` | `/auth/me`; a missing session cannot prove completed deletion. Contact support to review a previous request. |
| `/delete-account` | Confirm the signed-in teacher’s email and explicitly acknowledge immediate access closure before POST `/me/delete`. Only a successful `pending_deletion` response shows an accepted request and its scheduled date. Staff accounts have no deletion form. |
| `/verification-success`, `/verification-failed` | `/auth/me.email_verified`; request a fresh verification email explicitly through `/auth/resend-verification`. Existing `/verify-email` confirms a submitted token through the API and links here. |
| `/link-expired` | Help obtaining a fresh account link. Validity remains checked by the existing token-processing endpoints. A purpose query selects the help action only. |
| `/payment-success`, `/payment-failed` | `/billing/subscription`; success-page polling checks webhook-updated plan access. Active current online paid access is described as current subscription access, without attributing payment to a pasted checkout reference. Trial and manual access do not establish payment confirmation. |
| `/subscription-expired`, `/trial-expired` | Current subscription and server trial flags. A missing subscription does not establish historical expiry. |
| `/usage-limit`, `/upgrade-required` | Current billing allowances, including explicit available balances, grants and reservations. The requested resource is restricted to known allowance names. |
| `/checkout` | Current pending checkout from billing, or actual current plan choices. Opening the page does not start a payment. Existing PricingTable starts checkout only after a plan button is clicked. |
| `/billing-portal` | Explicit POST `/billing/portal` for an available online subscription. Server-returned destinations accept HTTPS provider URLs and valid same-origin URLs; credentials, control characters, backslashes, empty values and unsafe protocols are rejected. |
| `/subscription-cancelled` | Server cancellation state; an explicit acknowledgement and POST `/billing/cancel` are required to request cancellation. |
| `/email-unsubscribe` | Current `/me/consents`; PUT `marketing_email: false` only after the button is clicked. Security and billing notices remain separate. |
| `/notification-preferences` | Existing `/me/notification-preferences` controls, including mandatory category enforcement by the API. |

## Existing flow integration

- App workspace authentication failures open session or restricted-account recovery.
- Legacy login displays a recovery link after a server-confirmed suspended, banned or pending-deletion response.
- Verification, password reset and magic-link errors provide usable fresh-link recovery.
- Plan & billing links to payment confirmation, help, allowances, secure payment settings and cancellation review.
- Settings links to the confirmed deletion workflow and accurately labels `/me/export` as an account summary. It does not promise a complete file export or complete storage purge.

## Validation

`npm run typecheck` passes. `e2e/account-system-pages.mjs` intercepts every API request and checks all nineteen routes, mobile layout, robots directives, URL spoofing, explicit mutations, staff restrictions, billing confirmation, reserved/granted quotas and rejected checkout destinations. It does not read or mutate the teacher database. Browser results are saved in `artifacts/system-pages-20261012/account/evidence.json` after the consolidated web build is refreshed.

## Existing limitations

The current account API deliberately returns generic unavailable access for restricted sessions. A 401 cannot identify a deleted account, and a missing paid subscription cannot identify a historical cancellation or expiry. The pages keep those states unconfirmed. MFA, invite management and completed purge verification have no existing supported account API workflow and are not represented as functioning features.

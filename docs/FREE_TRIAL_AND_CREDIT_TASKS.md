# Free trial and reviewed credit tasks in Clastio

## If a teacher does not upgrade

Teachers start on Free and can explicitly choose the seven-day trial after email verification when trials are enabled. A trial has no stored payment method and never automatically charges or renews. After the trial end time, every server entitlement check falls back to Free. Their lessons, files and designs remain stored; Free feature, storage and generation limits apply to new work.

Earlier credit spending in the same calendar month still counts. Ending a trial does **not** create another fresh allowance. The Free allowance resets on the first of the next month; the billing page and sidebar show the actual spendable balance, including queued-work reservations and approved grants. Staff can change the Free allowance in Plans & trial. The default is 60 lesson credits per month. The default seven-day trial has a separate maximum of 50 lesson credits while active.

Purchasing a subscription is an explicit checkout. A checkout return URL alone cannot grant paid access: signed provider confirmation is required. A pending checkout or unresolved payment subscription blocks overlapping trials, licenses and task rewards.

## Multiple email accounts and shared school computers

The server maintains a lifetime trial claim for the normalized email address, including common email aliases, even after account deletion. A signed, opaque random browser cookie additionally records a hashed installation claim. A different verified email on that same browser can still sign in and use Free, but cannot ordinarily start another trial.

The `clastio_installation` cookie is first-party, HTTP-only, uses SameSite=Lax, is Secure when `COOKIE_SECURE=true`, and lasts up to one year. It is not an advertising identifier and contains no email, IP address or hardware information. The database stores only a hash of its random identifier. A present invalid signature fails closed for trial/reward writes; ordinary sign-in and Free access remain available without silently resetting the identifier.

This is a deterrent rather than proof of a person's identity or a physical device. Clearing cookies, incognito, a separate browser profile or a different device can evade the browser claim. Verified email, account normalization, rate limits, manual reward review and bounded reward budgets provide additional controls. Shared school IPs are not blanket-banned, and the app does not use invasive device fingerprinting. Clerk/Turnstile verification can supplement this boundary where configured.

For a legitimate shared school computer, staff with **both** `users.manage` and `billing.modify` can record a reasoned exception in Admin → Credit tasks. This allows that verified, active teacher to explicitly choose their own first trial on the shared browser. It does not start a trial, waive email history, reset a previous trial, or allow overlapping subscriptions. The exception is audited.

Cookie Banner and the default Cookie Policy describe this essential abuse-control cookie. For a site with an already-published policy, publish a reviewed updated Cookie Policy through the legal admin page; seeding preserves existing published versions.

## Credit tasks: inactive and empty by default

Teacher page: `/rewards`. Admin page: `/admin/rewards` (Credit tasks in the billing navigation). No example tasks are silently created or published, and no product action automatically awards credits. Leave the program disabled until useful tasks and a sustainable budget are ready.

Staff with `billing.modify` can add drafts, publish tasks, specify optional UTC start/end times, set 1–20 lesson credits per task, and cap total task approvals. Useful tasks can ask for honest lesson-quality feedback, a bug report with reproducible steps, or an optional product tutorial exercise. Staff must acknowledge that tasks do not require positive public reviews, fabricated evidence, unsolicited messages or purchases. Do not request student personal information in proof.

The teacher submits a plain-text description of their completed work (20–2,000 characters). A staff member reviews the evidence and approves or rejects it with a note. Rejected submissions can be corrected by the same teacher. Approval always rechecks current account status, verified email, Free-plan eligibility, task publication/expiry, task amount, payment conflicts and program budgets. Teachers on a current trial or paid/manual plan are not eligible.

Default program limits are 20 approved credits per normalized email per UTC day, 60 per month, 200 for the lifetime of the email, and 500 across the platform per UTC day. The admin interface allows bounded adjustments: maximum 50/day, 200/month, 500/lifetime and 2,000/platform day. Tasks additionally have a bounded approval-count limit. Pending proofs do not reserve or award credits.

Each normalized account can earn a task once. Each browser can earn that same task once, even across different emails. A per-program transaction lock serializes approval budgets, and a locked submission status plus unique claim constraints prevent duplicate rewards from simultaneous approval or retries. Account deletion preserves hashed claim/budget evidence but erases submitted free text.

Approval writes an auditable `CREDIT_REWARD` row in the existing lesson-credit ledger. These credits increase actual available lesson credits while keeping Free feature limits. They expire at the next calendar-month boundary, as the existing Free-period ledger calculation moves to the next month. They do not roll over, unlock AI images or premium features, or become cash. A paid plan change likewise uses its own credit period.

For legitimate shared-device reward conflicts, support can review evidence and use the existing audited manual credit-grant tool if appropriate. The trial-cookie exception does not bypass reward safeguards.

## Deployment and validation

Apply migrations through `g207credits01` after the push migration `f206push01`, then deploy the API and frontend together. No new secret or service is needed for trials or rewards; keep the existing `SECRET_KEY` stable across API instances. Do not add payment/AI credentials to the frontend for this feature.

Before marketing, open **Admin → Settings & flags → Platform**, enable **Require verified email to generate**, and click **Save** in that Platform panel. This writes `system.require_email_verification_for_generation=true`; the default is currently false. It stops unverified Free accounts from spending generation credits while allowing signup and email verification. Keep per-account limits and global AI spending budgets enabled as well, since browser cookies cannot prevent every fresh verified-email account.

Regression coverage includes trial expiry with no charge/refill, same-browser different-email attempts, narrow staff exceptions, malformed-cookie rejection, disabled/unpublished/expired tasks, verified Free eligibility, payment-plan changes, permission checks, per-day/month/lifetime/platform budgets, duplicate review transactions and ledger balance updates. Browser regression exercises draft creation, activation, teacher submission, manual approval, read-only staff and mobile layouts with mocked accounts; real DB tests exercise the transactions separately.

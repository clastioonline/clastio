# Legal and policy page audit — 12 October 2026

**Implementation follow-up:** the [supporting-page revision](SYSTEM_PAGES_AND_INDEXING_20261012.md) adds Contact, a legal directory, public cookie-preference reopening, copyright/accessibility/privacy information, and server-rendered version-aware policy reading. These resolve the corresponding route/navigation limitations observed below. The owner approved `Clastio` and `Support@clastio.online`. Existing published policy rows were not rewritten or replaced; the policy-content, provider, export/purge and launch findings below still require their own resolution. The observations that follow record the earlier audit state.

**The five core policy pages work, but the published documents are still legacy templates and are not ready for public launch.** This is a local coverage and implementation review, not a jurisdiction-specific legal approval. No policies, accounts, consents or application configuration were changed.

## Pages that exist

All five pages and their public API endpoints returned HTTP 200, rendered their document title/content, and are linked from the public footer, the legal sidebar and the sitemap. The current published versions are all **1.0**, effective **26 September 2026**. Privacy also fits the checked mobile viewport without horizontal overflow. The browser recorded no JavaScript errors.

| Document | Public route | Current status |
| --- | --- | --- |
| Terms & Conditions | `/legal/terms` | Published and accessible without signing in |
| Privacy Policy | `/legal/privacy` | Published and accessible without signing in |
| Acceptable Use Policy | `/legal/acceptable_use` | Published and accessible without signing in |
| Cookie Policy | `/legal/cookie` | Published and accessible without signing in |
| Refund Policy | `/legal/refund` | Published and accessible without signing in |

Signup links to Terms, Acceptable Use and Privacy. The required policy checkbox and optional marketing checkbox start unchecked; account creation is disabled until the required checkbox is selected. Cookie choices include Essential only and Customise, with analytics off by default. Account settings provide consent history and a way for signed-in teachers to change cookie choices. Admin → Legal documents provides versioned drafts, publishing, immutable published versions and policy reacceptance.

Unknown document types and unknown document versions return 404. Each current policy has only one published version, so there is no earlier-version selector to exercise against this local database.

Source review also found a version-reader limitation: the selector assumes the first history entry is current, although the API can include a published version with a future effective date. Selected historical versions are neither read from nor reflected in the page URL. These paths were not tested by publishing historical or future versions; review them before relying on future-effective publication and direct version links.

## Content and implementation gaps

1. **The actual published documents differ from the current source defaults.** All five published documents still contain the old **PPT Genie** template notice/branding. Privacy still lists `privacy@pptgenie.example` with an instruction to replace it. A real operating entity, usable privacy/support contact and applicable business details need to be supplied. Updating `DEFAULT_DOCUMENTS` or restarting the backend will not replace existing published rows: [`seed_documents`](../apps/api/app/services/legal.py) deliberately preserves them. Use reviewed new versions through Admin → Legal documents.

2. **The AI-provider disclosure and no-training promise need verification.** Privacy names Anthropic, OpenAI and Google but omits the configured OpenRouter intermediary. It says providers do not train on the data “under our agreements”; this audit did not establish those agreements or account privacy settings. The [`OpenRouter adapter`](../apps/api/app/ai/openrouter_provider.py) requests supported parameters but does not explicitly set `data_collection: "deny"` or `zdr: true`. OpenRouter distinguishes its own no-training policy from downstream providers' retention/training arrangements. Account restrictions may affect routing, so the absence of request flags does not establish that training occurs. Match the published claim to verified settings and contracts. [OpenRouter privacy](https://openrouter.ai/privacy), [provider controls](https://openrouter.ai/docs/guides/routing/provider-selection), [zero-data-retention controls](https://openrouter.ai/docs/guides/features/zdr).

3. **The published cookie notice is behind the implementation.** It omits the signed random browser-installation cookie used for trial/reward abuse prevention, retained for up to one year in [`trial_device.py`](../apps/api/app/services/trial_device.py). The newer seed mentions it, but the current published version does not. Consent choices are stored in browser localStorage by [`cookie-banner.tsx`](../apps/web/components/cookie-banner.tsx), rather than the preference cookie described in the template. Anonymous visitors have no visible footer control to reopen their choices after dismissing the banner; signed-in users have a Settings control. Review the cookie/storage inventory against the enabled production authentication and analytics integrations.

4. **The data-deletion promise exceeds the cleanup found in source.** Privacy says content is removed after a 30-day grace period. [`purge_account`](../apps/api/app/services/lifecycle.py) explicitly deletes uploaded originals and educator-plan/demo/digital-resource exports, then deletes owned database rows. No equivalent deletion was found there for normal lesson PPTX/PDF/preview objects, document export files, template assets or generated media. Lesson exports also keep versioned `lessons/{id}/v*/` objects; the current row only holds current-version keys. This is a source-inspection finding, not a deletion test against teacher data. Complete and verify object-storage cleanup, including prior versions and failures, before relying on the promise.

5. **The data export is partial.** [`GET /me/export`](../apps/api/app/api/routes/teacher.py) returns profile/preferences/classes and summaries of courses, lessons, documents and uploads, plus an AI-call count. It does not provide the full lesson/slide contents, generated files, memory/conversations, consent history or billing/security data. Its own docstring calls it everything stored about the teacher. Establish the intended export/request scope and implement or describe it accurately; this audit did not submit an authenticated data request.

6. **The refund policy needs business and payment-provider confirmation.** The template promises pro-rata annual refunds and unused-pack refunds within 14 days and directs users to support. Confirm those terms, the request contact/process and real provider refund handling before accepting payment. A working policy page or checkout-return screen does not verify refund delivery.

7. **Retention and sharing disclosures need the final production configuration.** Operational retention is configurable and scheduler-driven in [`lifecycle.py`](../apps/api/app/services/lifecycle.py); the scheduler and actual production settings determine enforcement. Describe enabled hosting/payment/email/authentication processors and international transfers accurately, and review library/design sharing permissions against the Terms' statement about processing content to provide the service to its owner.

## Missing routes and coverage

| Item | Observed state | Next action |
| --- | --- | --- |
| Copyright/takedown policy | `/legal/dmca` and its API return 404. Backend/admin supports the type, but there is no default/published document and the frontend whitelist excludes it. | Define a suitable copyright complaint process and contact; add a reviewed document and matching public route. The existing code label does not establish that US DMCA rules apply. |
| Public contact/business page | `/contact` returns 404. Anonymous `/support` redirects to login. | Provide a usable public contact and operating-entity details, especially for people who cannot sign in. |
| Legal landing page | `/legal` returns 404; the five direct links work. | A legal index would improve navigation; its absence does not break the existing policy links. |
| Public cookie-preference reopen control | None found after choosing/dismissing the banner. | Add a visible public control if choices are offered to anonymous visitors. |
| Dedicated AI/data or accessibility policy | No `/legal/ai_data` or `/legal/accessibility` route. | These are coverage options, not automatically mandatory separate pages. AI disclosure can be incorporated into the existing Terms and Privacy; accessibility and school-processing commitments depend on the service and applicable obligations. |

Having every named page does not determine compliance. The operating entity, location, target markets, school contracts, data flows and applicable regime still need to be established. If UK rules apply, the [ICO privacy-notice checklist](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide/) covers controller/contact, purposes/lawful bases, recipients, retention, rights/complaints and relevant transfers. If UAE rules apply, review the [UAE government's data-protection overview](https://u.ae/en/about-the-uae/digital-uae/data/data-protection-laws) and the relevant regime, including any free-zone rules. Selecting a British curriculum does not establish UK jurisdiction. This audit does not determine the applicable law or certify these templates.

## Evidence and limits

- [Read-only public browser results](../artifacts/legal-pages-audit-20261012/public-browser.json) include the five pages, footer/sidebar links, signup defaults, cookie choices, mobile overflow, missing routes and zero browser errors. All non-GET API requests were guarded; none were attempted.
- [Published-document summary](../artifacts/legal-pages-audit-20261012/published-summary.json) records public versions, dates and placeholder flags. [Detailed content findings](../artifacts/legal-pages-audit-20261012/content-findings.md) provide source references for retention, deletion/export, sharing, refunds and collected-data discrepancies. [Navigation review](../artifacts/legal-pages-audit-20261012/public-navigation-review.md) records the public route and version-reader limitations.
- [Mobile privacy-page screenshot](../artifacts/legal-pages-audit-20261012/privacy-mobile.png) records the current published template.
- The earlier [launch audit](LAUNCH_AUDIT.md) covers broader application checks. This focused review adds the policy-content and deletion/export gaps above.
- This review used the local app at `http://localhost:3005`, public API GET requests and source inspection. It did not publish policy versions, exercise destructive account deletion, submit payments/refunds, inspect external provider account settings, determine jurisdiction or verify a public hosting deployment.

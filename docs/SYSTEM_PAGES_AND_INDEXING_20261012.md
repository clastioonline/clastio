# Supporting pages and indexing follow-up — 12 October 2026

The owner supplied nineteen main-domain Search Console URLs, three HTTP/www alternatives, a Clerk authentication-host URL, and the public contact **Clastio / Support@clastio.online**. This revision makes published policies readable in the initial HTML, adds public help and trust information, and connects branded recovery pages to existing account and billing APIs. It extends the [search implementation](SEARCH_GROWTH_IMPLEMENTATION.md) and [live GSC audit](GSC_FOLLOWUP_20261012.md).

## Public information and policy routes

| Route | Content and connected workflow |
| --- | --- |
| `/contact` | Owner-approved support email; existing authenticated `/support` tickets; help, status, privacy and school links. No invented office address or company registration details. |
| `/help` | Sign-in, generation, editable export, payment, allowance and personal-data help. |
| `/legal` | Current published policy catalogue and related privacy/support information. |
| `/legal/terms`, `/legal/privacy`, `/legal/acceptable_use`, `/legal/cookie`, `/legal/refund` | Request-time server-rendered published policy text. Title, version, effective date and selected history are visible without JavaScript. |
| `/security` | Account/session, upload, AI-processing, payment and reporting guidance. |
| `/data-privacy` | Correction, partial account-summary export, deletion request and communication choices. |
| `/data-processing` | School processing-review/agreement enquiries through support. This is a request workflow, not an executed DPA. |
| `/accessibility` | Available reading/keyboard guidance and reporting a barrier; no conformance certification is asserted. |
| `/copyright` | Authorised sources, licence checks and support-based copyright complaints. |
| `/cancellation-policy` | Existing renewal-cancellation workflow and links to the separately published Refund Policy. |

Published policy content remains the source of truth; this revision does not overwrite accepted versions or publish new legal terms. `/legal/dmca` is recognised by the frontend if an authorised administrator publishes that supported document type; it remains a genuine 404 while no document exists. A complaint-information page does not establish that US DMCA rules govern the business.

Policy-version URLs now select their actual public document: `/legal/privacy?version=1.0`. Archived versions use `noindex,follow` and canonicalise to the current policy address. Unknown types/versions return 404. Current effective policy is fetched independently rather than assumed to be the first history item. Unavailable or invalid upstream policy data shows an error instead of an empty successful document. Fetches have an exact public-resource restriction, a three-second deadline and bounded response bodies, and forward no visitor cookies or authorization headers.

Familiar addresses use permanent redirects to the canonical published documents: `/privacy`, `/terms`, `/cookies`, `/refund-policy`, `/acceptable-use`. Only destination URLs enter the sitemap.

## Branded error and connection states

The shared system layout supplies a title, explanation, appropriate actions, useful links and a support reference when available. The following direct public state documents use their real HTTP status on GET and HEAD and `noindex,nofollow`:

| Routes | HTTP status |
| --- | --- |
| `/400`, `/401`, `/403`, `/404`, `/409`, `/429`, `/500`, `/503` | Matching status code |
| `/maintenance`, `/offline` | 503 |
| `/permission-required` | 403 |
| `/browser-not-supported` | 200, excluded from indexing |

Unknown URLs retain the framework's genuine 404 response with the shared Clastio design. Root and global error boundaries use the shared layout and retry action. Opening `/maintenance` does not switch the service into maintenance; existing API maintenance controls remain responsible for operational state.

The service worker caches only two public brand images and the explicitly marked, self-contained public offline screen. A network failure on a known public document can show that screen. Account pages, authentication, APIs, uploads and generated files remain network-only. Actual HTTP errors are preserved and teacher response bodies are not cached.

## Account, billing and privacy recovery

Nineteen account/billing pages are detailed in [the account implementation](ACCOUNT_SYSTEM_PAGES_20261012.md). They cover session recovery, account restrictions, verification/fresh links, payment confirmation/help, checkout, plan/trial/usage states, billing portal, cancellation review, communication preferences and deletion requests. They read existing APIs and require an explicit action before sending a change. A pasted success URL cannot establish payment, cancellation, email verification or account deletion.

`/data-export-request` adds a twentieth account page. It checks sign-in and downloads `/me/export` only when the teacher clicks **Download account summary**. The page describes the actual partial scope and connects wider requests to account support or the approved email. It does not claim that the JSON contains every stored record or uploaded/generated file. All thirty-two system/account/privacy-state routes are excluded from the public sitemap and have crawl exclusions and noindex headers; account authentication remains the data-access boundary.

Existing login, signup, forgot/reset password, verification and token-processing pages remain connected. There is no supported MFA-enrolment or team-invitation API in the current app, so this revision does not present those as functioning product workflows. Existing account controls and support offer recovery.

## Internal links and crawl inventory

Public navigation, guide clusters, support pages, policy navigation and the footer link to relevant pages. Footer cookie preferences reopen stored choices for anonymous visitors as well as signed-in teachers. An early click remains queued while the dialog's script loads; the footer control becomes actionable after hydration. Contact points to existing support rather than introducing an unconnected message form. Public pages use canonical URLs, actual visible structured information and matching social metadata.

The public sitemap and `/llms.txt` directory include the new information pages and all reviewed teaching guides. Private state pages, policy aliases and the Clerk authentication host are excluded. Robots keeps the private exclusions for both the general crawler group and OAI-SearchBot, while allowing only the public billing catalogue, legal documents/index, public UI configuration and service-status reads needed for rendering. These crawl controls do not replace authentication or guarantee indexing.

## Owner-supplied query signals

The two one-impression queries are too small to establish demand or purchasing intent. `moe uae` may be Ministry navigation. The singular slide variant has no supplied metrics. The [live GSC report](GSC_FOLLOWUP_20261012.md) records those exact limits and the read-only HTTP evidence.

The existing UAE presentation guide now answers an Abu Dhabi classroom brief and British-versus-MoE source selection with primary ADEK/MoE references and relevant hub links. It has no fabricated local office or Ministry endorsement. The query catalogue now has **21** overlapping, RE2-compatible filters, including singular/plural slide creation, Abu Dhabi variants and potentially navigational MoE context.

```sh
cd apps/web
npm run seo:queries -- --patterns
```

These expressions analyse observed query exports; they are not keyword blocks inserted into visible page copy. Meaningful page content and useful related links do the work.

## Production indexing follow-up

The public HTTP audit found that all nineteen supplied main-domain URLs returned 200, declared matching canonicals and were already in the live sitemap. It also found an older active frontend: pricing lacked initial plan cards, two legal pages lacked initial policy text, and three new guides returned 404. Serve this reviewed revision from the actual public origin before requesting indexing of its source-only additions.

The three HTTP/www URLs correctly redirect to `https://clastio.online/`; “Page with redirect” is expected for those alternatives. The Clerk host already returned `noindex,nofollow` and an empty JSON response; preserve its authentication setup and keep it outside the marketing sitemap. Verify that it is the exact URL attached to the “indexed without content” warning.

After deployment, inspect priority canonical pages using the owner's Search Console access, compare live rendered HTML with the last indexed snapshot, and submit the public sitemap or request priority-page indexing where appropriate. Check actual CDN/crawl logs if Google cannot fetch the live page. This work did not submit Search Console changes or publish to an external server. See Google's [page indexing definitions](https://support.google.com/webmasters/answer/7440203?hl=en), [JavaScript rendering guidance](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics), and [canonical signals](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

The [legal-content gaps](LEGAL_PAGES_AUDIT.md) and broader [launch checks](LAUNCH_AUDIT.md) remain separate from route coverage. The new pages accurately describe the existing partial export and deletion-request receipt; they do not certify full storage cleanup, provider contractual promises or legal compliance.

## Validation and evidence

- **68 frontend unit tests passed**, including public legal fetch/validation bounds, billing truth and redirect guards, status/HTML recovery, offline privacy and queued cookie preferences. TypeScript and whitespace checks pass.
- **Production Next.js 16.3.8 frontend build passed** with 106 generated pages. Published policies and pricing render at request time. The reviewed public canonical origin is `https://clastio.online`; local browser traffic remains at `http://localhost:3005`.
- [Read-only HTTP audit](../artifacts/system-pages-20261012/public-http.json): **37 public sitemap URLs**, all with 200, a visible server H1 and a matching canonical; actual published policy paragraphs appear in HTML. **32** state pages have noindex/exclusions, **5** policy aliases permanently redirect, and **53** linked local routes resolve.
- [Generic browser checks](../artifacts/system-pages-20261012/generic-pages.json): **12** direct state pages use real GET/HEAD statuses, work without JavaScript and fit mobile screens. Unknown/deep URLs return branded 404. Actual offline public navigation uses only the marked public screen; private routes remain network-only.
- [Account browser checks](../artifacts/system-pages-20261012/account/evidence.json): **16** mocked scenarios cover **19** account/billing pages, server-confirmed states, explicit mutations, staff restrictions, safe destinations, grants/reservations, noindex and mobile controls. All API interactions are intercepted; no real account or billing data changed.
- [Isolated public-support SSR checks](../artifacts/system-pages-20261012/public-support-ssr.json): all **5** policy bodies are readable without JavaScript; archived content, canonical/noindex, missing versions/types, upstream errors, script escaping, **7** support pages, Contact, policy links, cookie reopening and explicitly clicked account-summary downloads pass. Synthetic incoming Cookie/Authorization headers are not forwarded by public server fetches.
- [Delayed-dialog production regression](../artifacts/system-pages-20261012/cookie-race-fixed.json): with the actual CookieBanner script held, a first click is preserved and opens the dialog after loading; no second click or API write is needed. The final rebuilt frontend and the unchanged backend are both healthy locally.
- The discovery browser check passes all **16** guides without JavaScript, current public pricing, structured information, sources/review dates, mobile layouts, public crawler files, social image, private noindex and regex targets. The existing SEO/assistant regression also passes its **13** original guides, product/legal/status metadata, pricing retry, CSP, responsive layout and clarify/confirm/remember interactions.

Browser assertions use synthetic account/payment responses or read-only public GETs. No paid generation, provider setting, real account deletion, payment/refund, policy publication, database migration or public deployment is performed by these checks. Prior evidence counts remain labelled as their earlier audit stages.

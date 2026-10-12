# Search Console follow-up and live indexing audit — 12 October 2026

## What the owner supplied

This is a small reported sample, not a Search Console account export. No account access, indexing request, validation request, DNS change, CDN change, or external deployment was performed.

| Reported query | Clicks | Impressions | Interpretation boundary |
| --- | --- | --- | --- |
| `moe uae` | 0 | 1 | May be navigation to the Ministry rather than interest in an independent teacher tool. No affiliation or product demand can be inferred. |
| `slides creation in abu dhabi` | 0 | 1 | A possible presentation task; teacher, AI, and purchasing intent are not established. |
| `slide creation in abu dhabi` | Not supplied | Not supplied | A query variant, with no invented counts. |

Reported indexing counts: **19 Discovered – currently not indexed; 3 Page with redirect; 0 Crawled – currently not indexed; 1 Page indexed without content.** The owner supplied the 19 main-domain URLs and three HTTP/www alternatives. The last reported URL appears to be `https://clerk.clastio.online/`; verify its exact issue row in Search Console before assigning that warning to it.

## Direct live evidence

Read-only public `curl` GETs inspected status, redirect chains, selected response headers, HTML metadata and visible server content. All **19 supplied main-domain URLs returned 200, declared the matching HTTPS canonical, and showed no observed HTML/header `noindex`**. They are all present in the current live sitemap. This proves availability in this HTTP sample, not Google's indexed state or selected canonical.

The live site serves content older than the reviewed working tree: the old guide hub and PPT guide titles remain, three new guides return 404, pricing has only a loading state for the plans, and two legal pages have navigation/skeleton/footer without their policy body. This points to an older active web build or origin/cache path. The exact production origin configuration was not inspected.

| Supplied path | Live status | Server HTML observation |
| --- | --- | --- |
| `/faq` | 200 | H1 and FAQ content present. |
| `/for-schools` | 200 | H1 and school information present. |
| `/how-it-works` | 200 | H1 and workflow content present. |
| `/legal/acceptable_use` | 200 | Canonical and index metadata present; no H1 or policy body in initial HTML. |
| `/legal/cookie` | 200 | Canonical and index metadata present; no H1 or policy body in initial HTML. |
| `/pricing` | 200 | H1 and FAQs present; plan area says “Loading current plans…” without server-rendered plan cards. |
| `/solutions` | 200 | Old hub H1 and guide links present. |
| `/solutions/british-curriculum-lesson-planning` | 200 | H1 and guide text present. |
| `/solutions/cbse-lesson-planning-uae` | 200 | H1 and guide text present. |
| `/solutions/differentiated-lesson-presentations` | 200 | H1 and guide text present. |
| `/solutions/eal-lessons-uae` | 200 | H1 and guide text present. |
| `/solutions/edit-ppt-without-regenerating` | 200 | H1 and guide text present. |
| `/solutions/lesson-planning-for-uae-teachers` | 200 | H1 and guide text present. |
| `/solutions/personal-ai-teaching-assistant` | 200 | H1 and guide text present. |
| `/solutions/quiz-and-exit-ticket-maker` | 200 | H1 and guide text present. |
| `/solutions/reuse-school-powerpoint-design` | 200 | H1 and guide text present. |
| `/solutions/stock-images-for-teaching-presentations` | 200 | H1 and guide text present. |
| `/solutions/turn-teaching-notes-into-powerpoint` | 200 | H1 and guide text present. |
| `/solutions/worksheet-maker-for-uae-teachers` | 200 | H1 and guide text present. |

### Concrete version and resource differences

- Live `/solutions` says “Solve the planning problems that take time from teaching”; the working tree has the topic-organised teacher guide hub and contextual internal links.
- Live `/solutions/ai-ppt-maker-for-teachers-uae` has the older short PPT guide. The reviewed source adds the objective/source review workflow, then the Abu Dhabi and British/MoE sections described below.
- These source routes returned **404 live** and are absent from the live sitemap: `/solutions/how-to-choose-ai-presentation-maker-for-teachers`, `/solutions/gcse-igcse-lesson-presentations`, `/solutions/ai-lesson-planning-costs-and-credits`. Do not request indexing for a source-only route before it serves its intended page publicly.
- Live `/api/v1/billing/plans` is available and lists AED **149 / 249 / 399 monthly** for the three paid plans, but initial `/pricing` HTML does not include their cards. The separately tested source change fetches that public catalogue at request time and preserves client refresh/retry.
- Live `robots.txt` permits the public pages but has `Disallow: /api/` without the reviewed public billing/legal/status exceptions. That is a resource-access gap for client-only content, not proof of the reason for the 19 discovered URLs. Google's [JavaScript guidance](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) explains rendering queues, blocked resources and the benefits of server-rendered content.
- Live `sitemap.xml` contains **25 URLs**, including all supplied main-domain URLs and 13 guides; it has no `lastmod`. The source sitemap adds the new guides and uses actual editorial review dates where supplied. Neither a sitemap nor a date guarantees indexing.

### CDN/bot sample and redirect results

The browser-like audit agent and a **spoofed Googlebot user-agent** both received 200 without an observed challenge on `/`, `/solutions`, the UAE PPT guide, `/pricing`, `/robots.txt` and `/sitemap.xml`. Response headers identify Cloudflare; sampled responses show `CF-Cache-Status: DYNAMIC`, with `X-Nextjs-Cache: HIT` on the older static pages. No blanket user-agent blocking was observed. This does **not** verify Google's source IPs, Google renderer access, all WAF rules, or the historical crawl that Search Console describes. Those require URL Inspection and relevant server/CDN logs.

| Alternative URL | Observed chain | Expected destination |
| --- | --- | --- |
| `http://clastio.online/` | 301 → 200 | `https://clastio.online/` |
| `https://www.clastio.online/` | 301 → 200 | `https://clastio.online/` |
| `http://www.clastio.online/` | 301 → 301 → 200 | `https://clastio.online/` |

These are working scheme/host canonical redirects in this sample; no loop or failing destination was observed. They are different from a redirect error.

The Clerk subdomain root returned 200 with an empty JSON body and `X-Robots-Tag: noindex, nofollow`. It is an authentication service host, not a teaching landing page, and is absent from the public sitemap. Preserve its authentication/DNS setup. If it is the reported “indexed without content” URL, inspect that exact host in Search Console separately from the main-domain content pages; do not make the auth host indexable to improve the marketing report.

## What the Google reasons mean

Google's [Page indexing documentation](https://support.google.com/webmasters/answer/7440203?hl=en) distinguishes these states:

- **Discovered:** Google knows the URL but has not crawled it yet. This label alone does not establish thin content, a penalty, or a measured server overload.
- **Page with redirect:** the alternate URL redirects; indexing the canonical destination is the relevant goal.
- **Crawled, not indexed:** Google fetched the URL but has not indexed it. The reported count here is zero.
- **Indexed without content:** Google could not read the content despite indexing the URL; inspect the exact page. Google distinguishes this warning from robots.txt blocking.

Use [URL Inspection](https://support.google.com/webmasters/answer/9012289?hl=en) to compare the indexed snapshot with the live page, including the last crawl, fetch result, rendered screenshot/HTML, user-declared canonical and Google-selected canonical. A successful live HTTP fetch is not an indexing guarantee.

## Local content and measurement changes

The sparse sample supports a useful explanation within the existing UAE guide rather than separate near-duplicate city pages:

- Added **“Create lesson slides for an Abu Dhabi classroom”**, with an actual programme/year/subject/source brief, classroom support, a meaningful local example and a PPTX review check.
- Added a **British versus UAE MoE teaching-context table**. A city label does not determine the school's programme; a MoE subject within another programme needs the school-confirmed requirements. No curriculum alignment, regulator approval, or endorsement is fabricated.
- Clarified that Clastio is independent teaching software, and linked primary [ADEK curriculum policy](https://www.adek.gov.ae/-/media/Project/TAMM/ADEK/Policies/School-Policies/Teaching-and-Learning/ADEK_S_Curriculum-Policy_EN_v1_2.pdf) and [MoE Minhaji](https://minhaji.moe.gov.ae/) resources. These support school/source context; linking them is not an affiliation claim.
- Added stable guide anchors and public hub links to those two sections, without a fabricated address or office in Abu Dhabi.
- Query filters now recognise `slide`/`slides`, `Abu Dhabi`/`Abu-Dhabi`/`Abudhabi`, non-AI presentation creation and UAE MoE context. Tests explicitly keep a city/slide query separate from proven AI intent, and label MoE context as possibly navigational.

Validation: **33 web unit tests passed**, including the added query-alias/negative-match checks; TypeScript and whitespace checks passed. The parent owns the consolidated production build and final browser check. These are local reviewed changes, not a claim that the live snapshot has already changed.

## Follow-up sequence

1. Serve the reviewed build from the active public origin. Recheck the affected URLs, actual plan cards, legal policy bodies, guide links, canonicals, robots and sitemap on `clastio.online` itself.
2. Inspect the homepage and a few priority teacher pages in Search Console. Check the live rendered result and the indexed/last-crawled version before attributing an exclusion to content quality or bot blocking.
3. After the public pages are correct, use the owner's Search Console access to submit the public sitemap or request indexing of a small number of priority canonical pages where appropriate. Do not submit the Clerk auth host or repeatedly resubmit unchanged URLs.
4. Monitor actual impressions/clicks over a meaningful period by country, page and query. The current one-impression samples cannot establish popular volume, keyword difficulty, conversion intent, or organic growth.

## Reproducible artifacts

- `artifacts/seo-gsc-20261012/live-indexing-audit.json`: timestamped 39-request metadata, canonicals, status/redirect chains, selected cache/robots headers, structural content observations and body hashes.
- `artifacts/seo-gsc-20261012/live-bodies/`: public unauthenticated response bodies.
- `artifacts/seo-gsc-20261012/live-indexing-audit.py`: bounded read-only audit script. Raw response headers containing possible `Set-Cookie` values are not saved in the report.
- `docs/SEARCH_INTENT_RESEARCH_20261012.md`: earlier query hypotheses and primary SERP sources, clearly separate from this owner-supplied Search Console sample.

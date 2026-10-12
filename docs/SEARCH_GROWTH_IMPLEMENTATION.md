# Organic discovery implementation — 12 October 2026

Later follow-up: [owner-supplied GSC URLs and query observations](GSC_FOLLOWUP_20261012.md) and [supporting pages/indexing implementation](SYSTEM_PAGES_AND_INDEXING_20261012.md). The latter expands policy SSR, public help/contact and private recovery pages. The query catalogue now includes 21 filters; the counts and validation below describe the earlier search implementation stage.

The first audience is **UAE teachers, especially British-curriculum teachers**, as selected by the owner. The implementation connects the searches teachers use to evaluate a service with useful public pages, readable answers, actual product limitations and current pricing. It does not promise a ranking, AI recommendation or a traffic increase.

## Research before copy

The [research memo](SEARCH_INTENT_RESEARCH_20261012.md) records **22 sampled search queries, eight intent groups and 26 primary source results**. The samples were not obtained from a UAE-localised Google account. They identify possible intent; they do not establish search volume, keyword difficulty, CPC or conversion. No paid keyword database or Search Console account was accessed.

| Teacher's buying question | Main acquisition page | What the page needs to answer |
| --- | --- | --- |
| Can I get an editable AI teaching PPT? | `/solutions/ai-ppt-maker-for-teachers-uae` | Native editable elements, PPTX download and a real file-edit check |
| Can I use my textbook PDF or teaching notes? | `/solutions/turn-teaching-notes-into-powerpoint` | Authorised upload, chapter/page selection, source review and PDF limitations |
| Will it fit a British curriculum lesson in the UAE? | `/solutions/british-curriculum-lesson-planning` | Year group, objective, prior learning, classroom context and a supplied specification |
| Can I prepare a GCSE/IGCSE lesson? | `/solutions/gcse-igcse-lesson-presentations` | Exam board, syllabus/examination year, tier and teacher-provided outcomes; no claimed endorsement |
| Can I keep my school design? | `/solutions/reuse-school-powerpoint-design` | Supported uploaded design workflow and export review |
| Can I fix one slide? | `/solutions/edit-ppt-without-regenerating` | Manual editing and targeted generation instead of an unrelated full-deck rebuild |
| Which tool should I buy? | `/solutions/how-to-choose-ai-presentation-maker-for-teachers` | A task-based evaluation checklist, export/accuracy/cost/privacy checks and a sample brief |
| How much will my teaching workload cost? | `/solutions/ai-lesson-planning-costs-and-credits` and `/pricing` | Actual plan catalogue, explicit Free/trial choice, rate assumptions and estimates before generation |

These are distinct task pages, not duplicate pages for every city, subject and year. Existing EAL, worksheet, quiz, differentiation and CBSE pages support the main clusters. Arabic and India-specific expansion require separate audience research and reviewed content; no untranslated Arabic alternate URL is advertised.

## What the optimisation terms mean here

| Area | Implemented approach |
| --- | --- |
| SEO | Relevant titles/descriptions, canonical URLs, crawlable public content, intentional internal links, public sitemap and protected private areas |
| GEO / AIO / LLMO | Plain server-rendered product answers, visible source links and review dates, consistent Clastio entity data and search-crawler access |
| AEO | Direct answers, practical examples, visible questions/answers and structured Article/Breadcrumb/entity data matching the page |
| SXO | British/UAE context, clear buyer routes, current AED pricing, Free-first CTAs, responsive reading and a smaller homepage client payload |
| Measurement | Search Console RE2 filters and a local CSV segmentation tool, plus the actual Google/Bing AI visibility reports |

Google's [current generative-AI search guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) treats useful content and technical SEO as the foundation. The optional `/llms.txt` resource index is maintained for readers/tools; it is not a ranking requirement. Structured data describes visible facts; no invented ratings, customers, addresses, prices, school endorsements or official curriculum approval are added. Public search-crawler access is separate from model-training preferences and from private-data authentication.

## Regex codes and local query analysis

The implementation is in [`search-query-patterns.ts`](../apps/web/lib/search-query-patterns.ts). It provides **18 overlapping filters** for brand, UAE location, British curriculum, GCSE/IGCSE, AI slides, teacher context, editable exports, document conversion, school designs, planning, editing, cost, free/trial, comparison, privacy, worksheets, assessment and differentiation.

These patterns segment observed queries. Putting regex strings or a list of keywords into page text does not improve ranking. A pattern match also does not prove that the searcher intends to buy.

Search Console → Performance → Search results:

1. Set **Country = United Arab Emirates**. This is stronger location evidence than requiring a query to contain “Dubai” or “UAE”.
2. Add **Query → Custom (regex) → Matches regex** and paste the `regex` value for the desired group. Use **Doesn't match regex** with the brand expression to isolate non-brand discovery.
3. Compare matching periods and inspect the associated Pages tab. Check which page is actually receiving the query; do not assume the intended mapping won.
4. Record clicks, impressions, CTR and relevant queries alongside indexed-page status. Do not interpret average position as an AI citation rank.

The [official filtering documentation](https://support.google.com/webmasters/answer/17011165?hl=en) specifies RE2, partial matching and case-insensitive matching by default. The provided expressions avoid lookarounds, backreferences and inline flags. Local matching uses equivalent case-insensitive JavaScript expressions; tests check both word orders, boundaries, positive/negative examples and CSV parsing.

Print all copyable expressions:

```sh
cd apps/web
npm run seo:queries -- --patterns
```

Export an English-language **Queries** CSV after selecting the UAE/date filters, then analyse it locally:

```sh
cd apps/web
npm run seo:queries -- /path/to/Queries.csv
```

The tool reads `Top queries`/`Query`/`Queries`, `Clicks` and `Impressions`; handles UTF-8 BOM, quoted fields, commas and CRLF; and returns counts/CTR by segment as JSON. It makes no network requests, uploads no data and rejects malformed metrics instead of silently reporting zero. CSV size is limited to 20 MiB and queries to 1,024 characters. Group totals overlap and must not be added together. Export limits and anonymised/omitted queries mean exported totals may differ from property-wide reports. The script does not invent search volumes or analyse a real account unless the owner supplies an export.

## Measure AI visibility using the available reports

- Google's [Search Generative AI performance reports](https://developers.google.com/search/blog/2026/06/gen-ai-performance-reports?hl=en) report impressions/pages/countries/devices/dates for supported generative search features; the announcement records worldwide rollout by 31 August 2026. Review the actual property report alongside the overall Web performance report. Do not invent a separate query-level AI rank.
- Bing's [AI Performance report](https://blogs.bing.com/webmaster/2026/2/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview/) measures citations and cited pages across supported surfaces. Its [June 2026 expansion](https://blogs.bing.com/search/2026/6/New-AI-Visibility-Insights-in-Bing-Webmaster-Tools-Intents-Topics-Citation-Share-Compare/) adds intent/topic/comparison views. These are reported citation measures, not guarantees that a page is recommended or ranked first.
- Connect discovery to real teacher outcomes: relevant visits, completed signup, first reviewed lesson/export and paid conversion. Search Console queries do not identify individual teachers. No new third-party tracking or behavioural profiling was installed in this work.

## Deployment and owner-controlled steps

Local implementation and browser checks do not publish this revision to `clastio.online` or create search-console properties. Deploy the reviewed web revision when authorised, preserving `NEXT_PUBLIC_SITE_URL=https://clastio.online` and the correct internal `API_URL`. Verify public HTML, canonical origin, OG image, sitemap, robots, pricing fallback and private-page noindex on the deployed service.

Then verify ownership in Google Search Console and Bing Webmaster Tools, submit the sitemap, inspect the important pages and collect a baseline. Check hosting/CDN bot controls too: an application robots rule cannot override a blocked crawler at the edge. Review actual UAE query and AI-visibility data before expanding pages or revising copy. Establish a teacher review process for new factual examples and source updates; changing a title or a build timestamp alone does not justify a new article review date.

The unresolved [legal-page audit](LEGAL_PAGES_AUDIT.md) and [launch checks](LAUNCH_AUDIT.md) still apply. Search metadata does not establish privacy compliance or fix payment/email/storage readiness.

## Validation

Final results:

- **32 frontend unit tests passed**, covering request handling, private PWA behavior, teaching scope, canonical/entity safeguards, public pricing boundaries and query/CSV segmentation. TypeScript and `git diff --check` passed.
- **Production Docker web build passed** on Next.js 16.3.8. Sixteen guide paths are prerendered; `/pricing` renders on demand using the configured public API. The new web image is running at `http://localhost:3005`; the API readiness endpoint is healthy.
- **Focused discovery browser check passed:** all 16 guides have readable server HTML without JavaScript, matching titles/descriptions/canonicals, Article/Breadcrumb data, real source/review dates where supplied, responsive 390/1280 layouts, functional buyer links and valid regex target routes. The 1200×630 PNG and private noindex/crawler controls also passed.
- **Existing discovery/assistant regression passed:** 13 original guides, three product pages, legal/status metadata, mocked monthly/yearly pricing and retry, production CSP, favicon, unknown-route 404 and clarify/confirm/remember interactions.
- **Isolated pricing SSR check passed:** configured plans in raw HTML, changed decimal prices, malformed/503 responses, JavaScript-disabled rendering, client refresh failure, retry recovery and yearly totals. No authenticated headers or cookies were forwarded by the server fetch; no paid calls were made.
- **The regex CLI passed:** 18 raw, copyable RE2 expressions print successfully; offline CSV/error/overlap checks passed. No owner's Search Console export was supplied or analysed.

Evidence: [final validation record](../artifacts/discovery-audit-20261012/validation.json), [pricing SSR check](../artifacts/discovery-audit-20261012/public-pricing-ssr.log), [technical research](../artifacts/discovery-audit-20261012/technical-research.md), [mobile homepage](../artifacts/discovery-audit-20261012/home-mobile.png), [desktop homepage](../artifacts/discovery-audit-20261012/home-desktop.png) and [content review](SEO_CONTENT_CHANGES_20261012.md).

Docker Desktop stopped during the initial build. It was restarted, the same app containers/database/storage were restored, and the retry build and final browser checks passed. Other stopped projects were not started or removed.

This is local implementation validation; no public deployment, indexing, ranking, traffic, AI citation, field Core Web Vitals or conversion result is claimed.

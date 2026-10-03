# Personal assistant and public discovery

## Image changes: discuss, clarify, confirm

From an image/concept slide, choose **Discuss image changes with your assistant**. The saved conversation is bound to that lesson and slide. It reads the current image, slide, selected chapter sources and confirmed teacher preferences, then asks up to three relevant questions: what should change, what should stay and which source to use. The first turn cannot offer a replacement button, even if the model prematurely produces a brief.

Once requirements are clear, the teacher reviews a replacement brief, its generation-credit cost and possible AI-image allowance use. Confirmation queues exactly one image replacement. Hybrid searches licensed Openverse images first; stock-only uses no paid AI image calls; AI requests a fresh image. This produces a replacement from a description, not a pixel-preserving edit of the original. Teachers can upload an exact replacement in the manual editor instead.

The server rejects foreign conversations, outdated briefs and changed slide versions. Confirmation replays return the existing job. Overlapping lesson updates are blocked. If no valid replacement is available, or its image bytes match the original, the original stays and no generation credits are consumed. A successfully generated AI image consumes its image allowance; a later export failure does not refund that provider work. Generation credits are consumed after the export saves successfully. Only the selected visual and its image attribution are replaced; the slide text and other slides are retained.

Conversations use existing `Conversation.channel = image_edit` and message JSON actions; no migration is required. `image_replacement` uses the existing AI queue, usage lock, plan limits and provider budget tracking. Image discussions use normal content/vision provider tokens but make no paid image calls. Replacement jobs make one attempt to avoid repeated paid calls on automatic retries.

## Memory with teacher control

Confirmed preferences guide the playground, image clarification, chapter planning and slide generation. Inferred preferences are suggestions to confirm; they no longer affect generation budgets automatically. Current explicit requests override remembered settings. The New chapter form no longer guesses Grade 8/Science when the teacher profile lacks those fields.

Teachers can manage image source and style in **Teacher memory**, explicitly say “Remember that I prefer diagrams for future lessons”, or opt into remembering style/source after a successful image replacement. One-off requests are not automatically made permanent. The remembered styles and sources are bounded enums. Other preferences and notes remain editable/deletable through the existing memory page.

`app/services/teacher_signals.py` contains bounded regex for image-change routing, slide numbers and explicit supported memory requests. Negated or ambiguous requests are not saved. Regex is a routing/extraction aid, not a substitute for understanding a teacher's requirements. Memory retrieval falls back to owner-scoped lexical matching across up to 60 recent notes when embeddings are unavailable or return no matching rows. Explicitly confirmed source preferences also apply to backend-created courses using automatic image mode. Chapter sources and teacher memory remain private.

## Public pages and search

`/solutions` links thirteen distinct, server-rendered guides:

- `/solutions/ai-ppt-maker-for-teachers-uae`
- `/solutions/lesson-planning-for-uae-teachers`
- `/solutions/eal-lessons-uae`
- `/solutions/british-curriculum-lesson-planning`
- `/solutions/cbse-lesson-planning-uae`
- `/solutions/edit-ppt-without-regenerating`
- `/solutions/personal-ai-teaching-assistant`
- `/solutions/worksheet-maker-for-uae-teachers`
- `/solutions/quiz-and-exit-ticket-maker`
- `/solutions/differentiated-lesson-presentations`
- `/solutions/turn-teaching-notes-into-powerpoint`
- `/solutions/reuse-school-powerpoint-design`
- `/solutions/stock-images-for-teaching-presentations`

Each includes a direct answer, practical steps, an example teacher prompt, common questions, related guides, a canonical URL, Open Graph/Twitter metadata, Article and Breadcrumb JSON-LD. The homepage links the guides and includes Organization, WebSite and SoftwareApplication JSON-LD. The content avoids invented endorsements, review counts, school affiliations or curriculum certification. Unknown/malformed guide slugs return 404 using a bounded regex plus an exact allowlist; JSON-LD escapes `<` to prevent script termination.

The sitemap includes public guides and excludes sign-in/app pages. Robots allows public crawling and disallows teacher/admin areas; private app pages also retain noindex metadata/headers. The default canonical origin is `https://clastio.online` rather than localhost. `/llms.txt` provides an optional public resource index; it is not a Google indexing requirement or ranking guarantee.

SEO, GEO, AIO and LLM discoverability are supported by clear public text, meaningful internal links and matching metadata. Public guides do not start authenticated activity polling, avoiding unnecessary account calls during public page rendering. SXO is addressed through mobile layouts, a table of contents, clear trial/plan links and task-oriented guidance. These changes do not guarantee a first-place ranking in the UAE. Google's official guidance says its normal SEO practices apply to AI search, with no special AI file/schema requirement: https://developers.google.com/search/docs/appearance/ai-features . Bing's webmaster guidelines also apply to AI search: https://www.bing.com/webmasters/help/bing-webmaster-guidelines-30fba23a .

## Deployment and measurement

Follow [the complete Render/Railway launch guide](RENDER_RAILWAY_LAUNCH_GUIDE.md) for database, storage, authentication, email, workers, payments and production verification.

Deploy the Render frontend and restart/redeploy Railway API and AI workers so the new handler is registered. Set `NEXT_PUBLIC_SITE_URL=https://clastio.online`, keep Openverse enabled on API/workers and configure live text/vision and image providers within the existing AI budgets. No database migration is needed.

After deployment, test an image discussion, corrected requirements, confirmation, provider availability, missing allowance, stale-slide rejection, style memory and manual upload. External AI/Openverse retrieval and database concurrency are mocked in local tests; production smoke tests remain necessary. Verify public pages, canonical origins, sitemap and robots at the live domain.

To measure actual discovery, verify site ownership in Google Search Console and Bing Webmaster Tools, submit `https://clastio.online/sitemap.xml`, inspect a new guide, and monitor UAE impressions, relevant teacher queries, indexed pages and signup conversion. Verification/submission require the owner's search-console access and were not performed from this workspace. Track real results before extending the content with additional teacher questions; keep any calendar/curriculum claims sourced and current.

## Validation

- API: `cd apps/api && ./.venv312/bin/python -m pytest unit_tests/test_launch_pricing.py unit_tests/test_engagement.py unit_tests/test_smart_assistant.py unit_tests/test_efficient_edits.py unit_tests/test_teacher_images.py unit_tests/test_stock_presentations.py unit_tests/test_playground.py -q`
- Web: `cd apps/web && npm run typecheck && npm run build`
- Browser against a local server on port 3100: `cd apps/web && node e2e/smart-assistant-seo.mjs`. Uses mocked authenticated API responses and Chrome; checks public server HTML, metadata/schema, sitemap, robots, invalid routes, responsive layouts and clarify/confirm/remember UI. It does not invoke live AI or payments.

Current local results: 63 targeted API tests and four web unit tests pass; the production build passes. Two consecutive production browser regressions pass across 13 guides, three product pages, monthly/annual prices, pricing retries and the image clarification flow with no page errors. The inline theme boot script now comes from a server-safe module instead of being a reference to an export in a client-only module; the previously observed hydration warning did not recur in these checks. Browser and gateway checks use mocks; live database concurrency, payment checkout, production AI retrieval and deployment still require a production smoke test.

## Expanded public pages

Six additional guides cover worksheet generation, quizzes/exit tickets, differentiated presentations, teaching-note sources, school design references and stock/uploaded images. Dedicated `/how-it-works`, `/for-schools` and `/faq` pages describe the actual workflow, a school pilot and product limits. Navigation, footer, homepage, sitemap and the optional public resource index link these pages. They do not invent school customers, reviews, endorsements or guaranteed outcomes. The FAQ describes credits rather than a fixed unlimited PPT count.

Launch price defaults and the explicit existing-database rollout command are documented in `ENGAGEMENT_AND_BILLING.md`. Changing source defaults does not silently rewrite existing catalogue rows or payment subscriptions.

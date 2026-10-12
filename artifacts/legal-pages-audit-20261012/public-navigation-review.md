Checked the public site at http://localhost:3005 on 12 October 2026. This review used public GET requests and an anonymous browser; no account or server-side data was changed.

All five known legal pages and APIs returned 200 and rendered their published v1.0 documents, effective 26 September 2026. Footer and sidebar links are present. Desktop and mobile Privacy layouts have no horizontal overflow, and no JavaScript errors occurred.

| Public document | Page / API | Version |
| --- | --- | --- |
| Terms | 200 / 200 | 1.0 |
| Privacy | 200 / 200 | 1.0 |
| Acceptable use | 200 / 200 | 1.0 |
| Cookies | 200 / 200 | 1.0 |
| Refunds | 200 / 200 | 1.0 |

The published Privacy page still displays privacy@pptgenie.example and “replace with your real contact”. Its AI-provider paragraph names Anthropic, OpenAI and Google and asserts processing without model training under agreements. These published statements need reconciliation with the actual operator and provider setup before launch. Every published document still contains the template-review notice.

Signup links Terms, Acceptable Use and Privacy. Required acceptance and optional marketing start unchecked; Create account is disabled before policy acceptance. Cookie customization starts with analytics unchecked and links the Cookie Policy. No public cookie-choice reopen control exists; signed-in Settings provides one.

/legal, /contact, /legal/dmca, /legal/accessibility and /legal/ai_data return 404. Anonymous /support redirects to sign-in. Unsupported document types and missing API versions return 404. Backend DMCA support has no published document and no matching frontend route whitelist.

Only v1.0 is published for each current document, so no history selector appears. Code review found that the selector assumes the first history version is current, which can fail when a published version has a future effective date. Selected history versions are not reflected in or read from the page URL. No historical documents were published or modified to test these paths.

The absence of separate accessibility or AI-data pages is recorded as a product/documentation gap, not a finding that either page is legally mandatory. Detailed route evidence is in public-browser.json; the public Privacy page is captured in privacy-mobile.png.

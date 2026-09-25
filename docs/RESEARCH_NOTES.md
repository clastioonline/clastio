# AI Teacher Assistant — Research Notes

_Research date: September 2026. These findings drive the changes made in `PRODUCT_SPEC.md`._

---

## 1. Market: who the UAE teacher actually is

| Finding | Implication for the product |
|---|---|
| Dubai (KHDA) regulates ~227 private schools, 17 curricula, ~390k students. Abu Dhabi (ADEK) oversees ~219 private schools. | The UAE is a **multi-curriculum** market. A "curriculum" field on its own isn't enough. Each curriculum needs its own framework, grade naming and outcome codes. |
| Dubai private-school enrolment by curriculum: British ~35–37%, Indian (CBSE/ICSE) ~32%, American ~15%, IB ~8%, UAE MoE ~5%, others ~3%. | Launch with **British (UK National Curriculum / IGCSE / A-Level), Indian (CBSE/NCERT), American (Common Core / NGSS)** and IB (PYP/MYP/DP). Add MoE after that. Indian-curriculum teachers in the UAE also give a natural route into the **India** launch. |
| All regulators (KHDA, ADEK, SPEA) now use the **UAE Unified School Inspection Framework**. | Lesson plans should be "inspection-ready" by default: clear objectives, success criteria, differentiation, assessment for learning, links to national identity and moral education, and support for students of determination. This is a strong selling point on its own. |
| Schools must also teach Arabic, Islamic Education, and UAE Social Studies and Moral Education. | Arabic and **RTL slide rendering** are needed from day one, not later. Many teachers teach bilingual groups. |
| The UAE MoE made **Artificial Intelligence a subject from KG to Grade 12 starting in 2025–26**, in public and private schools. It covers seven areas: foundations, data and algorithms, software applications, ethics, real-world applications, innovation and project design, and policy and community. 22,000 teachers are being trained. | **A clear way in.** Thousands of teachers are teaching a new subject without mature materials. Ship a pre-built "UAE AI Curriculum" course pack. The MoE also stresses **verifying AI output and ethical AI use**, so the product should be transparent about AI (sources, fact-check flags, optional disclosure). |
| A large share of students are EAL (English as an additional language) learners. | Built-in EAL scaffolds: key-vocabulary slides, bilingual glossaries and simplified reading levels. |

## 2. UAE school-calendar facts that affect planning

- The academic year runs roughly late August to early July, in **3 terms**, on a unified calendar.
- The week is **Monday to Friday, with a shortened Friday**. The timetable model needs different period lengths for each day.
- **Ramadan**: schools shorten the day under regulator rules, so periods get shorter. The planner must compress lessons automatically during Ramadan, not just move them.
- Public holidays such as Eid (which moves with the lunar calendar) and National Day shift dates, so the weekly planner needs a holiday-aware calendar.

## 3. Competitors

| Product | Strength | Gap we exploit |
|---|---|---|
| MagicSchool | 80+ teacher tools, good free tier, US standards | Generic output. No teacher design memory. Single lessons, not connected courses. Weak on PPTX. |
| Brisk Teaching | Chrome extension inside Google Docs/Slides | Tied to the browser. No long-term memory of curriculum progress. |
| Gamma / Curipod | Good-looking decks | Output is in *their* design, not the teacher's. No curriculum sequencing. |
| Storyflow | Visual unit planning | No teacher-template PPTX output. |

**Positioning:** no competitor combines (1) **the teacher's own slide design system**, (2) **memory of what has been taught and how it went**, and (3) **daily delivery via WhatsApp**. The spec is built around these three.

## 4. WhatsApp Business Platform

- Since July 2025 pricing is **per template message**, not per conversation.
- **From 1 October 2026, utility templates are charged per message even inside the 24-hour customer-service window.** Free-form replies inside the window are still free.
- Business-initiated messages sent more than 24 hours after the user's last message **must use pre-approved templates**.

**Design decisions:**
1. Send **one consolidated daily message**, not one per class.
2. Get users to reply (quick-reply buttons such as "Show today's plan"). A reply opens a free service window, and the detail is sent as free-form messages.
3. Record the cost of every message in the usage ledger. Count WhatsApp messages as a metered resource on each plan.
4. Explicit opt-in, easy opt-out ("STOP"), and quiet hours.
5. Use only the official Cloud API, either directly or through a BSP.

## 5. Data protection

- **UAE PDPL (Federal Decree-Law 45/2021)** has been in force since January 2022. It requires a stated purpose and a lawful basis, disclosure of third parties, and protection for cross-border transfers (to countries deemed adequate or with safeguards).
- **India DPDP Act 2023** applies to the India launch.
- **Design decisions:**
  - **Collect no student personal data by default.** Class profiles are aggregates ("7B: mixed ability, 40% EAL"), not student lists.
  - If rosters are ever added (for example, for marking), they are opt-in, pseudonymised and never sent to AI providers.
  - Strip PII from prompts. Sign DPAs with AI providers and use settings that exclude our data from training.
  - Configurable **data region** (UAE or EU) for storage. Record where each AI provider processes data.
  - Consent records, data export and account deletion.
  - Treat uploaded documents as **untrusted input** (prompt-injection defence).

## 6. Payments

- **Stripe** operates in the UAE (about 2.9% + AED 1 for domestic cards) and has the most complete subscription tooling (Billing, customer portal, webhooks, proration).
- Local alternatives: **Telr**, **PayTabs**, **Network International** (lower rates, useful for B2B school invoicing).
- A merchant of record such as **Paddle** handles UAE VAT, EU VAT and other taxes if we sell internationally.
- UAE **VAT is 5%**. Invoices need our TRN once registered.
- India: **Razorpay** (UPI Autopay, cards), 18% GST, INR pricing.
- **Decision:** a `PaymentProvider` abstraction. Stripe first, Razorpay for India, bank transfer or invoicing for school contracts.

## 7. Technical research that changes the architecture

1. **Read PPTX design from the XML, not with vision.** A PPTX contains its theme colours, theme fonts, slide masters, layouts and placeholder geometry. Parsing these with `python-pptx` and `lxml` is exact, free and deterministic. Use vision models only for PDFs or images, where no structure exists.
2. **Keep the teacher's real slide master.** For PPTX uploads, the best result comes from cloning the teacher's file, removing the slides, and keeping the masters and layouts as the template. Generated decks then *are* the teacher's design. Rebuilding a template from extracted values is the fallback, used only for PDF uploads.
3. **Use one renderer.** Use `python-pptx` on the server and don't run it alongside PptxGenJS. Two renderers mean two layout engines and inconsistent QC.
4. **Convert legacy `.ppt` to `.pptx`** with LibreOffice headless before analysis.
5. **Visual QC** renders PPTX to PDF and then to PNG (LibreOffice headless + PyMuPDF). Overflow detection can mostly be done *before* rendering by measuring text with the actual font metrics (Pillow/fontTools). Render-based checks then confirm the result.
6. **Native editable diagrams.** Build cycles, processes, timelines and comparisons as PPTX shapes and connectors, not images, so teachers can edit them. Build maths as OMML equations, not pictures.

## 8. Issues found in the original brief

| Issue | Fix in the spec |
|---|---|
| Pricing: AED 99 for "20 PPTs" is high next to competitors with free or low-cost individual tiers, and the four tiers overlap. | Credit-based plans, a stronger free trial, annual discount, and a **School/Department plan** where most UAE revenue sits. Limits stay admin-configurable. |
| No differentiation or SEND support, although UAE inspections expect it. | Differentiation engine (support / core / extension), students of determination, EAL. |
| No curriculum standards data, so "curriculum alignment" couldn't be checked. | Standards library with outcome codes, plus a coverage tracker. |
| Memory only records what was *generated*, not what *happened in class*. | **Post-lesson reflection loop** (a one-tap WhatsApp or web check-in) that updates pacing and next-lesson planning. |
| Factuality QC with no ground truth. | Teacher-uploaded textbooks and syllabi as **grounding sources**, with citations. |
| No evaluation method for "better than generic generators". | Golden test set, rubric scoring, human ratings, regression gates on prompt changes. |
| Arabic/RTL missing. | First-class bilingual support. |
| Copyright of uploaded third-party decks (publisher material). | Style extraction is allowed. Reusing content needs the teacher's confirmation that they have the rights. Attribution is kept. |
| No accessibility requirements. | WCAG 2.2 AA app, alt text on slides, contrast checks, a dyslexia-friendly option. |

## Sources

- [UAE MoE AI curriculum from 2025–26 (UAE BARQ)](https://www.uaebarq.ae/en/2025/05/04/ministry-of-education-introduces-ai-curriculum-in-public-schools-starting-from-2025-2026-academic-year/)
- [Gulf News: UAE schools to introduce AI curriculum](https://gulfnews.com/uae/education/uae-schools-to-introduce-ai-curriculum-in-new-academic-year-1.500242831)
- [The National: how UAE schools are introducing AI (Sept 2026)](https://www.thenationalnews.com/news/uae/2026/09/24/more-ai-but-no-more-screen-time-how-uae-schools-are-introducing-artificial-intelligence-to-pupils/)
- [Middle East AI News: 1,000 teachers deployed for AI curriculum](https://www.middleeastainews.com/p/uae-deploys-school-teachers-for-ai)
- [Education in Dubai (Wikipedia)](https://en.wikipedia.org/wiki/Education_in_Dubai)
- [UAE Education System Explained: KHDA, ADEK, Curricula and Inspections](https://thearabianpost.com/uae-education-system-guide/)
- [UAE school curricula compared 2026](https://www.uaeexperthub.com/uae-school-curricula-compared/)
- [Meta: Pricing on the WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [Gulf Business: WhatsApp Business pricing changes from July 1](https://gulfbusiness.com/en/2025/world/starting-july-1-whatsapp-business-rolls-out-major-pricing-changes/)
- [Wati: message-based pricing explained](https://support.wati.io/en/articles/11561662-message-based-pricing-all-you-need-to-know)
- [UAE Government: data protection laws](https://u.ae/en/about-the-uae/digital-uae/data/data-protection-laws)
- [Securiti: overview of UAE PDPL](https://securiti.ai/uae-personal-data-protection-law/)
- [PaySelect: recurring billing in the UAE 2026](https://www.payselect.ae/newsroom/recurring-billing-and-subscription-payments-in-the-uae-the-2026-merchant-guide)
- [Framnex: best payment gateways in the UAE](https://framnex.com/en-ae/blog/guides/best-payment-gateway-uae)
- [VAT for SaaS in the UAE](https://www.ourtaxpartner.com/vat-applicability-for-saas-and-online-subscription-businesses-in-the-uae/)
- [Brisk vs MagicSchool (2026)](https://academicaitrends.com/blog/brisk-teaching-vs-magicschool-ai/)
- [Best AI tools for teachers 2026 (Storyflow)](https://storyflow.so/blog/best-ai-tools-for-teachers-2026)

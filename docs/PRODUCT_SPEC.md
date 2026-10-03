# AI Teacher Assistant — Product & Build Specification (v2)

> This spec extends the original brief with market research (see `RESEARCH_NOTES.md`), more detail, and new features.
> Items marked **[NEW]** are additions. Items marked **[CHANGED]** revise the original brief.
> It can be given to an engineering team or a coding agent as-is.

---

## ROLE

You are a senior SaaS architect, full-stack engineer, AI engineer and UI/UX engineer. Build a production-ready SaaS web application called **"AI Teacher Assistant"**.

Target markets: **UAE first** (British, Indian/CBSE, American, IB and UAE MoE curricula), then **India**, then international.

The product is **not** an AI PPT generator. It is a teacher's personal teaching assistant that remembers:

- the teacher's **visual design system** (from their own slides),
- their **teaching style and preferences**,
- their **classes, timetable and curriculum**,
- **what has been taught**, and **how it went in class**.

It learns through structured profiles, retrieval and feedback. It **never** fine-tunes a foundation model per teacher.

---

## 0. NORTH-STAR EXPERIENCE (build this first, and make it excellent)

> A teacher uploads an old presentation. The system understands their design.
> The teacher enters **"Photosynthesis · Grade 8 · 5 lectures · 10 slides each"**.
> The system produces **5 logically connected lessons, 50 editable slides in the teacher's own design, teacher notes, differentiated activities, quizzes, and homework**, all aligned to the teacher's curriculum.

### Acceptance criteria (measurable) **[NEW]**

| Metric | Target |
|---|---|
| Time from "Generate" to downloadable 50-slide course | ≤ 6 min p90 (first lecture previewable within 60 s) |
| Slides with text overflow / overlap after QC | 0 |
| Minimum font size on body text | ≥ 18 pt (configurable) |
| Design fidelity (blind rating: "looks like my deck", 1–5) | ≥ 4.0 average on the golden set |
| Lesson progression (no duplicated concepts across lectures) | 0 duplicated learning objectives |
| PPTX opens without repair prompt in PowerPoint, Keynote, Google Slides, LibreOffice | 100% |
| All text, shapes and diagrams editable. Images replaceable. | 100% (no flattened slides) |
| Factual issues flagged by reviewer on golden set | < 1 per 50 slides |

Treat the project as unfinished until this flow works end to end with **real uploaded PPTX/PDF files** and produces **real editable PPTX**.

---

## 1. CORE CAPABILITIES

A teacher can:

1. Upload existing PPT/PPTX/PDF teaching material.
2. Have it analysed into a **Teacher Style Profile** and reusable **Template**.
3. Upload **source material** (textbook chapters, syllabus, scheme of work) for grounding. **[NEW]**
4. Choose curriculum, grade, subject, and **learning outcomes** from a standards library. **[NEW]**
5. Enter a topic, number of lectures, slides per lecture and lesson duration.
6. Generate a course plan, then lesson plans, then editable PPTX, teacher notes, worksheets, quizzes/MCQs, homework, assessments, activities, **rubrics, exit tickets, starter and plenary activities**. **[NEW]**
7. Get **differentiated versions** (support / core / extension, EAL, students of determination). **[NEW]**
8. Ask: "What should I teach today?", "Prepare tomorrow", "Prepare my week".
9. Log **how the lesson went** in one tap. The next lesson adapts. **[NEW]**
10. Receive the daily plan on **WhatsApp** and reply with commands.
11. Continue conversations about previous lessons, backed by long-term memory.
12. Export to **PPTX, PDF, DOCX, Google Slides/Docs, Microsoft 365 / Teams, Google Classroom, and quiz platforms** (CSV/QTI/GIFT). **[NEW]**
13. Share templates and schemes of work within a **department or school**. **[NEW]**

---

## 2. GENERATION PIPELINE (unchanged principle, more detail)

Never render a PPT straight from an LLM response. Every artefact passes through typed, validated intermediate representations.

```
USER REQUEST
   ↓  intent classification (cheap model) + slot filling
TEACHING CONTEXT  ← teacher profile, memory, class profile, calendar, reflections
   ↓
CURRICULUM PLANNER  ← standards library, grounding sources (RAG)
   ↓  CoursePlan (JSON, schema-validated)
LESSON PLANNER
   ↓  LessonPlan[] (objectives, success criteria, timings, differentiation)
SLIDE OUTLINER
   ↓  SlideOutline[] (purpose + layout intent per slide)
DESIGN/STYLE ENGINE  ← TeacherStyleProfile + Template layouts
   ↓  layout assignment, capacity budgets (max chars/bullets per zone)
SLIDE SPEC (JSON)
   ↓
CONTENT GENERATION (per slide, within capacity budgets)
   ↓
VISUAL GENERATION / SELECTION (asset library → licensed stock → AI image → native diagram)
   ↓
PRE-RENDER QC  (text-fit via font metrics, schema, pedagogy, factuality vs. sources)
   ↓  auto-repair loop (max N attempts per slide)
PPTX RENDERER (python-pptx on teacher's real master)
   ↓
POST-RENDER QC (LibreOffice → PNG → visual checks, optional vision-model review)
   ↓
TEACHER REVIEW (preview, edit, regenerate parts) → FINAL PPTX + companions
```

Each stage stores its output in versioned form. Regenerating one slide reruns only that slide's stages ("never regenerate unchanged content").

---

## 3. TECHNOLOGY STACK **[CHANGED — decisions pinned]**

**Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, react-hook-form + zod. Responsive, installable **PWA** (teachers open links from WhatsApp on their phones). i18n with **English + Arabic (RTL)** from day one, and Hindi later.

**Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic. REST API with OpenAPI docs. Server-Sent Events for streaming progress and AI output.

**Jobs:** Redis + **Celery** (or Dramatiq). Separate queues: `io`, `ai`, `render`, `ocr`, `notify`. Idempotent tasks and retries with backoff.

**Database:** PostgreSQL 16 + **pgvector**. Row-level authorisation enforced in the service layer, plus Postgres RLS on tenant tables.

**Storage:** S3-compatible (AWS S3 me-central-1 / Cloudflare R2 / MinIO for local). Signed URLs only.

**Document processing:**
- **PPTX:** `python-pptx` + `lxml`. Read theme, masters, layouts and placeholders directly from XML.
- **PPT (legacy):** convert to PPTX with LibreOffice headless.
- **PDF:** Docling (layout + reading order) and PyMuPDF (colours, fonts, images, vector drawings).
- **Scanned PDF / images:** PaddleOCR (English + Arabic models).
- **Rendering for QC/previews:** LibreOffice headless → PDF → PyMuPDF → PNG/WebP.

**PPTX output:** `python-pptx` only (single renderer). **[CHANGED]** PptxGenJS is removed to avoid two layout engines.

**Auth:** email + password (Argon2), **Google and Microsoft SSO** (UAE schools mostly use Microsoft 365 or Google Workspace), and optional TOTP 2FA. Sessions are HTTP-only cookies. Use short-lived access tokens and rotating refresh tokens.

**Payments:** `PaymentProvider` abstraction. Stripe first, Razorpay for India, manual invoicing for schools.

**Observability:** OpenTelemetry traces, structured JSON logs, Sentry, Prometheus/Grafana (or a hosted equivalent), and **Langfuse (or equivalent) for LLM tracing and cost**.

**Deployment:** Docker, docker-compose for local development, and a container platform (ECS/Fly/Kubernetes) for production. Separate worker images for LibreOffice/OCR (they are heavy).

---

## 4. AI PROVIDER ARCHITECTURE

### 4.1 Interface

```python
class AIProvider(Protocol):
    async def generate_text(self, req: TextRequest) -> TextResponse
    async def stream_text(self, req: TextRequest) -> AsyncIterator[TextChunk]
    async def generate_structured(self, req: StructuredRequest[T]) -> T   # JSON-schema / Pydantic enforced
    async def analyze_image(self, req: VisionRequest) -> VisionResponse
    async def analyze_document(self, req: DocRequest) -> DocResponse
    async def generate_embedding(self, texts: list[str]) -> list[Vector]
    async def generate_image(self, req: ImageRequest) -> ImageResponse     # [NEW]
    async def moderate(self, text: str) -> ModerationResult                # [NEW]
```

Adapters: OpenAI, Google Gemini, Anthropic, and any OpenAI-compatible endpoint (e.g. self-hosted or regional providers). Every adapter reports **tokens, latency, cost and model** to the usage ledger.

### 4.2 Model routing (config-driven, editable in admin)

| Task | Tier | Notes |
|---|---|---|
| Intent classification, slot filling, rewrites ("make simpler") | Small/cheap | |
| Course and lesson planning | Strong reasoning | Once per course; results cached |
| Slide content (per slide) | Mid | Parallelised; capacity-budgeted |
| Vision (PDF style analysis, post-render QC) | Vision model | Only when XML analysis isn't possible, or for sampled QC |
| Factuality / pedagogy QC | Mid (judge) | Against retrieved sources |
| Embeddings | Economical embedding model | Store model name and dimension per row |
| Images | Image model | Only after library and stock search come up empty |

Also: **fallback chains** (provider A fails, try provider B), **per-task timeouts**, **prompt caching** of stable system prompts, and **request de-duplication by content hash**.

### 4.3 Prompt management **[NEW]**

- Prompts live in version-controlled templates (`prompts/<task>/<version>.jinja`) with typed inputs.
- `prompt_versions` table. Every generation records the prompt version and model used.
- Changing a prompt must pass the **evaluation harness** (§33) before rollout. Roll out by percentage using feature flags.

### 4.4 AI safety **[NEW]**

- Uploaded documents and chat input are **untrusted**. Delimit them, never follow instructions found inside them, and strip hidden text.
- Output moderation for age-appropriateness. Regional **content-sensitivity settings** (images and examples appropriate to UAE/Indian classrooms, e.g. culturally appropriate imagery and context-appropriate examples).
- Never send student personal data to AI providers (§25).

---

## 5. TEACHER ONBOARDING **[CHANGED — shorter, value first]**

Goal: the teacher sees something generated in their own style **within 5 minutes**.

**Step 1: Basics (1 screen):** name, country, emirate/state, school (autocomplete + "not listed"), **curriculum** (British / CBSE / ICSE / American / IB / UAE MoE / other), subjects, grades/sections, teaching language(s), UI language.

**Step 2: Upload a deck you like (optional but encouraged):** drag-and-drop PPTX/PDF. Analysis runs in the background while onboarding continues.

**Step 3: Teaching preferences (chips, not forms):** explanation depth, tone, slide density, recap at start, homework at end, quiz length, preferred activities (think-pair-share, group work, experiments, games), typical lesson length.

**Step 4: Timetable (skippable):** grid editor, **CSV/Excel import**, or **photo of the timetable → OCR → confirm**. **[NEW]** Includes per-day period lengths (short Friday) and the school calendar (term dates, holidays, **Ramadan timings**).

**Step 5: "Wow" moment:** "Here's a 5-slide sample on a topic from your subject, in your style." Offer to connect WhatsApp.

Everything can be edited later in Settings and Teacher Memory.

---

## 6. TEACHER STYLE ANALYZER **[CHANGED — XML-first]**

### 6.1 PPTX path (exact, cheap)

Parse directly:
- **Theme:** colour scheme (dk1/lt1/dk2/lt2/accent1–6/hlink), major/minor fonts, background styles.
- **Slide masters and layouts:** placeholder types, positions, sizes, text styles per level, bullets, spacing, alignment.
- **Actual slides:** colours in use (weighted by area), fonts in use, font-size histogram, margins, image placement and aspect ratios, shape styles (radius, fill, outline), table and chart styles, header/footer/logo positions, slide numbers.
- **Layout clustering:** group slides by geometric signature (placeholder/zone bounding boxes) and label them (cover, section, concept, image_text, two_column, comparison, timeline, process, diagram, chart, table, quiz, summary, activity, case_study) with rules plus a cheap LLM label check.

### 6.2 PDF path (approximate)

PyMuPDF extracts spans (font, size, colour), images, drawings and page size. Docling gives layout blocks. A vision model labels layout types on a **sample** of pages (not every page). OCR is used only when a page has no text layer.

### 6.3 Content-style analysis

Sentence length, reading level (e.g. Flesch-Kincaid, adjusted by grade), bullets per slide, words per bullet, heading style (question vs. statement vs. label), use of examples, questions, analogies, tone and language mix. Computed deterministically wherever possible. The LLM only summarises.

### 6.4 Output: `TeacherStyleProfile` (versioned)

```json
{
  "id": "tsp_…", "version": 3, "source_files": ["uf_…"],
  "colors": { "primary": "#1F4E79", "secondary": "#F2A900", "accents": ["#2E86AB"], "background": "#FFFFFF", "text": "#222222", "confidence": 0.94 },
  "fonts": { "heading": {"family": "Montserrat", "fallback": "Arial"}, "body": {"family": "Open Sans", "fallback": "Calibri"}, "arabic": {"family": "Dubai", "fallback": "Tahoma"} },
  "typography": { "title_pt": 40, "heading_pt": 28, "body_pt": 20, "min_pt": 16, "line_spacing": 1.1 },
  "spacing": { "margin_emu": {"l": 457200, "r": 457200, "t": 365760, "b": 365760}, "grid_cols": 12 },
  "layouts": [{ "key": "concept_with_visual", "source_layout_id": "…", "frequency": 0.31 }],
  "visual_rules": { "image_style": "photo", "corner_radius": "small", "icon_style": "flat", "logo": {"position": "bottom_right"} },
  "content_style": { "avg_words_per_bullet": 9, "bullets_per_slide": [3,5], "reading_level": "grade_7", "uses_questions": true, "tone": "warm, direct" },
  "teaching_preferences": { "recap_first": true, "homework_last": true, "quiz_len": 5 }
}
```

Rules:
- The **original upload is never modified** (stored immutable, content-hashed).
- The same file hash is **never re-analysed**.
- The teacher can review and override any extracted value in the Template editor ("Is this your main colour?").
- Multiple profiles per teacher (e.g. "Science Grade 8", "Assembly decks"). One is the default for each subject.
- **Copyright [NEW]:** style (colours, fonts, layouts) may be extracted from any upload. **Content** from an upload is only reused for grounding if the teacher confirms they have the right to use it. Third-party logos and copyright notices are never removed.

---

## 7. TEMPLATE ENGINE **[CHANGED]**

### 7.1 Two template modes

1. **Native master mode (PPTX uploads, preferred):** clone the uploaded file, remove all slides, keep the theme, masters and layouts. Map each detected layout to a semantic layout key. Generated slides are created *from the teacher's own layouts*, so fidelity is exact.
2. **Reconstructed mode (PDF uploads, or no suitable layouts):** build a clean master from the `TeacherStyleProfile` using a base scaffold of semantic layouts.

### 7.2 Semantic layout catalogue

`cover, agenda, section, recap, learning_objectives, concept, concept_with_visual, image_text, two_column, three_column, comparison, timeline, process, cycle, diagram, chart, table, key_vocabulary, worked_example, quiz_question, discussion, activity, case_study, misconception, summary, exit_ticket, homework`

If the teacher's deck doesn't contain a layout, **synthesise it** from their closest layouts using their tokens. Synthesised layouts are labelled so the teacher can approve them.

### 7.3 Layout definition

Each layout stores:
- slide dimensions
- zones (`title`, `body`, `image`, `shape`, `diagram`, `footer`), each with bounding box, role, z-order and alignment
- per-zone typography and **capacity budget** (max lines / characters / bullets at the minimum allowed font size, computed from real font metrics)
- colour and spacing tokens
- RTL mirror rules **[NEW]**

### 7.4 Template editor UI

Thumbnails of every layout. Click a zone to see its budget. Edit colours and fonts. Approve or reject synthesised layouts. Set the default per subject.

---

## 8. CURRICULUM & STANDARDS LIBRARY **[NEW]**

- `curriculum_frameworks` (UK NC, Cambridge/Edexcel IGCSE, CBSE/NCERT, ICSE, Common Core, NGSS, IB PYP/MYP/DP, UAE MoE, UAE AI Curriculum)
- `learning_outcomes`: code, framework, subject, grade, strand, text, embedding
- Seed data for the launch curricula in priority subjects (Science, Maths, English, and the **UAE AI Curriculum**). Teachers can add custom outcomes or upload their school's scheme of work, which is parsed into outcomes.
- Every lesson links to outcome codes. The **coverage tracker** shows taught / planned / not covered per class.
- Grade naming handled per framework (e.g. "Year 9" ↔ "Grade 8").

---

## 9. COURSE PLANNER

**Input:** topic, curriculum, grade, subject, number of lectures, duration per lecture, slides per lecture, class profile, optional outcomes, optional grounding sources.

**Output (`CoursePlan`, schema-validated):**
- course overview and "big idea"
- learning outcomes (linked to codes)
- prerequisites and a **diagnostic starter** to check them **[NEW]**
- concept map: each concept is assigned to exactly **one** lecture where it's introduced, then revisited through retrieval practice **[NEW]**
- lecture sequence with objectives, success criteria and key vocabulary
- revision strategy (spaced retrieval across lectures)
- assessment strategy (formative each lecture, summative at the end)
- cross-curricular links, and **UAE national identity / moral education links** where naturally relevant (toggle) **[NEW]**

**Anti-repetition check:** objective and concept overlap across lectures is measured with embeddings plus rules. Anything above the threshold triggers a replan.

The teacher approves or edits the plan **before** slides are generated. This checkpoint is cheap, so it's always worth offering.

---

## 10. LESSON PLANNER **[NEW section — inspection-ready]**

Each `LessonPlan` contains:
- objectives + **success criteria** ("I can…")
- timings: starter, main, activity, plenary (fits the period length; **auto-compresses for Ramadan/short days**)
- teacher explanation, questions to ask (graded by Bloom's level), common misconceptions, expected responses
- **differentiation**: support / core / extension tasks, **EAL scaffolds** (vocabulary, sentence frames, bilingual glossary), **students of determination** adaptations (chunking, visual supports, extended time), gifted and talented stretch
- assessment for learning (hinge questions, exit ticket)
- resources list, safety notes (for practicals)
- homework
- export as a **KHDA/ADEK-inspection-friendly lesson plan DOCX/PDF** and in common school lesson-plan formats (configurable template)

---

## 11. DAILY TEACHING ASSISTANT (chat)

Natural commands (web chat + WhatsApp):
"What should I teach today?", "Prepare tomorrow's classes", "Prepare my week", "What did I teach 7B last week?", "Continue from my last lesson", "Students struggled with fractions — remedial lesson", "Make this easier for Grade 6", "Create homework from today's lesson", "Test on everything taught this month", **"Cover lesson for tomorrow — I'm absent"** **[NEW]**, **"Translate these slides to Arabic"** **[NEW]**, **"Parent message about this week's topics"** **[NEW]**.

Implementation:
- **Intent router → tools**, not free-form chat. Tools: `get_timetable`, `get_progress`, `get_lessons`, `plan_course`, `generate_lesson`, `generate_worksheet`, `generate_quiz`, `adapt_material`, `summarise_history`, `search_memory`, `schedule_whatsapp`.
- Responses stream, show citations to the teacher's own history ("From your 12 Sept lesson with 7B…"), and offer one-click actions.
- Every long operation becomes a **job** with a progress card.

---

## 12. TEACHER MEMORY **[CHANGED — structured + episodic + feedback]**

Three layers:

1. **Profile memory (structured, editable):** preferences, style, curriculum, classes, assessment preferences, language, explanation depth. Shown on `/teacher-memory` as editable cards. The teacher can see and delete everything.
2. **Episodic memory:** lesson history, per-class progress, generated artefacts, chat summaries. Stored as rows plus embeddings for retrieval.
3. **Learned signals [NEW]:** derived from behaviour. Edits the teacher makes (e.g. they always shorten bullets, which updates `content_style`), regenerate reasons, ratings, and **post-lesson reflections**.

### 12.1 Post-lesson reflection loop **[NEW — key differentiator]**

After each timetabled class (or on WhatsApp at the end of the day), send a one-tap check-in:
`✅ Went well · ⏱ Ran out of time · 😕 Students struggled · ⏭ Skipped`, plus optional voice or text note.

Effects:
- "Ran out of time" moves unfinished content into the next lesson and adjusts pacing for that class.
- "Struggled" offers a remedial starter next lesson and adds a misconception to memory.
- "Skipped" reschedules it.

**Class profiles** (aggregate, no PII): pace, ability mix, EAL %, SEND needs summary, and notes such as "7B loves games". Each section of the same grade has its own profile and progress.

### 12.2 Memory hygiene
Preferences have provenance (stated vs. inferred) and confidence. Inferred preferences are shown for confirmation ("You seem to prefer 4 bullets per slide — keep this?"). Stale episodic memory is summarised periodically.

---

## 13. SLIDE GENERATION

`SlideSpec` (validated with Pydantic, stored per version):

```json
{
  "slide_id": "sl_…", "lesson_id": "ls_…", "slide_number": 4, "version": 2,
  "purpose": "introduce_concept",
  "layout": "concept_with_visual", "template_id": "tpl_…",
  "title": "Why are leaves green?",
  "content": [{ "type": "bullet", "text": "Chlorophyll absorbs red and blue light", "level": 0 }],
  "visual": { "kind": "diagram", "diagram_type": "labelled", "spec": {…}, "asset_id": null, "alt_text": "…" },
  "speaker_notes": "…",
  "teacher_instruction": "Ask: what colour light is reflected?",
  "timing_minutes": 4,
  "outcome_codes": ["KS3-BIO-2.3"],
  "differentiation": { "support": "…", "extension": "…" },
  "sources": [{ "doc_id": "src_…", "page": 42 }],
  "language": "en", "direction": "ltr",
  "qc": { "status": "passed", "issues": [] }
}
```

Renderer rules:
- Use the teacher's template layouts and placeholders. Text stays **editable text**, images are **replaceable picture placeholders**, shapes and diagrams are **native shapes/SmartArt-like groups**, and equations are **OMML**.
- **Never flatten slides to images.**
- Speaker notes go in the PPTX notes pane.
- Arabic slides: RTL paragraph direction, mirrored layouts, Arabic fonts, correct numerals setting.
- Optional **bilingual key-vocabulary slide** (English | Arabic / Hindi). **[NEW]**

---

## 14. NATURAL, TEACHER-STYLE CONTENT

Content should be natural, varied, age-appropriate, concrete (classroom and local examples, e.g. UAE contexts such as desalination or date palms where they genuinely help), concise, accurate and adapted to the teacher's tone.

- Do **not** claim content was written by a human.
- Do **not** build anything intended to evade AI-detection systems.
- Optimise for originality, educational usefulness, factual accuracy and personalisation.
- A "banned phrases / tics" list plus variety checks in QC (repeated openers, repeated headings).

---

## 15. CONTENT QUALITY ENGINE (pre-render)

| Check | Method |
|---|---|
| Schema validity | Pydantic |
| Text fits zone | Font-metric measurement against the zone budget (deterministic) |
| Bullet density / words per slide | Rules from the style profile |
| Reading level vs. grade | Readability formula + LLM judge for edge cases |
| Objective alignment | Each slide maps to ≥ 1 lesson objective |
| Curriculum alignment | Outcome codes present and valid |
| Factuality | Claims extracted and checked against grounding sources, then LLM judge. Unsupported claims are **flagged to the teacher**, not silently kept. |
| Repetition | Across slides and lectures (embeddings) |
| Safety / sensitivity | Moderation + regional rules |

Failures trigger **targeted repair** (shorten, split slide, change layout, regenerate) with a retry cap. If the cap is reached, the slide goes to the teacher with a visible warning.

---

## 16. PPTX QUALITY CONTROL (post-render)

1. Render to PNG (LibreOffice headless).
2. Check bounding boxes from XML: overlaps, off-slide elements, minimum font sizes, alignment to the template grid.
3. Pixel checks: overflow (text beyond the zone), large empty areas, and **contrast ratio** of text over background (WCAG) **[NEW]**.
4. Image checks: resolution vs. displayed size, aspect distortion.
5. Consistency against the template: fonts, colours and layout usage.
6. Optional vision-model review on a sample, or on slides with borderline scores.
7. Regenerate or repair failed slides, then re-render only those.
8. Validate the file opens cleanly (open with python-pptx and LibreOffice). Keep a compatibility test matrix in CI.

Only then deliver the final PPTX.

---

## 17. METADATA & BRANDING

- No AI watermarks, no "Generated by AI" text, no hidden promotional text, no product-identifying metadata by default.
- Legitimate document metadata (author = teacher, title) is set properly.
- A teacher setting controls the metadata of files they own.
- **[NEW] Optional AI-use disclosure:** some schools require disclosure of AI assistance (in line with UAE MoE emphasis on ethical AI use). Provide an **opt-in** setting (off by default for individuals; configurable by a school admin) that adds a discreet note in the notes or on the final slide.
- Never build tools that remove third-party copyright marks, ownership notices or attribution.

---

## 18. VISUAL GENERATION & ASSET MANAGER

Order of preference (cheapest and most reliable first):
1. **Native diagram** (process, cycle, timeline, comparison, labelled diagram, chart from data), editable in PowerPoint.
2. **Teacher's own asset library** (images extracted from their uploads, with the teacher's permission).
3. **Shared licensed library** (curated educational illustrations and icons with clear licences).
4. **Stock providers** via API (licence recorded).
5. **AI image generation** as a last resort. No text baked into images, age-appropriate, consistent with the teacher's style, correct aspect ratio.

`assets`: `asset_id, owner_id, type, prompt, source, license, attribution, dimensions, storage_url, content_hash, tags, embedding, safety_status, created_at`.

Reuse by hash and semantic search. Show attribution where the licence requires it.

---

## 19. TEACHER NOTES

Per slide (optional): explanation, talking points, questions to ask (with Bloom's level), common misconceptions, expected responses, activity instructions, **time allocation**, differentiation tips. Stored in the PPTX notes pane and exported as a printable **teacher guide** (DOCX/PDF).

---

## 20. WORKSHEETS, QUIZZES, ASSESSMENTS

**Question bank [NEW]:** every generated question is stored with type, difficulty, Bloom's level, outcome codes, answer, explanation and usage history. Quizzes and tests are assembled from the bank plus new items, so they avoid repeating questions a class has already seen.

**Worksheets:** practice, MCQ, short and long answer, matching, fill-in-the-blanks, case studies, application, **labelled-diagram**, **data-analysis**. Difficulty: easy / medium / hard / mixed / **tiered (3 versions)**.

**Quizzes:** 5 / 10 / 20 questions; MCQ, true/false, short answer, application, case-based.

**Assessments:** unit tests with **marking schemes and rubrics**, and blueprint tables (outcome × difficulty) **[NEW]**.

**Outputs:** student version, teacher answer key (separate file), DOCX + PDF, and **exports to Google Forms, Microsoft Forms, Kahoot/Quizizz-style CSV, QTI and Moodle GIFT** **[NEW]**.

**Homework:** tied to the lesson, with estimated completion time and an optional differentiated version.

---

## 21. WEEKLY & TERM PLANNER **[CHANGED]**

**"Prepare My Week"** uses the timetable, school calendar (holidays, **Ramadan hours**, exam weeks), curriculum progress, reflections and upcoming outcomes.

It generates a view for each working day (Mon–Fri, respecting short Fridays), and for each class:
topic, objective, lesson plan, PPT, activity, assessment and homework. Status per item: _planned → generated → reviewed → taught → reflected_.

**[NEW] Term / year planner:** a scheme of work across the term with drag-to-reschedule. Holidays shift lessons automatically. Shows the coverage gap against outcomes.

**[NEW] Cover lesson mode:** generates a self-contained lesson and instructions a substitute teacher can run.

Weekly generation is a **batch job**. Materials are generated lazily: the plan comes first, and full PPTX for each day is produced the evening before (configurable) to spread cost.

---

## 22. WHATSAPP ASSISTANT **[CHANGED — cost-aware]**

- **Official WhatsApp Business Platform (Cloud API)** only, directly or through a BSP. **No unofficial automation.**
- **Opt-in** with double confirmation. **STOP** to opt out. Quiet hours. Phone verification.
- **Pre-approved templates** (Utility category): `daily_plan_morning`, `tomorrow_ready`, `week_ready`, `reflection_checkin`, `job_complete`.
- **Cost design:** one consolidated morning message with quick-reply buttons ("Show details", "Open lesson"). A reply opens the free service window, where details are sent as free-form messages. Note: from **1 Oct 2026, utility templates are billable per message even inside the service window**, so keep template sends to a minimum.
- Links are **short-lived signed deep links** to the PWA (magic-link login if the session has expired).
- Inbound commands go through the same intent router as web chat (text and **voice notes** → speech-to-text **[NEW]**).
- Webhook signature verification (X-Hub-Signature-256), idempotency on message IDs, delivery/read status tracking, and a retry policy.
- Store `whatsapp_messages` with direction, template, cost category, status and cost.

Example morning message:

```
Good morning, Ms. Sara 👋
Today (Tue): 3 classes

1) 8A Science · Photosynthesis (L2/5) · 45 min
2) 8B Science · Photosynthesis (L1/5) · 45 min
3) 7C Science · Cells recap · 45 min

✓ Slides  ✓ Notes  ✓ Activity  ✓ Exit quiz  ✓ Homework

[Open today]  [Show details]
```

---

## 23. SUBSCRIPTIONS & PRICING **[CHANGED — credits + school plan]**

Limits are expressed as **credits** so different outputs can be priced fairly (e.g. 1 slide = 1 credit, worksheet = 5, AI image = 3). All values are **admin-configurable**, and none are hard-coded.

| Plan | Suggested price (validate with pilots) | Includes |
|---|---|---|
| **Free** | AED 0 | 1 style profile, monthly credits enough for ~2 short decks, worksheets/quizzes limited, no WhatsApp |
| **Teacher** | AED 79–99 / month | Teacher memory, course & lesson planning, worksheets, quizzes, homework, 2 style profiles, standard credits |
| **Teacher Pro** | AED 149 / month | Higher credits, unlimited classes/subjects, advanced memory & reflections, Arabic/bilingual, exports to Forms/LMS |
| **AI Teaching Assistant** | AED 249 / month | Everything + daily/weekly planning automation, WhatsApp assistant, cover lessons, priority generation |
| **School / Department [NEW]** | Per-seat annual contract | Shared templates & schemes of work, admin dashboard, SSO, coverage reports, invoicing, data-processing agreement |

- **7-day trial** of Assistant features. **Annual billing ≈ 2 months free.** Referral credits. Education or bulk discounts.
- Monthly and annual billing, usage tracking, status (trialing / active / past_due / cancelled), renewal, cancellation (effective at period end), upgrades/downgrades with proration, dunning emails, **5% UAE VAT-compliant tax invoices**, and payment webhooks (signature-verified, idempotent).
- India: INR pricing, Razorpay (UPI Autopay), GST.

---

## 24. SCHOOL / DEPARTMENT WORKSPACE **[NEW]**

- Organisations → departments → teachers. Roles: `school_admin`, `head_of_department`, `teacher`.
- Shared **brand template** (school logo, colours) and department template libraries.
- Shared schemes of work and question banks. Optional HoD review/approval of plans.
- Reports: curriculum coverage per grade, usage, and (aggregate only) time saved.
- Seat management, SSO enforcement, and an org-level AI-disclosure policy.

---

## 25. SECURITY & PRIVACY **[CHANGED]**

- Secure auth (Argon2, SSO, 2FA), RBAC + tenant isolation (Postgres RLS), and object-level authorisation checks on every resource.
- AI and payment keys stay **server-side only**. Secrets live in a secret manager.
- Signed, short-lived file URLs. Private buckets only.
- Rate limiting per user, per IP and per plan (Redis token bucket), plus per-endpoint cost-weighted limits on AI endpoints.
- Input validation (Pydantic/zod), **magic-byte file type validation**, size limits (e.g. 100 MB, 300 pages/slides), zip-bomb and XML-bomb protection (defusedxml, decompression limits), macro stripping, and **ClamAV scanning** before processing. Processing runs in sandboxed workers with no network access.
- Webhook signature verification (Stripe, Razorpay, WhatsApp).
- CSP, CSRF protection, secure cookies and HSTS.
- **Audit log** for admin actions and data access.
- **Privacy [NEW]:** no student PII by default. PII scrubbing before AI calls. Data-region setting. Consent records. Data export and deletion (UAE PDPL, India DPDP). DPAs with AI providers, and model training on customer data disabled. Retention policy for uploads and generations.

---

## 26. FILE PROCESSING PIPELINE

```
Upload (resumable, presigned) → hash dedupe → type/size/magic check → ClamAV
→ immutable storage → [PPT→PPTX convert] → extraction (XML | Docling+PyMuPDF | OCR)
→ layout clustering → style analysis → template build → previews → Ready
```

Progress states shown to the user: _Uploading → Scanning → Analysing → Extracting design → Understanding content → Creating template → Ready_ (or _Needs your review_ / _Failed — reason_).

---

## 27. JOB SYSTEM

Jobs: `document_processing, style_analysis, template_build, source_indexing, course_generation, lesson_generation, slide_generation, ppt_render, ppt_quality_check, image_generation, export, weekly_plan, whatsapp_delivery, reflection_followup, usage_rollup`.

Stored fields: `job_id, user_id, type, parent_job_id, status, progress (0–100), stage, input_hash, result_ref, error_code, error_detail, attempts, cost_usd, created_at, started_at, completed_at`.

Parent/child jobs (a course has lecture jobs, which have slide jobs). Progress is pushed to the client over SSE. Dead-letter queue and an admin retry button.

---

## 28. FRONTEND PAGES

`/` landing (English/Arabic), `/pricing`, `/login`, `/signup`, `/onboarding`, `/dashboard`, `/assistant` (chat) **[NEW]**, `/projects`, `/projects/[id]` (course → lessons → slide editor), `/templates`, `/templates/[id]`, `/sources` (grounding documents) **[NEW]**, `/question-bank` **[NEW]**, `/teacher-memory`, `/classes` (class profiles) **[NEW]**, `/curriculum` (coverage tracker), `/calendar` (timetable + term planner), `/lessons`, `/whatsapp`, `/settings`, `/billing`, `/school` (org admin) **[NEW]**, `/admin`, `/admin/ai-costs` **[NEW]**, `/admin/evals` **[NEW]**.

---

## 29. DASHBOARD UX

```
Good morning, Sara 👋            Tue 7 Oct · Week 7 of Term 1

TODAY'S CLASSES
[8A Science · Photosynthesis L2 · Ready ✓]
[8B Science · Photosynthesis L1 · Ready ✓]
[7C Science · Cells recap · Needs review ⚠]

[★ Create Today's Teaching Plan]  Prepare Tomorrow  Prepare My Week
Create PPT · Worksheet · Quiz · Cover lesson

HOW DID YESTERDAY GO?  8A ✅  7C 😕 → "Remedial starter added to today's 7C lesson"

CURRICULUM PROGRESS (per class)   RECENT PROJECTS   TEMPLATES   MEMORY INSIGHTS
```

Also: empty states that teach the product, keyboard shortcuts, fully usable on mobile, and RTL layout in Arabic.

---

## 30. ONE-CLICK "CREATE TODAY'S TEACHING PLAN"

Timetable → calendar (holiday / Ramadan / short day) → curriculum progress + reflections → AI planning → generate the missing materials (reuse what exists) → display the complete day with per-class status → optional WhatsApp summary.

---

## 31. EDITING

- A slide editor with live preview (rendered from SlideSpec). Inline text edits write back to the SlideSpec.
- Regenerate: entire deck, a lecture, a single slide, title, paragraph, image, diagram or notes.
- Quick actions: _Make simpler · More visual · Add examples · Reduce text · Adapt for Grade N · Add activity · Translate (AR/EN) · Create another version · Differentiate_.
- Every change **preserves the design system** (it stays within layout budgets).
- **Version history** with restore and a compare view **[NEW]**.
- **Learn from edits** (§12, learned signals).

---

## 32. PERFORMANCE & COST

- Lazy loading, streaming, background jobs, compressed WebP previews, CDN, database indexes.
- Parallel slide generation within a lecture (bounded concurrency per user).
- Cache by content hash: `TeacherStyleProfile`, template layouts, curriculum and outcome embeddings, lesson summaries, assets and **LLM responses for identical inputs**.
- Model routing (§4.2). OSS tools for parsing and OCR. Deterministic checks before any LLM judge.
- **Per-project cost budget.** Generation stops and asks before exceeding it.
- Target: **AI cost per 50-slide course ≤ USD 0.50** (tracked on the admin cost dashboard; tune model tiers until it's met).

---

## 33. EVALUATION HARNESS **[NEW]**

- **Golden set:** 30+ real teacher decks (various curricula, PPTX + PDF, English + Arabic) × 20 topics × grades.
- **Automated metrics:** overflow count, QC pass rate, objective coverage, repetition score, reading level fit, factuality flags, render time, cost.
- **LLM-judge rubrics** (pedagogy, clarity, age fit, progression), calibrated against human ratings.
- **Human review:** teacher panel rates design fidelity and usefulness (1–5) each release.
- **CI gate:** prompt or model changes must not regress key metrics beyond thresholds.
- Online: thumbs up/down, regenerate reasons, edit distance, reflection outcomes.

---

## 34. OBSERVABILITY

Structured logs with request/job/user correlation IDs, error tracking, and OpenTelemetry traces across API → worker → AI provider.

Dashboards:
- generation success rate, average and p90 generation time, failed PPT rate, QC repair rate
- **AI cost per project / user / plan / model**, token usage
- API latency and error rate, queue depth, worker saturation
- WhatsApp sent / delivered / read / failed and cost
- business: signups, activation (first deck downloaded), retention, MRR, churn

Alerts on error spikes, queue backlog, cost anomalies and webhook failures.

---

## 35. DATABASE (core tables)

**Identity & org:** `users, organizations, org_memberships, sessions, oauth_accounts, consents, audit_logs`

**Teacher:** `teacher_profiles, teacher_preferences (key, value, source, confidence), teacher_memory (type, content, embedding), class_sections, class_profiles, timetables, timetable_slots, school_calendars, calendar_events (holiday/ramadan/exam/short_day)`

**Curriculum:** `curriculum_frameworks, subjects, grades, learning_outcomes (embedding), schemes_of_work`

**Content:** `uploaded_files, source_documents, source_chunks (embedding), style_profiles, templates, template_layouts, template_versions, projects, courses, lectures, lessons, lesson_outcomes, lesson_reflections, slides, slide_versions, assets, worksheets, quizzes, questions (question_bank), question_usages, homework, rubrics, exports, share_links`

**System:** `generation_jobs, prompt_versions, eval_runs, eval_results, ai_usage (ledger), usage_counters, plan_limits, feature_flags`

**Billing:** `plans, subscriptions, payments, invoices, credit_ledger, webhook_events`

**Messaging:** `whatsapp_contacts (opt_in, quiet_hours), whatsapp_messages, notification_preferences`

Use UUIDv7 primary keys, `created_at/updated_at`, soft delete where needed, foreign keys with appropriate `ON DELETE`, composite indexes on `(owner_id, created_at)`, HNSW indexes on vectors, and partial indexes for active subscriptions and pending jobs.

---

## 36. API SPECIFICATION (outline) **[NEW]**

```
POST   /auth/signup | /auth/login | /auth/logout | /auth/oauth/{provider}
GET    /me                          PATCH /me/preferences
POST   /uploads (presign)           POST /uploads/{id}/complete
GET    /style-profiles              GET/PATCH /style-profiles/{id}
GET    /templates                   GET/PATCH /templates/{id}   GET /templates/{id}/layouts
POST   /sources                     GET /sources
GET    /curricula/{fw}/outcomes?subject=&grade=&q=
POST   /courses (plan)              GET/PATCH /courses/{id}   POST /courses/{id}/approve
POST   /courses/{id}/generate       (→ job)
GET    /lessons/{id}                POST /lessons/{id}/reflection
GET    /slides/{id}                 PATCH /slides/{id}   POST /slides/{id}/regenerate {action}
POST   /worksheets | /quizzes | /homework | /assessments   (→ job)
POST   /exports {format, target}    (→ job)
POST   /assistant/messages          (SSE stream)
POST   /planner/today | /planner/tomorrow | /planner/week
GET    /jobs/{id}                   GET /jobs/{id}/events (SSE)
GET    /billing/plans               POST /billing/checkout   POST /billing/portal
POST   /webhooks/stripe | /webhooks/razorpay | /webhooks/whatsapp
GET    /admin/metrics | /admin/users | /admin/ai-costs | /admin/limits (PATCH)
```

Everything is versioned under `/api/v1`, uses cursor pagination, and returns a consistent error envelope `{code, message, details, request_id}`.

---

## 37. ADMIN PANEL

Metrics: total/active/paid users, MRR, churn, activation, generations, AI usage and cost, storage, WhatsApp usage and cost, failed generations, most-used subjects/grades/curricula, and feature adoption.

User management: view user, subscription, usage, projects, account status (suspend/reactivate), credit adjustments, impersonation (audited, read-only by default).

Config: plan limits, credit costs, model routing, feature flags, WhatsApp templates and prompt versions. Also eval dashboards and the job dead-letter queue.

---

## 38. ACCESSIBILITY & INCLUSION **[NEW]**

- The app meets WCAG 2.2 AA (keyboard navigation, focus states, contrast, screen-reader labels).
- Generated slides include alt text on images, reading order set correctly and contrast checks. An optional **dyslexia-friendly** mode (font, spacing, off-white background).
- Full Arabic UI and RTL. English/Arabic content generation. Hindi planned for India.

---

## 39. DEVELOPMENT REQUIREMENTS

Before writing code:
1. Inspect the repository (currently **empty** — greenfield). Choose a monorepo layout: `apps/web`, `apps/api`, `apps/worker`, `packages/shared-schemas` (JSON Schemas generated from Pydantic → TS types), `infra/`, `docs/`.
2. Write: architecture document (with diagrams), database schema and migrations, API spec (OpenAPI), implementation plan and ADRs for key decisions.

Then build incrementally **in this order** **[NEW — phased]**:

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 — Spike (week 1–2)** | PPTX style extraction + native-master template + SlideSpec → PPTX render + text-fit QC, CLI only | 10 real decks produce 10-slide outputs that pass QC and "look like mine" |
| **1 — North-star MVP** | Auth, upload pipeline, style profile, course planner, lesson plans, 50-slide generation, teacher notes, worksheet/quiz/homework, download, basic editor | North-star acceptance criteria (§0) met on the golden set |
| **2 — Memory & planning** | Timetable, calendar, class profiles, reflections, today/tomorrow/week planner, assistant chat, standards library, coverage | A teacher can run a real week from the app |
| **3 — Monetisation & delivery** | Billing, credits, WhatsApp, exports (DOCX/PDF/Forms/QTI), admin panel, cost dashboard | Paid pilot with UAE teachers |
| **4 — Scale & schools** | School workspace, SSO enforcement, Arabic content generation polish, UAE AI Curriculum pack, India launch (CBSE, Razorpay) | First school contract |

After each major feature: run unit and integration tests, typecheck (tsc, mypy/pyright), lint (eslint, ruff), exercise API tests, migrations up/down, upload tests, PPT generation tests and **visual regression snapshots** of rendered slides.

---

## 40. TESTING

Automated tests for: authentication and SSO, authorisation / tenant isolation, file upload (valid, malicious, oversized, wrong magic bytes, zip bomb), PDF processing, PPT/PPTX processing, style extraction (golden JSON per sample deck), template build, teacher memory, curriculum planning (schema + no repetition), lesson generation, SlideSpec validation, text-fit, PPTX generation, **PPTX opens in LibreOffice without errors**, visual regression, downloads, subscription limits and credits, payment webhooks (signature, idempotency, out-of-order events), WhatsApp webhooks, rate limiting, Arabic/RTL rendering and exports.

AI calls are mocked in unit tests with recorded fixtures. A nightly eval job runs against real models.

Include **sample test files**: varied PPTX (corporate-style, colourful primary-school, minimal, Arabic RTL), text PDFs, scanned PDFs and a legacy `.ppt`.

---

## 41. PRODUCTION DELIVERABLES

`.env.example` · `README.md` · `docs/ARCHITECTURE.md` · `docs/API.md` (+ OpenAPI) · `docs/DEPLOYMENT.md` · `docs/SECURITY.md` · `docs/PRIVACY.md` · `docs/RUNBOOK.md` · database migrations · seed data (demo teacher, curricula/outcomes subset, sample templates) · docker-compose · CI pipeline (lint, typecheck, tests, eval smoke, image build) · infrastructure-as-code for production.

---

## 42. FINAL DELIVERABLE (end-to-end user journey)

A new teacher can:
1. Sign up (email or Google/Microsoft).
2. Complete onboarding in under 5 minutes.
3. Upload an old PPT/PDF.
4. See their style analysed and confirm it.
5. Save the teacher style/template.
6. Add curriculum, classes and timetable.
7. Enter a topic, pick outcomes, lecture count and slides per lecture.
8. Review and approve the course structure.
9. Get lesson plans (with differentiation).
10. Get PPTX in their own design.
11. Download editable PPTX.
12. Generate worksheet, quiz and homework (student + answer key).
13. Have lesson history stored automatically.
14. Tap "how did it go?" after class.
15. Ask "What should I teach next?" and get an answer that uses progress and reflections.
16. Prepare tomorrow's classes in one click.
17. Receive the daily plan on WhatsApp and open it on their phone.

---

## 43. MOST IMPORTANT QUALITY REQUIREMENT

Don't optimise for the number of features. Optimise for the north-star experience in §0. It must feel **clearly better than a generic AI presentation generator** because:

1. **It looks like the teacher made it** (their own master, fonts, colours and layouts).
2. **It knows where the class is** (curriculum progress + reflections).
3. **It fits the teacher's day** (timetable, calendar, WhatsApp).

The project is **not complete** because the UI works. It is complete when real uploaded files produce real, editable, high-quality PPTX through the full flow, and the metrics in §0 are met.

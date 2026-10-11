# Clastio educator platform — implemented phases and local validation

All four phases are implemented in the workspace as of 11 October 2026: educator schemas, queued planners and demos, a staged digital library, and a persistent Teacher Copilot. This document records the resulting contracts and local verification. It does not record a production deployment or a successful paid-model quality trial.

## Existing foundations

Clastio uses SQLAlchemy/Alembic, not Prisma. `TeacherProfile`, `Course`, `Lesson`, `Slide`, `Document`, `UploadedFile`, `SourceChunk`, conversations and teacher memory already exist. The existing generation `LessonPlan` is a Pydantic schema persisted in `Lesson.plan`; it remains compatible with PPT generation. The new ORM `LessonPlan` supplies independently usable planners, instead of replacing that JSON or requiring a presentation for every plan.

Books support private originals, an explicitly published catalogue, one-time indexing, saved chapter ranges and curriculum filters. The educator workspace reuses these sources, the existing job queues, credit accounting, document conversion, and presentation preview/editor. Copilot conversations use the existing conversation tables with a dedicated `copilot` channel.

## Educational context and evidence

This is an inspection-aligned planning structure designed for Clastio, not an official regulator-mandated JSON template or automatic compliance certification. The teacher's curriculum, school conventions, class needs and evidence determine the final plan. Teacher review and regulator alignment are separate states.

Official references checked:

- KHDA: [UAE School Inspection Framework](https://web.khda.gov.ae/en/Resources/Publications/School-Inspection/UAE-School-Inspection-Framework-2015-16), including teaching, assessment and learning quality.
- KHDA: [Dubai inclusive education policy framework](https://web.khda.gov.ae/en/Resources/Publications/School-Inspection/Dubai-inclusive-education-policy-framework).
- ADEK: [Teaching and Learning policies](https://www.adek.gov.ae/Education-System/Education-Policies/School-Policies-Teaching-and-Learning), including assessment, curriculum, inclusion, cultural consideration and quality assurance. The page lists school curriculum/assessment policy compliance from AY 2025/26; references must preserve the actual document/version rather than inventing a 2026 framework edition.

School inspection fields must not be advertised as university compliance. University resources use the university stage; a university planner cannot select a school framework (`khda`, `adek`, `moe`) in this contract.

## Phase 1 — exact database changes

Migration: `i209educator01`, parent `h208feedback01`. Exact executable PostgreSQL DDL, defaults, indexes, checks and Alembic version update: [phase-1-postgresql.sql](educator-schemas/phase-1-postgresql.sql). Apply this migration rather than manually copying partial SQL and separately changing the migration version.

### Extend `teacher_profiles`

| Column | PostgreSQL type | Default / requirement |
| --- | --- | --- |
| `regulatory_authority` | `varchar(20) NOT NULL` | `not_specified`; checked values `khda`, `adek`, `moe`, `other`, `not_specified` |
| `education_stages` | `varchar[] NOT NULL` | Empty array; values restricted to the four stages |
| `planning_preferences` | `jsonb NOT NULL` | `{}`; aggregate SEN/ELL scaffolds, preferred assessment tools and school format |

The existing `/me/profile` GET/PUT contract now supports these fields. Notes are aggregate class support, not individual student records. Existing profiles receive safe defaults and retain their previous curriculum/subjects/grades.

### Add `lesson_plans`

Identity/ownership: UUID `id`, `owner_id → users`, optional `lesson_id → lessons` and `class_section_id → class_sections`, creation/update timestamps.

Searchable metadata: `title varchar(300)`, `topic varchar(300)`, `subject varchar(80)`, `grade varchar(30)`, `curriculum varchar(40)`, `language varchar(10)`, `education_stage varchar(20)`, `framework varchar(20)`, positive `schema_version`, `version`, `duration_minutes`, and checked `status`.

Required structured JSONB fields:

- `learning_objectives`: stable ID, measurable description, observable action, success measure, Bloom level.
- `success_criteria`: ID, objective IDs, criterion and observable evidence.
- `cross_curricular_links`: subject, actual activity and evidence of learning.
- `uae_context`: `national_identity`, `moral_education`, `arabic_culture`; each has relevance, a connection or reason, and a classroom application.
- `differentiation`: nonempty `sen` and `ell` arrays with learning barrier, scaffold and assessment accommodation; core/extension instructions are in the content contract.
- `formative_assessment`: ID, objective IDs, tool, task/question, expected response, evidence to record and subsequent teaching response.
- `lesson_sequence`: duration, objectives, teacher/student actions and assessment IDs.

Additional JSONB: `prerequisites`, `homework` (JSON string), `resources`, `source_references`, `review_checks`. Optional `pdf_key`, `error`, `reviewed_at` support exports and human review.

Queued/draft rows can have empty generated fields. Ready/reviewed rows must have nonempty planning arrays, all three nonempty UAE context objects, and nonempty SEN/ELL arrays. The Pydantic content contract additionally enforces unique identifiers, objective coverage, per-phase assessment alignment, and exact lesson timing.

### Add `demo_classes`

UUID identity/owner/timestamps; optional links to `lesson_plans` and the existing `lessons` table; title/topic/subject/grade/curriculum/language/framework; version/status. `duration_minutes` defaults to 15 and has a database check requiring exactly 15.

JSONB `hook`, `teacher_script`, `slide_payload`, `source_references`, `review_checks`; optional `pptx_key`, `pdf_key`, `error`. Ready/reviewed demos require a nonempty hook, teacher script and slides array. The strict content contract requires at least three continuous script steps covering 0–900 seconds, references every slide, preserves the approved title/objectives/success criteria, and derives slide durations from the script's mapped steps.

### Add `digital_resources`

UUID identity/owner/timestamps; optional `uploaded_file_id → uploaded_files` and `document_id → documents`; title/topic/subject/stage/nullable grade/curriculum/language; positive version/schema version; kind/origin/status; cache key.

JSONB `content`, `chapters`, `source_references`, `license_metadata`; optional `pdf_key`, `error`.

- Kinds: `book`, `guide`, `subject_primer`, `study_guide`.
- Origins: `uploaded`, `official`, `generated`.
- Generated content may only be a `subject_primer` or `study_guide`. It cannot masquerade as an official textbook.
- Ready/reviewed generated resources need content and chapters.
- `UNIQUE(owner_id, cache_key)` prevents duplicate cached resources within an account.
- Compound lookup index: owner, subject, education stage, curriculum, language.

All three new entities require an owner. Deleting an owner cascades; deleting an optionally linked artifact sets that link to NULL. Services check ownership/access to linked classes, plans, templates and selected sources before queuing work, and check the saved links again when a worker uses them. An ordinary foreign key alone does not prove ownership.

### Shared values and content contracts

Stages: `early_years`, `primary`, `secondary`, `university`.

States: `draft`, `queued`, `generating`, `ready`, `reviewed`, `failed`, `archived`.

Frameworks: `khda`, `adek`, `moe`, `other`, `not_specified`.

Strict schemas: [lesson-plan.schema.json](educator-schemas/lesson-plan.schema.json), [demo-class.schema.json](educator-schemas/demo-class.schema.json), [generated-resource.schema.json](educator-schemas/generated-resource.schema.json). Runtime validators live in `apps/api/app/generation/educator_specs.py`. The existing AI service turns these into provider-compatible strict JSON schemas; JSON schema alone cannot validate cross-reference/timing invariants, so Pydantic validators remain necessary.

Source references require a safe HTTPS URL or file UUID syntactically. Workers validate exact reference identifiers, titles and page/section values against supplied evidence. Framework references carry the actual title, URL/file, section and relevance. Unsupported citations cannot become verified evidence merely because they pass the JSON schema. AI review status is `teacher_review_required`; the model cannot grant regulator approval.

## Phase 2 — lesson planner and demo generation

The planner is independent of presentation generation. A request supplies its topic, subject, grade/year, curriculum, language, stage, framework, duration and optional indexed sources. Durations are bounded to 5–180 minutes. The queued `educator_plan` worker generates and validates `UAEPlanContent`, records evidence gaps, and produces a structured UI preview plus editable DOCX and printable PDF.

The planner prompt uses the requested UAE master teacher/school inspector perspective and backward design: measurable objectives, success evidence, then aligned activities and assessment. It requires concrete SEN/ELL scaffolds, cross-curricular applications and relevant UAE connections. The selected framework comes from the teacher's input/profile; a UAE location alone does not select KHDA or ADEK. Books, memories and excerpts are treated as reference data rather than instructions. See `apps/api/app/generation/educator_prompts.py` and `apps/api/app/services/educator.py`.

Manual edits validate the saved plan and supplied-evidence snapshot without another AI call. Version checks reject conflicting edits. Editing or recording teacher review increments the version and invalidates older export links; a new export uses the latest plan. Recording review means a teacher reviewed the draft, not that a regulator approved it.

Demo generation accepts either a topic or a matching ready 15-minute plan. A reused plan must match topic, subject, grade, curriculum, language, stage and framework. The worker preserves the plan's objectives and success criteria, writes an interactive hook and continuous 0–900-second teacher script, then formats 3–8 slide briefs in batches of three. Every slide maps to the script, and slide timings derive from those mappings rather than an independent estimate.

The demo worker saves an ordinary Project, Course, Lesson and Slides record through the existing presentation pipeline. This gives the demo its existing presentation preview, manual editor, PPTX download, rendered slide PDF and preview images. The script has separate PDF/DOCX exports. After manual slide edits, the download links use the current linked presentation; the original demo script is labelled as its original draft. Text overflow checks, rendering and visual review run before publication, and any unavailable renderer is reported explicitly. Uploaded templates use the existing template-preservation path and relevant image queries for actual picture slots.

All API paths below are relative to `/api/v1` and require the current user's session:

| Resource | Implemented operations |
| --- | --- |
| `/lesson-plans` | `POST` queue a plan; `GET` list own plans, optionally by subject/stage |
| `/lesson-plans/{id}` | `GET` detail; `PUT` versioned content edit; `DELETE` own inactive record |
| `/lesson-plans/{id}/review` | `POST` versioned teacher review and notes |
| `/lesson-plans/{id}/export` | `POST` queue current PDF/DOCX exports |
| `/demo-classes` | `POST` queue a 15-minute demo; `GET` list own demos |
| `/demo-classes/{id}` | `GET` script, linked lesson and current downloads; `DELETE` own inactive record |
| `/demo-classes/{id}/export` | `POST` queue script PDF/DOCX exports |

Create/export responses include the job ID for the existing job-status UI. Detail responses carry status, errors, evidence/review metadata and available downloads. Active records cannot be deleted while their jobs run. Artifact cleanup is restricted to the entity's owner/id storage namespace.

## Phase 3 — reusable digital library

`/digital-library` groups material by Early Years, Primary, Secondary and University. It shows saved books/notes directly, with links to their saved original files, alongside AI-generated primers and study guides. `/books` remains the place to upload/import authorised PDFs, edit metadata, record the stage, index the book once and select chapter ranges. Books with no stage/grade metadata appear in All stages until categorised. The API supports subject, stage, curriculum, grade and language filters for saved digital resources.

If a matching primer/guide is missing, the `educator_resource` worker creates an outline and writes each chapter separately. Requests are bounded to 1–6 chapters. The content contract requires complete definitions/explanations, examples, UAE case studies, summaries and paired practice/answers. The saved result includes structured content, chapter data, provenance and PDF/DOCX exports. Generated material is visibly labelled as an AI teaching draft and cannot be stored as an official textbook.

The owner-scoped cache fingerprint includes normalised classroom scope/topic, instructions, selected file IDs and content hashes, page ranges, teacher planning preferences, and prompt/schema versions. Identical ready requests reuse the saved resource without another AI call. Identical queued requests reuse their job; an owner lock plus the database uniqueness constraint protects concurrent submissions. Failed resources remain distinguishable and can be retried.

| API path | Implemented operations |
| --- | --- |
| `/digital-resources` | `GET` list own resources with optional subject/stage/curriculum/grade/language filters |
| `/digital-resources/generate` | `POST` reuse a matching saved resource or queue a new primer/guide |
| `/digital-resources/{id}` | `GET` detail and downloads; `DELETE` own inactive resource |
| `/digital-resources/{id}/export` | `POST` queue current PDF/DOCX exports |
| `/digital-resources/{id}/regenerate` | `POST` retry a failed saved request |

The app reuses books that have actually been uploaded/imported or made available in the authorised catalogue. It does not bundle every official UAE textbook or assume that a missing commercial book is free to copy. Generated guides supplement the available book collection; they do not replace it or imply MoE approval.

## Phase 4 — dashboard and Teacher Copilot

The responsive app shell/dashboard now links My Presentations (`/projects`), Lesson Planners (`/lesson-planners`), Demo Class Generator (`/demo-classes`), Digital Library (`/digital-library`) and AI Copilot (`/copilot`). Planner, demo and library pages include classroom/source forms, queued-job states, saved-item lists, structured previews and download controls. The existing teaching chat at `/assistant` remains accessible from the Copilot page.

Teacher settings store framework, education stages and aggregate SEN/ELL scaffolds/assessment preferences. Profile defaults initialise forms, while user edits and explicit grade/subject/topic in the current Copilot request take precedence. For example, a Grade 6 Science ecosystems request is not silently forced to a saved Grade 7 preference. University tasks/resources use their own stage; university planners and Copilot tasks offer Other/Not specified rather than school inspection frameworks.

The Copilot has persistent chat-like conversations and saved printable classroom tasks. A user request and queued response are stored before generation; the final response includes an action card opening the saved task. Reopening a conversation or task restores its saved classroom scope and source selections; teacher edits made while it loads take precedence. Follow-ups include bounded recent messages and the previous structured task so requests such as “make it easier” retain useful context. Conversations and task resources remain private to their owner, and concurrent replies in the same conversation are rejected until the pending job finishes.

Each [`CopilotTask`](educator-schemas/copilot-task.schema.json) contains student-facing reading, vocabulary, questions, concrete SEN support, ELL sentence frames, core/extension work, an assessment tool and expected answers. The UI renders the task and exports it as DOCX/PDF with a separate teacher answer-key section. Copilot tasks reuse `DigitalResource` records with `resource_type: copilot_task`, rather than an additional table. Source citations are checked against the supplied material; unsupported references are removed with a visible evidence gap. Missing source evidence requires factual checking rather than fabricated citations.

| API path | Implemented operations |
| --- | --- |
| `/copilot/resources` | `POST` create/reuse a printable task and record its conversation turn; `GET` list own saved tasks |
| `/copilot/conversations` | `GET` list own Copilot conversations |
| `/copilot/conversations/{id}` | `GET` own conversation messages and resource action cards |

Copilot task reuse is independent of conversation ID, so the same first request in a new conversation can reuse an existing task. Follow-up context, classroom scope, source hashes/page ranges, preferences and prompt/schema versions still participate in the cache key.

## Model routing, sources and cost controls

The new workflows reuse the existing AI service; no browser API key or separate provider integration is introduced. With OpenRouter configured, `planning` routes through `MODEL_PLANNING` (or the saved admin override). `content` handles demo scripts, slide batches, guide outlines/chapters and Copilot tasks. The uploaded-template slide route may use `MODEL_TEMPLATE_CONTENT`. Existing rendered-slide review uses the configured review/vision path. See [OpenRouter configuration](OPENROUTER.md) for routing syntax and the configured preset; task tiers remain configurable rather than hard-coded to retired example models.

Credits are checked/reserved when work is queued, and paid AI calls use the existing price-card and spending-limit reservations. A demo reserves for up to eight slides and settles its credit charge against the resulting slide count. Guide credit reservations scale with chapter count. The new job types participate in active reservations, so parallel educator jobs count towards the user's allowance. Provider cost accounting remains separate from teacher credit units.

Source selection is limited to five indexed files, with an optional ordered chapter range of at most 80 PDF pages per file. Workers bound excerpt payloads and supply exact identifiers/pages to the model. Saved originals and indexed chunks can be reused without searching for or uploading the same book for every lesson. This bounds retrieval context; it is not a promise that a whole textbook has been exhaustively used in one generation.

The workflow controls cost through saved-resource reuse, AI response caching, one stronger planning pass, smaller content batches, and native/stock visuals. Demo generation does not enable paid AI images. It does not add an automatic Perplexity search to every plan, chapter or Copilot request. Plans can be useful with existing source material; current claims still need appropriate source checking and teacher review.

## Validation and local startup

Schema validation covered PostgreSQL migration upgrade/downgrade on a temporary database, preservation of existing teacher profiles, ready-content guards, owner-cache uniqueness and generated-resource provenance. Focused API unit tests cover timing/objective invariants, source access/citations, budget reservations, job failure/retry, exports, ownership, conversation persistence and template mapping. The broader unit run passed 568 tests, excluding two known unrelated failures concerning stock fallback wording and expired-session push; this is not a claim that every existing test passes. Relevant tests are in `apps/api/unit_tests/test_educator_*.py` and `test_copilot_resources.py`.

The responsive browser fixture test is `apps/web/e2e/educator-workspace.mjs`. It passed against the built local frontend on port 3005, checking planner/library/demo/Copilot flows, framework/stage defaults, mobile overflow and explicit request context. TypeScript validation passed. Fixtures validate browser behavior without paid AI calls.

An isolated Docker QA stack on web port 3004/API port 8004 completed real queue, worker, PostgreSQL and document/rendering flows with offline AI: plan generation and PDF/DOCX exports; manual edit/review and fresh export; exact 900-second demo, PPTX, rendered slide previews and an editable linked lesson; saved chapter guide/cache reuse; Copilot PDF, saved conversation and contextual follow-up; and cross-owner access returning 404. Offline samples are labelled illustrative and require replacement/checking before teaching. This verifies integration and export behavior, not the factual/pedagogical quality of live paid-model output. No paid OpenRouter generation or real student data was used in this QA run.

To reproduce that QA on a dedicated Compose project, with its own database/storage and no application `.env`:

```bash
docker compose -p clastio-educator-qa -f docker-compose.yml -f deploy/docker-compose.educator-qa.yml up -d --build --wait
python3 apps/api/e2e/educator_platform.py
docker compose -p clastio-educator-qa -f docker-compose.yml -f deploy/docker-compose.educator-qa.yml down --volumes
```

The script refuses live AI and production mode before creating fixtures. The final command removes only the dedicated QA project's disposable containers and volumes. Run the responsive fixture test against a running frontend with `BASE_URL=http://localhost:3005 node apps/web/e2e/educator-workspace.mjs`.

The full local stack includes frontend, API, worker, PostgreSQL, Redis and Gotenberg. On this machine Chatwoot already uses port 3000, so use port 3005 for Clastio:

```bash
cd /Users/macbookpro/development/ai-teacher-assistant
WEB_PORT=127.0.0.1:3005 PUBLIC_WEB_URL=http://localhost:3005 docker compose up -d --build --wait api worker web
```

Open `http://localhost:3005`. The API is available at `http://localhost:8000/api/v1`; the frontend proxies `/api/v1` to it. Local health checks confirmed all four new pages return HTTP 200 and readiness checks pass for the database, Redis and migration `i209educator01`. Keeping `PUBLIC_WEB_URL` consistent with the selected port ensures local origins/callbacks use the correct address. Use the same environment overrides for subsequent compose starts/rebuilds on this machine.

The Compose migrate service applies `i209educator01` before API/worker startup. For an already configured native backend environment, apply migrations with:

```bash
cd apps/api
.venv/bin/alembic upgrade head
```

Live content requires the server-side OpenRouter key, a supporting model route, approved rate cards and enabled spending controls. The current local `.env` has an empty `OPENROUTER_API_KEY` with OpenRouter-only routing enabled, so live AI is unavailable until the key is added. Add your key to the root `.env`; never put it in a `NEXT_PUBLIC_*` variable or frontend code:

```dotenv
OPENROUTER_API_KEY=<your-openrouter-api-key>
```

Then reload the environment in the running services:

```bash
WEB_PORT=127.0.0.1:3005 PUBLIC_WEB_URL=http://localhost:3005 docker compose up -d --force-recreate api worker web
```

Approve current model price cards and enable the desired live daily/monthly/job budgets in the admin controls before paid generation. `AI_OFFLINE_MODE=true` deliberately selects illustrative QA content. Gotenberg/LibreOffice must be available for PDF and rendered slide previews; the app reports conversion warnings rather than claiming a PDF exists when conversion fails.

Before classroom use, test a representative live plan/demo against a saved authorised chapter, check factual coverage and SEN/ELL suitability, inspect the PPT preview, make an editor change, and confirm the downloaded PPTX reflects the latest presentation. Schema/render checks and a teacher's recorded review do not establish regulator certification. No production deployment is represented by the local completion described here.

Rollback removes the new tables/profile fields and their new data. It was exercised only on a temporary verification database. Legacy lesson-plan JSON and other tables remain in place.

# Clastio educator platform — implementation plan and Phase 1

Verified against the workspace on 11 October 2026. Phase 1 code is implemented and tested. Phases 2–4 below are the execution roadmap; their new endpoints/pages are not implemented by this first schema delivery.

## Existing foundations

Clastio uses SQLAlchemy/Alembic, not Prisma. `TeacherProfile`, `Course`, `Lesson`, `Slide`, `Document`, `UploadedFile`, `SourceChunk`, conversations and teacher memory already exist. The existing generation `LessonPlan` is a Pydantic schema persisted in `Lesson.plan`; it remains compatible with PPT generation. The new ORM `LessonPlan` supplies independently usable planners, instead of replacing that JSON or requiring a presentation for every plan.

Books already support private originals, an explicitly published catalogue, one-time indexing, saved chapter ranges and curriculum filters. The assistant already persists conversations and queues printable documents. The expansion should reuse those paths.

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

All three new entities require an owner. Deleting an owner cascades; deleting an optionally linked artifact sets that link to NULL. Service endpoints in Phase 2 must check that every linked class, lesson, document or source is owned/accessible; an ordinary foreign key alone does not prove that.

### Shared values and content contracts

Stages: `early_years`, `primary`, `secondary`, `university`.

States: `draft`, `queued`, `generating`, `ready`, `reviewed`, `failed`, `archived`.

Frameworks: `khda`, `adek`, `moe`, `other`, `not_specified`.

Strict schemas: [lesson-plan.schema.json](educator-schemas/lesson-plan.schema.json), [demo-class.schema.json](educator-schemas/demo-class.schema.json), [generated-resource.schema.json](educator-schemas/generated-resource.schema.json). Runtime validators live in `apps/api/app/generation/educator_specs.py`. The existing AI service turns these into provider-compatible strict JSON schemas; JSON schema alone cannot validate cross-reference/timing invariants, so Pydantic validators remain necessary.

Source references require a safe HTTPS URL or file UUID syntactically. Phase 2 must resolve file ownership and verify URLs against supplied evidence before calling them verified citations. Framework references carry the actual title, URL/file, section and relevance. AI review status is `teacher_review_required`; the model cannot grant regulator approval.

## Phase 2 — planner and demo workers

1. Add owner-scoped async `/lesson-plans` create/list/detail/update/review/export routes and queued jobs. Reserve existing credits and AI budget ceilings before paid calls; keep bounded retries and recoverable job errors.
2. Use a source-backed planner prompt: act as a UAE master teacher and school inspector preparing an inspection-aligned draft; work backwards from objectives to evidence to learning activities; require concrete SEN/ELL accommodations and culturally relevant activities; treat uploaded material as reference data, never instructions. Do not invent regulator requirements, textbook facts or approval.
3. Validate `UAEPlanContent`, save ready content atomically, and use a standalone DOCX/PDF adapter. The existing document handler requires `lesson.plan`, so simply calling it with a topic-only planner is insufficient.
4. Add `/demo-classes` create/list/detail/export jobs. Generate an approved 15-minute plan/script, then format slides with the content tier in small batches. Derive legacy PPT objectives, criteria, SEND/EAL guidance and timing from the approved plan rather than independently regenerating them.
5. Link demo slides to the existing Course/Lesson renderer/editor where practical; reuse template preservation, images, overflow checks and rendered-page review. Save script and slide payload together.
6. Store actual framework/source references, evidence gaps, prompt/schema version and teacher-review checks. Resolve jurisdiction from an explicit profile/input choice, not from UAE location alone.

## Phase 3 — staged digital library

1. Extend the existing book-library UI with the four stages and typed digital resources; preserve curriculum, grade and language filtering.
2. `/digital-resources` lists saved resources. `/digital-resources/generate` first checks a fingerprint containing normalized stage, grade, subject, curriculum, language, topic, source hashes and prompt/schema version.
3. When no matching resource exists, generate a primer/guide outline, then chapters in bounded batches. Validate explanations, definitions, examples, UAE case studies, summaries and answer-bearing practice.
4. Save the result and PDF once. Return the ready cached resource without repeating AI calls. Keep failed/in-progress jobs distinct from reusable ready content.
5. Label AI-generated guides visibly. Reuse authorised official PDFs through the existing private/published-book path; do not substitute a generated primer for a school textbook or label it MoE-approved.
6. Test education-stage filters, owner isolation, concurrent duplicate requests, bounded generation and cached no-call retrieval.

## Phase 4 — dashboard and teacher copilot

1. Reuse the responsive app shell/dashboard; add My Presentations, Lesson Planners, Demo Class Generator, Digital Library and AI Copilot navigation.
2. Add planner/demo forms and structured previews, timing/script panels, review controls, and printable exports.
3. Reuse persistent assistant conversations; add typed planner, demo, guide and differentiated-task action cards. A differentiated reading task should become a saved printable resource, not only unsaved chat Markdown.
4. For the Grade 6 ecosystems/UAE mangroves example, return a source-backed task with vocabulary, accessible SEN supports, ELL sentence frames, an extension, questions, expected answers and an assessment tool, with PDF/UI preview.
5. Validate small-screen layouts and real end-to-end generation with authorised source material. Automated schema checks do not establish regulator approval or pedagogical quality.

## Validation and deployment order

Phase 1 validation: 464 API unit tests passed; two previously known unrelated tests (stock fallback wording and expired-session push) were excluded. Ruff passed. Validation includes PostgreSQL upgrade/downgrade on an isolated database, preservation of a pre-existing teacher profile, ready-content checks, generated-resource provenance, owner-cache uniqueness, strict Pydantic contracts, and the existing API unit suite. No paid calls or real student records are used.

Apply migration `i209educator01` before running API code that queries the new profile columns. With the existing Docker local setup, the migrate service precedes API/worker startup:

```bash
docker compose up -d --build --wait api worker
```

Native environment:

```bash
cd apps/api
.venv/bin/alembic upgrade head
```

Rollback removes the new tables/fields and consequently their new data; it was exercised only on a temporary test database. Existing legacy plans and other tables are not replaced. The temporary verification database was removed after testing. Production is not altered by this Phase 1 schema delivery.

# Architecture

How PPT Genie is put together, and why. For the product itself see [PRODUCT_SPEC.md](PRODUCT_SPEC.md).

## Overview

```
Browser ──► Next.js web (apps/web) ──/api/*──► FastAPI API (apps/api) ──► PostgreSQL 16 + pgvector
                                                    │   ▲                      ▲
                                        enqueue job │   │ SSE / polling        │ SKIP LOCKED
                                                    ▼   │                      │
                                              generation_jobs table ◄──── Worker(s): AI calls, LibreOffice,
                                                                           rendering, QC, documents, WhatsApp
                                        File storage (local disk or S3) ◄──┘
External: Anthropic / OpenAI / Gemini · Openverse · Stripe · WhatsApp Cloud API · Google / Microsoft OAuth · SMTP
```

- **The browser only talks to the web app.** Next.js proxies `/api/*` to FastAPI, so session cookies stay first-party and no API key or backend URL reaches the client.
- **Requests never do slow work.** Uploading, analysing, planning, generating, rendering and document creation are jobs. The API writes a row to `generation_jobs` and returns its id. Workers claim jobs with `SELECT … FOR UPDATE SKIP LOCKED`, so there is no separate broker. Clients follow progress by polling or over SSE (`/api/v1/jobs/{id}/events`).
- **One Postgres holds everything:** relational data, the job queue, embeddings (pgvector HNSW indexes, cosine distance) and settings. Redis is optional and only shares rate-limit buckets across API instances.

## Backend layout (`apps/api/app`)

| Package | Responsibility |
|---|---|
| `api/routes` | HTTP layer: auth, teacher (profile, classes, timetable, calendar, planner), content (uploads, templates, courses, lessons, slides, documents, jobs, downloads), assistant and memory, platform (billing, webhooks, WhatsApp, admin, health) |
| `services` | Business logic: courses, planner, assistant, memory, documents, assets, styles, uploads, sources, usage and credits, billing, WhatsApp, admin, runtime settings |
| `generation` | Lesson pipeline: specs (Pydantic schemas for plans and slides), prompts, layout budgets, QC and repair, the offline content generator |
| `engine` | Deterministic document engine: style analysis (PPTX XML, PDF), template building, PPTX rendering and text fitting, visual QC, DOCX/PDF/CSV/GIFT exports |
| `ai` | Provider-neutral AI service: tier routing, fallbacks, structured output, usage and cost ledger |
| `jobs` | Job queue (enqueue, claim, retry with backoff, dedupe) and handlers |
| `models` | SQLAlchemy 2 models; Alembic migrations in `alembic/` |
| `core` | Config, DB, security (Argon2, JWT, signed URLs), storage, rate limiting, logging, errors |

Job types and queues: `style_analysis` and `source_indexing` (docs), `course_plan`, `lesson_generation`, `slide_regeneration` and `document_generation` (ai), `lesson_render` (render). A worker can be limited to some queues with `--queues ai,render`.

## From an old deck to a template

1. **Upload.** The file is validated by extension, magic bytes, size and page count, and optionally scanned by ClamAV. It is stored under a content hash; the original is never modified.
2. **Analyse** (`engine/style`). For PPTX: theme colours and fonts, slide masters and layouts, placeholder geometry, and *decorations*. A decoration is a shape, picture or text that recurs on at least half the slides at the same place (compared on a 2% grid with image hashes), such as header bands, logos, footers and slide numbers. For PDF: PyMuPDF extracts text spans, vector drawings and images, and recurring elements are found at span level. Content zones (title, body, footer bands) come from where text actually sits.
3. **Build a template** (`engine/template`):
   - **Native** (PPTX): the teacher's own file is reduced to donor slides and keeps its masters, layouts and theme. Decorations are copied with relationship remapping and renumbered shape ids.
   - **Reconstructed** (PDF): a new deck recreates the colours, fonts, bands and decorations. Logos are cropped from a rendered page so transparency survives.
   - **Built-in** styles for teachers who don't upload anything.
4. **Preview.** A sample lesson is rendered in the template so the teacher can see and accept it.

## Generating a lesson

```
course_plan job      ─► CoursePlan: outcomes, big idea, prerequisites, per-lecture objectives and key concepts,
                        progression check (duplicate concepts, embedding similarity between lectures)
lesson_generation    ─► context      teacher profile, preferences, memory, class, reflections and carry-over,
job (per lesson)                     curriculum outcomes, retrieved source chunks
                     ─► deck         LessonDeck (lesson plan + SlideSpecs) as one structured-output call
                     ─► normalise    enforce layouts, counts, required slides (objectives, quiz, exit ticket …)
                     ─► content QC   budgets per layout from the template's real geometry and fonts, reading level,
                                     repair of over-long slides by a focused rewrite
                     ─► images       Openverse (CC, credited) → AI image (credited, labelled) → placeholder
                     ─► render       DeckRenderer on the template with font-metric text fitting
                     ─► visual QC    LibreOffice → PDF → PyMuPDF: off-slide, overflow, overlaps, contrast;
                                     repair and re-render (bounded rounds)
                     ─► save         PPTX, slide versions, previews; credits charged; lesson summary to memory
```

Slide specs use 19 layouts (cover, objectives, concept, process, cycle, timeline, comparison, table, key vocabulary, quiz, worked example, activity, exit ticket, homework and others). Diagrams are drawn as native shapes, so everything stays editable in PowerPoint. Arabic decks are rendered right-to-left.

**Editing** regenerates a single slide (`slide_regeneration`) from a quick action or free text, then re-renders the deck. Every change creates a slide version that can be restored.

## AI layer (`app/ai`)

- **Tiers:** `planning`, `content`, `fast`, `vision`, `qc`, `embedding`, `image`. Each tier maps to `provider:model` through env vars (`MODEL_*`) or a runtime override in `app_settings` (Admin → AI costs). `vision` is configured but not used yet.
- **Providers:** Anthropic (Messages API, streaming, JSON-schema structured output, prompt caching of the system prompt, server-side fallbacks on the planning model), OpenAI (Responses/Embeddings/Images), Gemini (`google-genai`), and an **offline** provider that returns deterministic content from registered generators when no key is present.
- **Fallbacks:** if the routed provider has no key or fails with a retryable error, the call goes to the tier's fallback on another provider.
- **Refusals** raise a typed error, which the job reports to the teacher without retrying.
- **Ledger:** every call writes `ai_usage` (provider, model, tier, task, tokens, cost in USD from an overridable price table, latency, job, user).

## Planning, memory and the assistant

- **Planner** (`services/planner.py`): days are built from the timetable and the school calendar (holidays skip, Ramadan and short days shorten lessons). "Prepare" assigns the next pending lesson per class and queues generation. Reflections ("ran out of time", "struggled") carry content over or add a remedial starter; repeated signals adjust a class's pace.
- **Memory** (`services/memory.py`): explicit preferences (teacher-set or learned from uploads, always visible and editable) plus free-text items (lesson summaries, misconceptions, notes) with embeddings for retrieval.
- **Assistant** (`services/assistant.py`): a rule-based intent router handles common requests without an AI call. Anything else goes to the `fast` tier with a JSON schema. Intents map to the same services the UI uses. Replies stream over SSE. WhatsApp messages go through the same assistant.

## Billing and limits

Plans live in the `plans` table: price, monthly credits, max lessons per course, WhatsApp messages, AI images and feature flags. Nothing is hard-coded. Credit costs per action are runtime settings. Stripe Checkout and the Billing Portal handle payment; webhooks are signature-verified and idempotent (`webhook_events`). Admins can assign plans by hand.

## WhatsApp

Official WhatsApp Cloud API only. A number is linked with a one-time `LINK <code>` message, with opt-in recorded. STOP and START are honoured, and quiet hours are respected. Business-initiated messages use approved templates and are metered per plan. Inbound webhooks are verified with the app secret (`X-Hub-Signature-256`). The worker's scheduler sends the morning plan and the after-class check-in, guarded by a Postgres advisory lock so several workers never double-send. Without credentials, messages are simulated and shown in the app.

## Security

Argon2id password hashes. HttpOnly, SameSite=Lax session cookies, or Bearer tokens for API clients. Role checks for admin routes and ownership checks on every resource. Downloads use short-lived HMAC-signed URLs. Rate limits apply per IP (generous, because schools share IPs) and per account for login. Webhook signatures are verified. Security headers are set on both apps. Audit log for sign-ins and sensitive changes. Teachers can export their data and delete their account from Settings.

## Frontend (`apps/web`)

Next.js App Router with React 19, Tailwind CSS v4 design tokens (light and dark), SWR for data, and English/Arabic UI with RTL layout. Pages: marketing and pricing, sign-up and sign-in, onboarding, Today dashboard, assistant, projects and course builder, lesson editor, lessons and documents library, calendar and timetable, classes and curriculum, design templates, teacher memory, WhatsApp, billing, settings, and admin (metrics and AI costs, with hand-written accessible SVG charts).

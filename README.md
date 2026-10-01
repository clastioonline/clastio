# Clastio

[![Clastio: Your AI Teaching Assistant](https://repoclip.io/api/badge/174f257e-b32b-4df2-9634-a9473bf979c2)](https://repoclip.io/v/174f257e-b32b-4df2-9634-a9473bf979c2)

An AI teaching assistant for teachers, starting in the UAE with India and international markets to follow.

A teacher uploads a deck they have taught with. The assistant learns its design: slide master, colours, fonts, logo, header bands and layouts. It then plans connected lesson sequences and builds **editable PowerPoint files in that same design**, with speaker notes, activities, quizzes, worksheets, homework and answer keys. It keeps track of each class's timetable, calendar and progress, and can send the day's plan over the official WhatsApp Business Platform.

> **North star:** upload one old deck, ask for *Photosynthesis, Grade 8, 5 lessons × 10 slides*, and get 50 editable slides in the teacher's design with notes, activities, quizzes and homework. This flow is covered by an automated test (`apps/api/tests/test_north_star.py`) and a browser E2E test.

## What's in the box

| Area | What works |
|---|---|
| **Style learning** | PPTX analysis of theme, masters, layouts, recurring decorations, logos, footers and slide numbers. PDF analysis reconstructs the look from vector drawings and text spans. The original file is never modified. |
| **Lesson generation** | Course plan (outcomes, big idea, progression checks), then per-lesson plans (phases, misconceptions, differentiation, exit tickets), then slide specs with 19 layouts, then native editable PPTX. |
| **Design fidelity** | Native templates reuse the teacher's own master and layouts. Text fits the teacher's fonts using real font metrics. Diagrams (process, cycle, timeline, comparison, tables, quiz cards) are native shapes, not pictures. Arabic RTL is supported. |
| **Quality control** | Content QC, layout budgets, then LibreOffice render and visual inspection (overflow, off-slide, overlap, contrast), with an automatic repair loop. Every slide gets a preview image. |
| **Editing** | Slide editor with quick changes ("make simpler", "add examples", "turn into activity" and more), free-text changes, speaker notes, versions and restore, and a per-lesson rebuild. |
| **Documents** | Worksheets, quizzes, homework, lesson plans and teacher guides as DOCX and PDF, each with a separate answer key. Kahoot CSV and Moodle GIFT exports. Question bank. |
| **Planning** | Classes, timetable (CSV import), school calendar (holidays, Ramadan timings, short days), "prepare today / tomorrow / my week", reflections that carry unfinished content into the next lesson, curriculum coverage. |
| **Assistant** | Chat over SSE that plans, creates lessons and documents, answers "what did I teach 8B last week?" and adapts content. The same assistant is reachable over WhatsApp. |
| **Teacher memory** | Preferences stated by the teacher or learned from their slides (always shown and editable), lesson summaries and misconceptions, retrieved with pgvector. |
| **Media studio** | Paid add-on for AI images (OpenAI / Gemini) and short videos (Sora 2 / Veo) with style presets, priced in media credits. Admins set prices, packs, models and lengths, and grant credits. Output is labelled AI-generated and keeps the provider's provenance data. |
| **Business model** | Self-serve SaaS for individual teachers. Every sign-up gets a no-card free trial of a paid plan (admin sets the plan and length), then drops to the Free plan and is invited to upgrade in the app. Hitting any plan limit opens an upgrade dialog. Checkout, plan changes, cancellation and invoices run through Dodo Payments (merchant of record, UAE/India) or Stripe. Plans, prices, limits and the trial are data the admin edits in **Plans & trial**. Schools can be given plans by the admin (never overriding a paid subscription). |
| **Admin** | Platform operators, not customers: no plan, no billing, no onboarding. Admin area only: overview (real revenue from paid subscriptions only, teachers, trial conversion, generation health, AI spend), Teachers (extend trials, grant plans, credits, suspend), Plans & trial, Payments & media, AI costs. |
| **Dashboards** | Teacher dashboard (lessons prepared, weekly activity, next class, upcoming lessons, classes, curriculum coverage, lesson timer, getting-started checklist) with a Tutorials & help section. Separate admin overview (revenue, teachers, generation health, sign-ups, paying teachers, failed jobs) plus Users, AI costs and Payments & media pages. |
| **Two looks** | "Forest" (green, rounded, default) and "Classic" (indigo), each in light and dark. Teachers pick in Settings; admins set the default. |
| **Security & privacy** | Argon2 passwords, HttpOnly cookies, RBAC, signed download URLs, upload validation (optional ClamAV), rate limits, audit log, data export and account deletion (UAE PDPL / India DPDP). |

## Quick start (Docker)

```bash
cp .env.example .env            # optional: add ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY
docker compose up -d --build --wait
open http://localhost:3000
```

Demo accounts (created by the seed unless `SEED_DEMO=false`; never created when `ENVIRONMENT=production`):

| Role | Email | Password |
|---|---|---|
| Teacher with classes, timetable and a plan granted by the admin | `sara@example.com` | `teacher-demo-123` |
| Platform admin | `admin@example.com` | `admin-demo-123` |

Or sign up as a new teacher and go through onboarding with one of the sample decks in [`samples/`](samples).

**Without an AI key** the app runs in *demo mode*. A built-in offline provider produces structured sample content, so every flow works (upload, analysis, planning, rendering, QC, documents, assistant), but the lesson text is generic. A banner in the app says so. Add a key and restart to get real content.

## AI models

All AI calls go through one provider-neutral service with task tiers. Routing is configurable through env vars or live in **Admin → AI costs**, and every call is recorded with tokens and cost.

| Tier | Used for | Default | Fallbacks |
|---|---|---|---|
| planning | course plans, lesson plans | `anthropic:claude-opus-5` | OpenAI, Gemini |
| content | slide decks, documents, rewrites | `anthropic:claude-sonnet-5` | OpenAI, Gemini |
| fast / qc | intent routing, content QC | `anthropic:claude-haiku-4-5` | OpenAI, Gemini |
| embedding | memory, curriculum and source retrieval | `openai:text-embedding-3-small` | Gemini |
| image | illustrations when no CC-licensed image fits; media studio images | `openai:gpt-image-1-mini` | Gemini |
| video | media studio clips | `openai:sora-2` | Gemini Veo |

Style analysis uses no AI at all. It parses the PPTX XML and PDF drawing operations directly, which is exact, fast and free. Structured output uses JSON schemas end to end, so the renderer never parses free text. Images are searched on Openverse (CC-licensed, credited in the speaker notes) before one is generated, and generated images are labelled as AI-generated. Teachers can add an AI-assistance note to file metadata in Settings. The product never claims content was written by a human.

## Local development (without Docker)

Requirements: Python 3.11+, Node 22, PostgreSQL 16 with pgvector, LibreOffice and fonts (see `apps/api/Dockerfile` for the package list).

```bash
# API + worker
cd apps/api
python -m venv .venv && . .venv/bin/activate
python -c "import tomllib;p=tomllib.load(open('pyproject.toml','rb'))['project'];print('\n'.join(p['dependencies']+p['optional-dependencies']['dev']))" > /tmp/req.txt
pip install -r /tmp/req.txt -c constraints.txt
createdb teacher_assistant && alembic upgrade head && python -m app.seed --demo
uvicorn app.main:app --reload --port 8000          # API docs at http://localhost:8000/api/docs
python -m app.worker --concurrency 4               # in a second terminal

# Web
cd apps/web
npm install
npm run dev                                         # http://localhost:3000 (proxies /api to :8000)
```

Long-running generation runs in the separate worker. After a request is accepted, teachers can navigate away or close their browser and recover results from **Activity** and in-app notifications. Assistant replies are saved with their conversations. File uploads must finish transferring before closing the tab; analysis then continues in the background. The API and worker must share the same database and storage (as configured in Docker Compose).

## Tests

```bash
cd apps/api && createdb teacher_assistant_test && python -m pytest -q
cd apps/web && npm test && npm run typecheck && npm run build
cd apps/web && BASE_URL=http://localhost:3000 node e2e/run.mjs          # needs a running, demo-seeded stack
cd apps/web && BASE_URL=http://localhost:3000 npm run e2e:background   # navigation, reopening, notifications and mobile Activity
```

The API tests run against real Postgres, real LibreOffice rendering and the offline AI provider. They cover the north-star deck (50 slides, teacher decorations and fonts preserved, notes, previews, zero QC errors), style analysis of PPTX and PDF, the AI adapters (with mocked SDKs), billing webhooks, WhatsApp signatures and commands, planning, memory, the assistant and security. The browser E2E test signs up, uploads a deck, builds lessons, downloads the PPTX, edits a slide, creates a worksheet, chats with the assistant and visits every page on desktop and mobile. CI (`.github/workflows/ci.yml`) runs all three, including the E2E test against the Docker Compose stack.

## Repository layout

```
apps/api     FastAPI API + job worker (Python)
  app/ai          provider-neutral AI service: Anthropic, OpenAI, Gemini, offline
  app/engine      style analysis, templates, PPTX renderer, visual QC, document exports
  app/generation  planning → lesson plan → slide specs pipeline, budgets, prompts
  app/services    courses, planner, assistant, memory, billing, WhatsApp, admin …
  app/jobs        Postgres job queue and handlers
apps/web     Next.js teacher app, marketing pages and admin
samples      sample teacher decks (PPTX + PDF) and the script that makes them
docs         product spec, research, architecture, deployment
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how the pieces fit, the generation pipeline and the design decisions
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md): production setup, configuration, scaling, backups, costs
- [`docs/PLATFORM.md`](docs/PLATFORM.md): accounts, roles, audit, limits, notifications, legal, admin console, production checklist and what is not implemented
- [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md): full product and build specification (v2)
- [`docs/RESEARCH_NOTES.md`](docs/RESEARCH_NOTES.md): market, regulatory and technical research behind the spec
- API reference: `http://localhost:8000/api/docs` (OpenAPI, 107 operations)

## Current status and known limits

- **Dodo Payments, Sora 2 and Veo are implemented against their official SDKs but not yet exercised against the live services.** Webhooks, checkout parameters and the video adapters are tested with signed payloads and fake SDK clients; do a test-mode purchase and one short video before launch.
- **Live AI providers are implemented but not yet exercised against real APIs.** The Anthropic, OpenAI and Gemini adapters are unit-tested with mocked SDK clients, and every end-to-end run so far used the offline provider. The first thing to do with real keys is generate the north-star course and review content quality and cost in Admin → AI costs.
- **Curriculum data is illustrative.** The seeded outcomes are topic-level starter sets under our own codes. Import the official framework documents (UAE MoE, CBSE, NGSS, Cambridge and others) before selling to schools.
- **Integrations need credentials:** Dodo Payments or Stripe, WhatsApp Cloud API (message templates must be approved by Meta), Google/Microsoft sign-in, SMTP, S3. Without them the app uses manual plans, a WhatsApp simulator, email/password sign-in, logged magic links and local storage.
- **Arabic UI is partial.** Navigation and the dashboard are translated and the layout switches to RTL. Generated Arabic slides are fully RTL.
- **Scanned PDFs are not supported yet.** There is no OCR, so upload the original PPTX or a text-based PDF. The same applies to scanned reference material.
- **A vision model tier is configured but unused.** It is reserved for future scanned-page understanding.

# Clastio architecture upgrade

The existing native master/template engine, PostgreSQL queue (`FOR UPDATE SKIP LOCKED`), Sentry initialization, provider circuit breakers, and notification dispatch remain the foundations. This upgrade adds the following behavior.

## Generation and delivery

`POST /api/v1/courses/{id}/generate` accepts `bundle: true` and returns `202` with `job_ids`. The project preparation dialog exposes this option and explains the additional document credit cost. The worker produces the deck, DOCX lesson plan, Support/Core/Extension worksheet with an answer key, and quiz exports before completing the bundle job. Standard document downloads expose these files. Quiz exports include Kahoot CSV and Moodle GIFT; GIFT is the existing native Moodle import format, rather than an invented Moodle CSV format.

Document IDs derive from the job ID and document kind. A retry reuses completed documents and resumes unfinished ones. A saved generation-job checkpoint prevents rebuilding the slides during a document-stage retry. A failed bundle can leave useful completed files available; Activity reports the failure. Starting a new generation is a new job and consumes the appropriate credits.

The generated lesson-deck schema validates a maximum of 120 visible words per slide, excluding teacher notes. Existing finer template budgets still apply. Prompts prefer native diagrams. UAE context includes WALT/WILF, measurable progress, misconceptions, cross-curricular and moral education links, and differentiated support. DOCX plans label WALT/WILF explicitly. These planning aids do not certify inspection compliance.

## Rendering and database connections

Docker Compose runs a pre-warmed Gotenberg service for PPTX/DOCX to PDF. PyMuPDF still produces PNG previews and performs local geometric QC from the returned PDF. Configured sidecar failures never launch local LibreOffice, preserving process isolation. `GOTENBERG_URL` can point to another private renderer; an empty value retains local LibreOffice for non-Docker development. Legacy `.ppt` to `.pptx` conversion continues to need local LibreOffice.

API and worker connections pass through PgBouncer in transaction mode. `MAX_PREPARED_STATEMENTS=100` enables protocol-level prepared-statement support for SQLAlchemy/asyncpg. Migrations connect directly to Postgres. Transaction-scoped advisory locks remain compatible with pooling. Both services are private to the Compose network. Production resource limits isolate renderer memory from workers.

Place licensed fonts in `deploy/fonts` and restart the services. The directory is shared by API, workers and Gotenberg. Donor font requirements are extracted from actual PPTX XML, audited against the worker's fontconfig inventory, logged, stored with the template and displayed in the design screen. The worker and sidecar also need matching standard-font inventories: the stock images have different font packages, so worker checks alone do not certify every sidecar font. Review rendered previews after installing or substituting fonts. Proprietary font binaries are ignored by Git.

## Task routing and costs

| Task | Default route |
| --- | --- |
| Curriculum/lesson planning | `anthropic:claude-sonnet-4-6` |
| Slide JSON and document content | `openai:gpt-4o-mini` |
| Chat and intent routing | `groq:llama-3.3-70b-versatile` |
| Visual review | `gemini:gemini-3.5-flash` |
| Scanned PDF ingestion | `gemini:gemini-3.5-flash` |
| Explicit current/live teaching search | `perplexity:sonar` |
| Daily teacher reflection | `openai:gpt-4o-mini` |
| Audio transcription | Groq `whisper-large-v3-turbo`, or OpenAI `whisper-1` when Groq is unconfigured |

Environment settings and existing admin routing overrides take precedence. Existing fallbacks apply only to providers supporting the task. Groq Llama uses JSON mode followed by Pydantic validation. Perplexity responses retain HTTPS source citations. Requests for “live search”, “search the web”, “latest” or “current” facts use Sonar when configured and classified as teaching-related.

The prompt's historical Claude 3.5 models are retired; Sonnet 4.6 is Anthropic's listed replacement. Gemini 1.5 is also historical; current multimodal Flash serves ingestion and vision without a separate invented `-vision` model ID. See [Anthropic's lifecycle documentation](https://platform.claude.com/docs/en/about-claude/model-deprecations) and [Google's lifecycle documentation](https://ai.google.dev/gemini-api/docs/deprecations).

Anthropic adapters mark stable system prefixes with explicit cache control. OpenAI and current Gemini use provider-managed automatic prefix caching; stable systems precede volatile user data and cached token usage is recorded. Cache hits depend on provider thresholds and repeat prefixes. The existing tenant-scoped result cache is separate from provider prompt caching.

Add credentials and administrator-approved rate cards before enabling new live routes. Transcription and Sonar include charges that are not fully described by token usage, so accounting retains the approved reservation ceiling for invoice reconciliation. Audio and ingestion images have separate bounded input limits in the budget policy; price-card ceilings must cover these maximum inputs. No paid provider tests are run automatically by this change.

## Teacher feedback

Alembic revision `h208feedback01` creates `slide_feedback` with owner, slide version, before/after JSON and reflection state. Manual editor changes write durable diffs in the same transaction as the slide edit.

The lesson screen has an explicit “Use this slide as a future example” action. The corresponding owner-checked acceptance endpoint is idempotent per slide version. Accepted JSON is stored in `teacher_memory` metadata, with a semantic embedding for retrieval. Future context retrieves the top two teacher-scoped examples. Downloads are never inferred to be acceptance.

The scheduler runs a bounded daily reflection through the reflection tier, marking diffs consumed only after successful profile updates. An advisory transaction lock coordinates multiple schedulers. Reflection skips offline mode. Teacher-stated preferences take precedence over inferred suggestions; suggestions retain confidence and remain editable and unconfirmed.

## WhatsApp voice

Signed inbound audio webhooks log the Meta message ID, queue `whatsapp_voice`, and acknowledge receipt without running transcription or an LLM inside the webhook. The worker retrieves media metadata from Meta, permits only HTTPS Meta attachment hosts, rejects redirects, bounds audio size, and transcribes through the same spending/circuit-breaker layer as other AI calls. Successful transcripts are checkpointed for retries; raw audio is not stored.

The fast router extracts topic, grade, subject, slide count and duration. Complete requests create an asynchronous course with automatic first-lesson bundle generation. Missing required parameters receive a clarification. Stable owner-scoped course IDs derived from the inbound message ID prevent a retry creating a second course. Non-generation requests use the existing assistant. Workers recheck active accounts and WhatsApp consent before processing and sending results. Existing completion notifications deliver approved WhatsApp templates, opted-in Web Push and email.

External WhatsApp sends are still at-least-once: Meta does not provide an exactly-once send primitive, and a process crash after Meta accepts a message but before the local commit can produce a duplicate. Template approval and live media/API access require production verification.

## PDF source ingestion

Text-based source extraction stays local and exact. Scanned or unreadable pages in mixed PDFs go through the ingestion route using bounded rendered page images; original page numbers are retained. At most 40 scanned pages are processed per upload, and blank/illegible output adds no invented text. Original text and transcriptions are chunked into the existing owner-scoped pgvector source store. Offline mode asks for an OCR/text PDF. AI transcription requires teacher review for equations and small print.

## Deployment

Run `alembic upgrade head` against the direct database connection, rebuild API/worker/web, and recreate Compose services. Existing `.env` values and admin overrides are not rewritten: review their model routing explicitly. Verify real provider access, approved price cards, WhatsApp templates, email and Push credentials, and representative school fonts before production use.

# Original-template PPTX generation

## Implemented flow

The New chapter form includes **Base PowerPoint template**. With a PPTX selected, it sends the original file (`file`) and the JSON teaching brief (`payload`) in one multipart request to `POST /api/v1/courses/from-template`. Without a file it uses the existing course endpoint.

Uploads use the existing ownership, file-size, magic-byte/OOXML/macro validation, virus-scan and storage controls. The original bytes are stored unchanged. Template slot discovery and style analysis run in a thread. The template’s sample text is excluded from factual teaching context. The template is then attached to the normal queued course/lesson worker, which retains source grounding and content-first lesson generation.

The new preserved-template mode fills title, subtitle, body and image placeholders. Alternatively, name top-level shapes `clastio:title`, `clastio:subtitle`, `clastio:body`, or `clastio:image`; text tags `{{title}}`, `{{subtitle}}` and `{{body}}` also work. Each usable donor needs a title slot, and at least one needs a body slot. Support is for 1–30-slide PPTX templates. Unmarked text, logos, backgrounds, existing theme/master/layout parts and decorative shapes remain in their template design. Original text paragraph/run properties are reused; original font sizes are not auto-shrunk. Output repeats existing body designs when additional slides are needed.

SlideSpec strict JSON fields map to those slots: title to title; subtitle to subtitle; bullets, steps, definitions/vocabulary, columns, questions and table text to body; `visual.image_query`/description through the existing image resolver to the image slot. Native charts/grouped content are not automatically redesigned or populated; use suitable text or image slots for generated material. Image slots require a resolved image, and unresolved slots fail generation instead of publishing an empty slot. Existing ordinary, unmarked pictures are preserved.

Presenton's `infographic_markdown_to_plain_text` and `repeated_child_source_index` functions were extracted into `app/engine/render/vendor/presenton.py`; Apache-2.0 licence and NOTICE are included. Clastio's new injection adapter uses these helpers, existing relationship-safe slide cloning, python-pptx and existing image services. Presenton's separate Node export runtime was not copied.

`MODEL_TEMPLATE_CONTENT` defaults to `openrouter:openai/gpt-4o-mini` for template content formatting. The scoped override is reset after generation, so concurrent jobs do not inherit it. Planning still uses the planning tier. Structured provider calls already enforce strict JSON schema and server validation. Configure the OpenRouter key in `.env`; approve the `openrouter:openai/gpt-4o-mini` price card from `docs/openrouter-rate-cards.json` in Admin → AI costs and enable live spending controls. Missing price cards remain a hard stop. No API key is sent to the browser.

## Local startup — recommended complete backend

Run from the project root. Keep your existing `.env`; do not overwrite its keys.

Terminal 1, FastAPI, worker, PostgreSQL, Redis and the document renderer:

```bash
cd /Users/macbookpro/development/ai-teacher-assistant
docker compose up -d --build --wait api worker
```

Terminal 2, Next.js on localhost:3000:

```bash
cd /Users/macbookpro/development/ai-teacher-assistant/apps/web
npm ci
API_URL=http://localhost:8000 npm run dev
```

Open `http://localhost:3000/projects/new`. Avoid starting the Docker `web` service alongside this frontend because both use port 3000. The Docker backend includes LibreOffice/fonts and shares storage between API and worker. Check jobs with `docker compose logs -f api worker`.

## Native Python alternative

Requires an existing PostgreSQL database with pgvector, Redis, LibreOffice and suitable template fonts. Set their connection paths in `.env` first. From the project root:

```bash
python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt -c apps/api/constraints.txt
cd apps/api
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload --port 8000
```

A second backend terminal:

```bash
cd /Users/macbookpro/development/ai-teacher-assistant/apps/api
.venv/bin/python -m app.worker --concurrency 4
```

Use the Next.js terminal command above as the third terminal. Actual runtime libraries were installed and tested in `/private/tmp/clastio-presenton-venv`; project-local setup above is reproducible after temporary directories are cleared.

## Testing checklist

1. At localhost:3000/projects/new, choose `samples/preserved-template.pptx`, enter a chapter, grade and subject, and submit. Network tools should show multipart/form-data with `file` and `payload`.
2. Follow Activity until planning/lesson generation finishes. Live AI requires the key, enabled budgets and approved model price cards. Offline mode checks the plumbing with sample content, not educational quality.
3. Download the PPTX and open it in PowerPoint or LibreOffice. Verify the generated title/body replaced sample text, while fonts, font sizes, colours, decorative bar, positions, dimensions and masters retain the original design.
4. Test your own template with a picture placeholder or named picture `clastio:image`; check that a relevant resolved image fills the existing frame. Ordinary logos/pictures must remain untouched. If no image is found, confirm the job reports the problem.
5. Use an intentionally tiny body placeholder or excessive text. Confirm a bounded fit-repair failure rather than font shrinking or silent clipping. Explicit manual edits remain available in the existing editor.
6. Test a PPTX without content slots, a renamed non-PPTX, and a macro-enabled file; these should be rejected before generation.

## Validation and limits

422 API unit tests passed with two pre-existing unrelated cases excluded (stock fallback wording and expired-session push). New tests cover multipart mapping, unchanged original upload bytes, repeated-slide content injection, run/shape formatting preservation, unchanged theme/master/layout ZIP parts, named-image geometry, overflow rejection, and scoped model routing. Next.js type checking and fixture browser checks passed at 320, 390 and 1280px. A four-slide output is available at `/private/tmp/clastio-preserved-template-result.pptx`.

These checks used deterministic content and mocked browser API requests. A paid live OpenRouter generation and a visual comparison in the desktop PowerPoint application were not run. Actual rendering depends on available fonts; the Docker worker includes the supported rendering stack. Install proprietary template fonts on the worker when necessary. A template with no suitable content slots cannot be filled reliably; the app reports that requirement instead of reconstructing its design.

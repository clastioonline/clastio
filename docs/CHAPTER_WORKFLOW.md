# Chapter preparation and manual slide editing

Open `/projects/new` and choose the chapter topic, grade, subject and number of lesson parts. The **Books & notes** upload button is at the top of the form. It accepts PDF, DOCX, TXT, PPT and PPTX and also lets the teacher select previously uploaded sources. Sources are stored once, indexed in bounded embedding batches, and retrieved only from the selected files for this chapter. A different teacher's files cannot be attached. Wait for processing to finish before submitting. Scanned PDFs without readable text receive a clear error; automatic OCR is not included.

Choose a preparation mode:

- **Complete chapter:** plan the connected sequence and, when automatic building is enabled, build all lesson parts.
- **In parts:** plan the complete sequence first, then select individual parts or a group on the project page. No parts are automatically generated.
- **Day by day:** plan the complete sequence and build only lesson 1 when automatic building is enabled. After teaching, record class notes and prepare the next lesson. This is teacher-controlled preparation, not unattended daily scheduling.

The creation form and preparation dialog ask what was already taught, what needs revision and any extra instructions. When generating later lessons, recorded taught lessons, reflections and unfinished-work carry-over are included. Preparing a file does not imply the class has already been taught. After-class notes can record difficulties and the last completed slide; these affect the next lesson's recap or unfinished work.

Open a generated lesson's **Slides & manual editor** tab. Teachers can change title, subtitle, content, steps, quiz answers, layout, timing, columns, table cells, chart categories/series/source/units, vocabulary and notes. They can upload a PNG/JPEG/WebP to replace an image and choose full-image containment or cropped frame filling. **Save & rebuild** validates and versions the changes, then rebuilds PPT/PDF and previews without an AI slide rewrite. Version history supports restoring earlier edits. For free-positioning shapes, font styling and full desktop editing, download the editable PPT and open it in PowerPoint; importing desktop edits back into this editor is not implemented.

Image modes offer automatic reuse/search/generation, preferred AI illustrations, or reuse/licensed images without paid generation. Existing uploaded visuals and native diagrams remain reusable. Requested diagrams skip stock-photo search. AI prompts include subject, grade, topic and slide purpose. Image-generation attempts are bounded, invalid images fall back, and placeholders are labelled in the image, notes and lesson warning. Full-image containment is the default to preserve diagram details. Real image relevance still requires teacher review; no live image-quality claim is made by these offline checks.

Gemini is optional: the existing OpenAI and Gemini adapters both support image generation. An API key alone does not enable paid images. Live mode, an allowed/priced image route, the image feature flag, account image allowance and budget policy must permit the call. Local review services remain in offline mode, and no new paid AI calls were made for this feature validation.

Validation: 217 offline backend tests passed; frontend TypeScript passed; the browser journey passed source upload/selection, daily chapter creation, next-day preparation, manual table editing, persisted PPT download links and layouts at 390 and 1440 pixels. Run `npm run e2e:chapter` in `apps/web` against the offline local review stack. Browser screenshots are under `apps/web/e2e/screenshots/chapter-review/` (ignored artifacts).

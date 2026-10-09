# Saved books and content-first lesson generation

The Books & notes page (`/books`) lists the teacher's existing sources. A direct public PDF URL can be imported in the background, or an authorised copy can be uploaded. Originals stay in the configured object storage; source text and embeddings stay in PostgreSQL. Saved originals open through signed URLs. This is a private teacher library, not a complete shared UAE textbook catalogue.

Online book discovery uses the configured search model only when **Find books** is clicked. The query result is cached per teacher. Saving the same source URL reuses its saved file; content hashes deduplicate identical uploads. Ready indexed books skip re-indexing. Publisher login pages cannot be imported as PDFs.

PDF table-of-contents entries supply chapter ranges when present. Teachers can save custom ranges in the library and select them when creating a course. Ranges use PDF page positions including covers, not the printed page labels. A range supports at most 80 pages; the chapter preparation request has a shared 40 KB UTF-8 source allowance. Oversized selections produce an explicit coverage warning. Without a range, relevant excerpts are used and the teacher is warned that full chapter coverage is not confirmed.

Before allocating lessons, the planning model creates a chapter topic/prerequisite pack from selected sources. If no usable source text exists and research is enabled, the search model researches the chapter once. The resulting pack is cached by teacher, chapter, curriculum, grade, language, source hashes and page ranges. Every pack topic must appear in a lecture's key concepts. All lessons in the chapter reuse the saved pack. Missing evidence remains visible on the chapter page.

Each live lesson uses the planning tier to write definitions, explanations, solved examples, misconceptions, student checks and expected answers. Content completeness and sequence are validated before formatting. The content tier chooses layouts and formats groups of at most three slides. An invalid layout plan gets one repair; an invalid batch gets one repair, then publication stops. Flexible slide counts allow up to three additional/fewer slides within the existing 4–30 limit. Exact counts are available by disabling flexibility. Credits reserve the maximum and charge the slides actually generated.

Existing native diagrams, image relevance checks, overflow repair and separate preview/editor views remain in use. Rendered page review now uses groups of four previews, at most two findings per group and six targeted repairs per deck. Teacher-positioned objects are preserved. Ordinary budget enforcement preserves complete content; overflow handling retains the existing last-resort strict fit.

OpenRouter requests include usage metadata and use reported total cost when available, including search request fees. Missing search charge metadata remains subject to the existing conservative spending controls. No budget ceiling is increased by this workflow. A configured search model and approved price card are required for online discovery/research; saved books can be reused without those search calls.

Model output still requires teacher review. UAE examples do not establish MoE approval. Matching the curriculum, subject, grade, language and edition is necessary before importing an initial collection. Restricted textbooks require an authorised teacher copy; this change does not preload unverified books.

## Validation

388 API unit tests passed, excluding two pre-existing failures: the legacy stock-photo fallback wording expectation and expired-session push delivery. The new book/workflow tests cover cache reuse, ownership, PDF validation, physical page counts, saved bookmarks, UTF-8 source limits, topic coverage, bounded retries, flexible counts, and valid block-specific citations. Web type checking and browser tests passed for the library at 320, 390, 768 and 1280 pixels, chapter selection, cached discovery, PDF-import controls, and existing mobile preview/editor navigation. Browser requests used fixtures; no paid model calls or production teacher files were used for these checks.

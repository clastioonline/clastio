# Planning, PPT review and uploaded designs

Choosing six classes creates a six-class course plan. Automatic generation now builds only lesson 1. The teacher opens that PPT, reviews the slides, requests edits or a rebuild, then approves the completed version. Only then can lesson 2 be generated. The API enforces this even when called outside the web form. Bulk generation is rejected; the initial credit estimate includes planning plus only the first PPT.

Approval is tied to the lesson version. A rebuilt or edited PPT requires another review. Feedback entered with approval is supplied to later lessons. Approval does not start the next paid job automatically: the teacher chooses Prepare next lesson.

Live PPT generation now plans a slide-by-slide outline before writing the deck. It checks consecutive slide numbers, a cover slide and total class time. Writing uses that outline with medium reasoning; the existing structural, answer-key, text-budget and rendering checks still apply. Course planning rejects a repaired sequence that still duplicates concepts or has excessive overlap.

Native PPTX extraction preserves donor designs from every source page, including unique layouts. AI classifies all source pages in batches using rendered thumbnails of every source page together with extracted text, notes and design metadata. The renderer matches the slide purpose to an original donor, retaining native layouts/backgrounds/decorations and page-specific text zones, fonts and colours. Stage navigation layouts retain priority. Existing native templates upgrade from their original upload in the worker; reuploading is not required. New inspection uses the configured vision route and an approved price card.

AI classifies teaching purpose; the native PowerPoint parser reads the actual visual properties. This is not a guarantee of a pixel-identical recreation of arbitrary diagrams, SmartArt, mixed typography or unsupported fonts. PDF designs remain reconstructed approximations. A live generated PPT and its source must be compared visually to establish fidelity and teaching quality; automated tests do not establish those outcomes.

Deploy API, worker and web changes together. No database migration is required: version-specific approval and review feedback use the lesson's existing QC JSON. Already queued bulk jobs are not cancelled by this release. A completed old lesson also needs approval before proceeding.

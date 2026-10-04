# Uploaded PowerPoint design inspection

Upload a PowerPoint under Designs to create a reusable template, then select it when preparing a lesson. This workflow extracts visual design; it does not copy the original teaching content into every generated slide.

The native extractor scans every source slide and reads themes, masters, layouts, fonts, colours, recurring decorations and teaching-stage variants. Template details now show a slide-by-slide inventory, including explicit fonts, tables, charts and pictures.

New editable tables reuse the dominant uploaded table's explicit cell fills, borders and text formatting, plus its table-style reference. Font sizes still fit the generated content and respect the renderer's legibility limits. New supported bar, line and pie charts reuse the dominant matching chart style and series formatting. Source values, categories and series names are not copied. New stage headings use detected text colours and sizes instead of a fixed black, 28-point heading.

Template specification version 4 triggers refresh of older native uploaded templates when reused for generation. Their original upload must still exist in the configured shared storage. API and worker must use the same R2/S3 bucket. Previously exported lesson files are not automatically rebuilt.

Limits: this is a reusable design system, not an exact clone of every source page. Mixed table designs use a dominant style. Unsupported chart types, image-based tables/charts, animations and arbitrary diagram layouts are not recreated as editable equivalents by this update. Fonts missing from the rendering environment can be substituted. PDF templates remain reconstructed designs.

Validation: synthetic 16-slide PowerPoint with tables and a chart on its last slide; generation round-trip verifies new editable data alongside original table fills, font colour, chart style and series fill. Existing native extraction and content-quality tests also run without provider calls.

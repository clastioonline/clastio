# UAE classroom presentation library

The library includes 12 additional native, editable classroom designs alongside Clean Classroom, Warm Sand and Chalkboard. These are independent themes for teachers working in UAE schools; they contain no school logos, official school branding or endorsement claims.

| Design | Intended classroom use | Design treatment |
| --- | --- | --- |
| UAE Heritage | Social studies, moral education, history and geography | Sand background, green and terracotta geometry, Caladea headings |
| Green Emirates | Ecosystems, climate and sustainability | Pale green canvas, emerald and teal circles, Montserrat headings |
| Maths Studio | Mathematics and worked examples | Graph-paper details, wide content area, square cards, Roboto and Carlito |
| Discovery Lab | Science, evidence and experiments | Deep teal title band, molecule motifs and Open Sans body type |
| Language & Stories | Reading, vocabulary and language discussion | Book-spine border, plum and copper accents, editorial headings |
| Arabic Classroom | Arabic, Islamic education and bilingual material | Restrained geometry and Noto Sans Arabic for Arabic text |
| Little Explorers | KG and early primary | Larger type, fewer words and playful native shapes |
| British Classroom | Retrieval, explanation and secondary practice | Navy header, gold accents, quiet square cards |
| CBSE Concept Builder | Definitions, worked examples and guided practice | Stepped margin blocks, burnt-orange and blue accents |
| IB Inquiry Atelier | Inquiry, perspectives and reflection | Open frames, violet and teal accents |
| Emirates Learning | Lessons using the teacher's selected UAE MOE curriculum | Green header, red edge details and a clean bilingual canvas |
| Future Makers | Computing, AI literacy and design projects | Circuit-like edge geometry, blue and teal panels |

Arabic text uses the existing renderer's complex-script font and paragraph direction support. Selecting an Arabic-friendly template alone does not translate content: teachers choose English or Arabic in the lesson form. Arabic runs in mixed text receive the Arabic font; the app has no separate bilingual language toggle.

## Suggestions and teacher choice

`GET /api/v1/templates` returns the accessible designs and up to three suggestions with reasons. Optional `subject`, `grade`, `language`, `curriculum` and `class_id` parameters refine the context. A class must belong to the signed-in teacher. Explicit lesson context takes priority over owned class defaults, which take priority over profile defaults. School names are displayed as context and never used to infer a curriculum or affiliation.

Suggestions favour a saved default, the teacher's own uploaded design or a design shared with their non-null organisation, then matching subjects, curriculum, grade and language. Subject-specific designs outrank more general themes when relevant. Age-inappropriate designs are penalised. Another teacher's uploads are excluded, including shared uploads with no organisation.

The gallery supports subject/tag search, UAE and suggestion filters, and a **Use for a lesson** link. The lesson form displays reasons and allows viewing the full collection. Receiving new suggestions or changing subjects does not overwrite a manual selection. Loading the template list before the teacher's profile also preserves the saved default.

## Deploying the catalogue

The normal Railway pre-deploy step seeds the library:

```sh
sh -c 'alembic upgrade head && python -u -m app.seed --skip-embeddings'
```

The seed creates new designs and updates older curated revisions in place while preserving template IDs, saved defaults and uploaded templates. New base objects use versioned storage keys. Once the revision is current, reseeding does not upload or render it again. Initial seeding renders the previews with LibreOffice and requires working storage credentials and the export image's fonts.

The catalogue and suggestion logic make no external AI calls and add no generation credits. Normal deck generation still consumes the plan's usual credits.

## Verification

- 34 unit cases cover all 15 editable native decks, distinct geometry, text contrast, Arabic direction/font, subject/curriculum/grade matches, saved defaults, private uploads and seed idempotency.
- Four API cases cover owned class context, curriculum independence from school names, private uploads and organisation sharing, course access rejection, and persistent IDs/storage keys on reseeding.
- `node e2e/uae-templates.mjs` checks gallery search, design selection and recommendation updates without replacing teacher choices, plus 320, 390 and 1440 pixel layouts. It uses mocked API responses and an isolated local browser.
- Native PPTX/PDF exports and a contact sheet are saved during local release verification in `/private/tmp/clastio-uae-export`.

Teaching accuracy is handled by the generation quality checks. A template recommendation selects visual presentation, not curriculum facts or a guarantee of school compliance.

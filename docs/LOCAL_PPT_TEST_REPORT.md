# Local test using the supplied PowerPoint

Source: `W02-G01-Math-Understand Addition and Subtraction-P1 1.pptx` (10 slides, Grade 1 Mathematics). The original file was read without modification. Testing used the local web app at http://localhost:3008 with PostgreSQL, API and background worker. AI stayed in explicit offline mode; no provider charges were incurred.

## Findings and fixes

1. **Generated presentations could not render.** The supplied deck has several slide masters with navigation links to individual slides. Deleting the source slides did not remove those references. Old slides remained reachable in the PowerPoint package, then collided with the filenames assigned to new slides. Generated files contained duplicate slide XML entries. Slide removal now removes associated internal navigation references. The renderer also cleans old cached templates before adding slides. External links and the source file are not changed.
2. **Blank previews incorrectly appeared to pass QC.** The API now records whether visual inspection actually ran. The editor warns when it was unavailable instead of showing “QC passed”. Failed rendering also clears the previous PDF download so it cannot serve an outdated version.
3. **Master text caused false overflow errors.** Visual QC now includes visible text shapes inherited from slide layouts and masters. The source sidebar labels no longer trigger false overflow failures.
4. **Offline output looked like normal teaching content.** The lesson editor now labels offline sample content explicitly. This matters because generic sample text is unsuitable for validating Grade 1 mathematics accuracy.

## Retest evidence

- Supplied deck upload and reusable template extraction: passed.
- Six template preview layouts: rendered, zero visual QC errors.
- Two Grade 1 Mathematics lessons, 10 slides each: generated with all previews.
- Quick slide edit: passed; edited lesson has zero visual QC errors.
- PowerPoint and PDF downloads: passed; PDF contains 10 pages.
- Edited PowerPoint: no duplicate ZIP entries; original slide dimensions retained (12192000 × 6858000 EMU).
- Both cached templates/lessons from the initial failed run: repaired and rerendered successfully.
- Worksheet plus answer-key/export links, assistant background reply, notifications, support, mobile layout and admin pages: full browser E2E passed with no browser errors.
- Backend: 187 tests passed, including regressions for master navigation and inherited text. Ruff passed.
- Web: production build passed; 4 tests passed.

Local review files (generated and ignored by Git):

- [Edited PowerPoint](../apps/web/e2e/screenshots/root-ppt-review/lesson1-edited.pptx)
- [Edited PDF](../apps/web/e2e/screenshots/root-ppt-review/lesson1-edited.pdf)
- [Quality report](../apps/web/e2e/screenshots/root-ppt-review/review.json)
- [Editor screenshot](../apps/web/e2e/screenshots/root-ppt-review/07b-edited-lesson.png)

## Quality boundary

**The local workflow and rendering passed. Teaching-content accuracy has not passed a live evaluation.** Inspection of the offline PDF found generic placeholder statements rather than a suitable Grade 1 explanation of addition. These files demonstrate template preservation and app functionality; they should not be used as classroom-ready lessons.

The user authorized a live OpenAI test with a $1 total ceiling on 2026-10-02. The saved key authenticated successfully and exposed the selected models, GPT-4.1 mini and text-embedding-3-small. The isolated review runner used a $0.95 admission cap, disabled paid images, and recorded every attempted call.

The live content evaluation is blocked by OpenAI billing: HTTP 429, `insufficient_quota` / `credit_balance_exhausted`, with “You have no credits remaining.” No live lesson or worksheet was produced. Confirmed spend is $0; unresolved reservations total $0.103, retained conservatively because the provider returned no usage. This is not a confirmed charge. Do not clear these reservations or reset the budget merely to retry.

Paid generation was paused in the runner's cleanup, and the offline review worker restarted. Add API credits to the key's OpenAI project/account before resuming within the original cumulative $1 authorization. The local review evidence is in `apps/web/e2e/screenshots/live-openai-review/report.json`.

## Live review resumed after credits were added

On 2026-10-02 the live OpenAI review completed within the original cumulative $1 authorization. The admission ledger was preserved across retries: total recorded spend is **$0.01227614**, with **$0.203** still held conservatively for calls without reported usage. Total recorded spend plus holds is $0.21527614. Paid generation was paused again and the offline review worker restored.

Live calls exposed two strict-schema defects, now fixed: schema cleanup removed actual properties named `title`, and unrestricted dictionary objects omitted the `properties` keyword. Both schema regression tests passed in isolation under the container's supported Python runtime. The usual pytest run was unavailable: the container has no pytest, and the host virtual environment uses Python 3.10, which cannot import `datetime.UTC`. `git diff --check` passed.

Completed artifacts:

- [Live PowerPoint](../apps/web/e2e/screenshots/live-openai-review/lesson.pptx)
- [Live lesson PDF](../apps/web/e2e/screenshots/live-openai-review/lesson.pdf)
- [Worksheet PDF](../apps/web/e2e/screenshots/live-openai-review/worksheet.pdf)
- [Answer key PDF](../apps/web/e2e/screenshots/live-openai-review/answer-key.pdf)
- [Visual contact sheet](../apps/web/e2e/screenshots/live-openai-review/contact-sheet.png)
- [Live spend and stages](../apps/web/e2e/screenshots/live-openai-review/report.json)

The lesson contains 10 slides and a 10-page PDF, with all slide previews present, no duplicate PowerPoint ZIP entries, no automated visual QC errors, and no text overflow reported. Visual inspection confirmed the original design and readable slide layout. All six worksheet answers were checked and are mathematically correct.

**Content evaluation: functional generation passed; classroom readiness needs revision.** The lesson timings total 60 minutes rather than the requested 45. Slides 3 and 6 show decorative placeholder images instead of the apples and counters described in teacher notes because paid images and stock search were disabled. The exit ticket asks for an addition problem without supplying one. The partner task does not explicitly bound the combined total to 10. The worksheet true/false question renders two extra empty options. These limitations are not detected by the current automated visual QC; a passing visual report does not establish teaching-content quality.

## Extraction and content improvements after review feedback

The previous output kept the sidebar but collapsed the source's distinct lesson phases into one layout. Extraction now identifies all eight navigation stages from the source's pointer and master labels, preserves their matching layout and header, and clears old date text when copying header shapes. Font and colour resolution now uses the actual slide master, paragraph fonts and theme colour transforms. The cover retains its original text placement and Times New Roman typography.

Content extraction now reads groups, tables, notes and visible inherited text, and keeps original teaching pictures (including picture fills) for reuse. Saved native templates upgrade from the preserved upload; template colour/font/size customizations are retained. The local review template was upgraded to version 3, with 10 source slides, 12 distinct source images, and all eight stages. Source text and a bounded numbered picture sheet are available to the generation pipeline so image-based examples can be inspected instead of inferred from filenames. Cross-teacher asset reuse is rejected.

Inspection also found inconsistent quantities in some original illustrations: the apple picture shows three objects of each colour while its written problem uses four, and the cube comparison picture shows three red cubes next to a `4 + 2` equation. These are content problems in the source pictures. The revised sample replaces inconsistent examples with native editable counting diagrams and keeps the original UAE flag and self-reflection pictures. Diagram object counts match their equations, and checks can hide the total. Practice and exit tickets state explicit problems and include teacher-note answers. The open partner task bounds the whole to at most 10; slide timings total 45 minutes. Worksheet exports omit empty answer options.

Revised review artifacts, created locally with **zero new provider calls**:

- [Revised PowerPoint](../apps/web/e2e/screenshots/extraction-improvement/revised-lesson.pptx)
- [Revised lesson PDF](../apps/web/e2e/screenshots/extraction-improvement/revised-lesson.pdf)
- [Revised contact sheet](../apps/web/e2e/screenshots/extraction-improvement/revised-contact-sheet.png)
- [Revised worksheet](../apps/web/e2e/screenshots/extraction-improvement/revised-worksheet.pdf)
- [Revised answer key](../apps/web/e2e/screenshots/extraction-improvement/revised-answer-key.pdf)
- [Review result](../apps/web/e2e/screenshots/extraction-improvement/revised-review.json)

Validation: **195 backend tests passed** in the separate `pptgenie_extraction_test` database; Ruff and `git diff --check` passed. The revised 10-slide sample has no visual QC errors or reported text overflow. It contains two original pictures and five exact editable counting diagrams. The original upload and previous live-review exports remain untouched. The local API and worker run in offline mode.

**Live validation of the new source-aware generation remains pending.** Automatic approval review rejected a new paid run because its payload would include source images and derived content sent to OpenAI and additional spend. No such run was executed. The concrete proposed reference payload is saved locally as [source text](../apps/web/e2e/screenshots/extraction-improvement/proposed-source-context.txt) and [numbered image sheet](../apps/web/e2e/screenshots/extraction-improvement/proposed-source-reference.jpg). Recorded spend and holds remain $0.01227614 and $0.203 respectively; the original cumulative $1 limit remains in force. The revised sample demonstrates the corrected extraction and locally reviewed content; it does not establish the live model's performance with the new payload.

## Reproduce

From `apps/web`, with the local API and worker running in offline mode:

```sh
BASE_URL=http://localhost:3008 \
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
SAMPLE="$PWD/../../W02-G01-Math-Understand Addition and Subtraction-P1 1.pptx" \
TOPIC='Understand Addition and Subtraction: Put Together' \
GRADE=1 SUBJECT=Mathematics REVIEW_EXPORTS=true \
OUT="$PWD/e2e/screenshots/root-ppt-review" npm run e2e
```

## Teaching scope and generation optimization update

Implemented server-side teaching relevance checks shared by web and WhatsApp, conservative redirection on classifier failure, a 1,500-token chat response cap, teaching-specific UI copy, native editable bar/line/pie charts with validated data and source captions, compact JSON prompts, relevant upload snippets and owner-scoped structured-result caching (24-hour TTL; shared when Redis is configured).

Validation: the complete offline backend run passed 208 tests and exposed one source-snippet budgeting failure. The fix preserves high-relevance pages before lower-relevance pages when shrinking the prompt. A subsequent focused run passed all 21 teaching-scope, chart, caching and extraction tests, including the formerly failing case. Ruff and frontend TypeScript checks passed. No additional paid AI calls were made. Semantic scope behavior against live providers remains untested; no universal adversarial-proof claim is made.

## Chapter source uploads and teacher-controlled preparation

Added book/notes uploads directly to chapter creation, chapter-specific source selection, complete/parts/daily preparation, previous-class and revision instructions, editable columns/tables/charts/vocabulary/layout/timing, manual image replacement, image-fit selection, detailed after-class notes and visible image-placeholder feedback. Daily mode prepares only lesson 1 automatically and returns the course to planned status when no generation jobs remain.

Validation: all 217 offline backend tests passed. The local browser test passed source upload/selection, day-by-day creation, next-day preparation, manual table persistence, editable PPT download links and 390/1440px layouts. TypeScript and Ruff passed. No paid API calls were made. See CHAPTER_WORKFLOW.md for behavior and current limitations.

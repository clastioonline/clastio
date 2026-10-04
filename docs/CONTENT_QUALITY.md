# Classroom content quality checks

Generation now checks the chapter, lesson and assessment before publishing an output. These checks improve correctness within their defined scope; a teacher still reviews facts, source interpretation and curriculum suitability.

## Checks before publication

- A chapter must contain the requested lecture count, titled lessons, learning objectives and success criteria. Curriculum outcome codes must come from the teacher's supplied outcomes.
- A lesson must contain the requested slide count and exactly one opening cover. Missing slides trigger a repair instead of silently padding a shorter response with generic discussion slides.
- Slide content must contain usable titles, explanations or tasks, vocabulary meanings and required chart data. Lesson-phase and slide timings are normalized to the selected lesson duration.
- A quiz needs four distinct, nonempty options, a valid answer index and a teacher explanation. Invalid indices are never silently changed to the first option. Quiz question and option text are not truncated to fit a design.
- Unambiguous numeric arithmetic questions are checked with a restricted expression parser and exact fractions. Word problems, algebra, rounding questions and ambiguous exercises remain for teacher review; no arbitrary code is evaluated.
- Worksheets and homework must contain the requested question count, distinct questions, answers, explanations and positive marks. The same MCQ stem with different answer-bearing options is allowed. Multiple-choice answers must match an option and pass the quiz checks, including quiz data retained under a different slide layout.

## Repair and credit behavior

Live generation permits one additional whole chapter/deck/assessment response for failed structural checks. Essential slide issues get one checked rewrite per affected slide during pre-render quality checks. Existing visual fit checks remain in place. Teacher-paid AI calls remain subject to the existing admission and spending limits.

If the essential checks still fail, the job stops rather than publishing guessed answers or retrying the entire paid job repeatedly. The job's reserved teacher credits are released. This does not refund provider costs for requests already performed. Failed targeted slide edits preserve the previous slide. Local AI rewrites preserve supplied outcome codes, slide timing, the cover sequence and quiz structure, so a repair cannot hide an invalid answer or invent official alignment.

The lesson page displays a review notice. Its quality report distinguishes structural checks from factual review and records the number of retrieved references. A source-free deck explicitly asks the teacher to add their textbook or syllabus. A retrieved reference is supporting context, not proof that every generated statement is correct.

## Validate teaching quality before increasing marketing

Use a small representative set of UAE teaching briefs: primary mathematics, secondary science, English, Arabic, and the selected British/CBSE/IB/MOE curriculum. Supply material you are permitted to use and review it against the authoritative source. Check factual accuracy, answer keys, age-appropriate wording, objectives, assessment coverage, accessibility, Arabic direction and editable PPT/PDF exports. Include a targeted teacher edit and measure actual provider cost.

Local regression tests use offline AI and mocked live responses, with real editable PPTX and LibreOffice PDF exports. They prove the checks and workflow; they do not establish the accuracy of a production AI model. Track real teacher feedback and failed quality checks before changing model routing or increasing allowances.

Related notes: [UAE template library](UAE_TEMPLATES.md), [Free trials and credit tasks](FREE_TRIAL_AND_CREDIT_TASKS.md), [AI cost controls](AI_COST_CONTROLS.md), and [launch audit](LAUNCH_AUDIT.md).

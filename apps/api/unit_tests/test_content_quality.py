from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.engine.template.builder import BUILTIN_STYLES, build_builtin
from app.generation import offline, pipeline
from app.generation.budgets import compute_budgets
from app.generation.quality import (
    ContentQualityError,
    arithmetic_answer,
    assessment_errors,
    quiz_errors,
    reference_count,
)
from app.generation.specs import AssessmentDoc, CoursePlan, LessonDeck, Question, QuizItem, SlideRewrite


def request():
    return {"topic": "Addition", "grade": "2", "subject": "Mathematics", "curriculum": "british",
            "num_lectures": 1, "slides_per_lecture": 10, "lecture_minutes": 40, "outcomes": []}


def deck():
    req = request()
    course = offline.course_plan(req, CoursePlan)
    return offline.lesson_deck({**req, "lecture": course.lectures[0].model_dump()}, LessonDeck)


def budgets():
    return compute_budgets(build_builtin(next(iter(BUILTIN_STYLES)))[1])


def quiz(**patch):
    return QuizItem(**{"question": "What is 2 + 3?", "options": ["4", "5", "6", "7"],
                       "answer_index": 1, "explanation": "Add two objects and three objects to make five.", **patch})


@pytest.mark.parametrize("question, answer", [("What is 2 + 3?", "5"), ("Calculate (2 + 3) × 4", "20"),
    ("8 ÷ 4 = ?", "2"), ("0.1 + 0.2?", "0.3"), ("-2 + 5?", "3"), ("(1 / 3) * 3?", "1")])
def test_exact_arithmetic_with_decimal_values_and_parentheses(question, answer):
    assert arithmetic_answer(question) == Decimal(answer)


@pytest.mark.parametrize("question", ["Is 2 + 3 = 7 incorrect?", "What is x + 3?", "Spot the error: 2 + 3 = 7",
    "What is 1 / 3?", "1 / 0?", "2 ** 1000000", "__import__('os').system('true')", "How many apples in 2 baskets?"])
def test_ambiguous_rounded_and_non_numeric_questions_are_not_guessed(question):
    assert arithmetic_answer(question) is None


def test_quiz_checks_answer_index_distinct_options_and_simple_math():
    assert not quiz_errors(quiz())
    assert quiz_errors(quiz(answer_index=9))
    assert quiz_errors(quiz(answer_index=0))
    assert quiz_errors(quiz(options=["5", " 5 ", "6", "7"]))
    assert quiz_errors(quiz(explanation=""))


def test_malformed_source_fields_cannot_crash_or_count_as_references():
    file_id = "12345678-1234-4234-8234-123456789012"
    assert reference_count([{"file_id": file_id, "page": 1}, {"file_id": file_id, "page": 1}]) == 1
    assert reference_count([{"file_id": file_id, "page": [1, 2]}, {"file_id": [file_id]},
                            {"file_id": "invented"}, {"file_id": file_id, "page": True}]) == 0


def test_normalization_preserves_bad_answer_for_validation_instead_of_guessing():
    lesson = deck()
    slide = next(slide for slide in lesson.slides if slide.layout == "quiz")
    slide.quiz = quiz(options=["", "4", "5", "6"], answer_index=9)
    pipeline.normalize_deck(lesson, req=request(), lecture_number=1, total=1, lecture_title="Addition")
    assert slide.quiz.answer_index == 9
    assert slide.quiz.options == ["", "4", "5", "6"]
    assert pipeline.slide_quality_issues(slide)


def test_quiz_answer_text_is_not_changed_to_fit_the_template():
    lesson = deck()
    slide = next(slide for slide in lesson.slides if slide.layout == "quiz")
    slide.quiz = quiz(options=["one two three four five six seven eight", "5", "6", "7"])
    original = slide.quiz.model_dump()
    limit = budgets()
    limit["quiz_question_max_words"] = 2
    limit["quiz_option_max_words"] = 2
    pipeline.enforce_budgets(slide, limit, strict=True)
    assert slide.quiz.model_dump() == original


async def test_failed_quiz_repair_cannot_publish_or_be_downgraded_to_discussion():
    lesson = deck()
    slide = next(slide for slide in lesson.slides if slide.layout == "quiz")
    slide.quiz = quiz(answer_index=0)
    ai = SimpleNamespace(mode="live", structured=AsyncMock(return_value=SlideRewrite(slide=slide)))
    # Remove cosmetic duplicate/style issues so this is precisely one bounded quiz repair.
    for index, item in enumerate(lesson.slides):
        item.title = f"Slide {index + 1}"
    with pytest.raises(ContentQualityError):
        await pipeline.pre_render_qc(ai, lesson, budgets(), context_text="", grade="2")
    assert ai.structured.await_count == 1
    assert slide.layout == "quiz"


async def test_correct_quiz_repair_is_validated_then_published():
    lesson = deck()
    slide = next(slide for slide in lesson.slides if slide.layout == "quiz")
    slide.quiz = quiz(answer_index=0)
    repaired = slide.model_copy(deep=True)
    repaired.quiz = quiz()
    ai = SimpleNamespace(mode="live", structured=AsyncMock(return_value=SlideRewrite(slide=repaired)))
    for index, item in enumerate(lesson.slides):
        item.title = f"Slide {index + 1}"
    await pipeline.pre_render_qc(ai, lesson, budgets(), context_text="", grade="2")
    assert not quiz_errors(next(item for item in lesson.slides if item.layout == "quiz").quiz)


@pytest.mark.parametrize("original_index, changed_layout", [(0, "concept"), (3, "cover")])
async def test_rewrite_preserves_cover_sequence_supplied_codes_and_timing(original_index, changed_layout):
    original = deck().slides[original_index]
    original.outcome_codes = ["SUPPLIED-CODE"]
    revised = original.model_copy(deep=True)
    revised.layout, revised.outcome_codes, revised.timing_minutes = changed_layout, ["INVENTED-CODE"], 999
    ai = SimpleNamespace(mode="live", structured=AsyncMock(return_value=SlideRewrite(slide=revised)))
    result = await pipeline.repair_slide(ai, original, "Improve wording", budgets(), context_text="", grade="2")
    assert result.layout == original.layout
    assert result.outcome_codes == ["SUPPLIED-CODE"]
    assert result.timing_minutes == original.timing_minutes


async def test_quiz_rewrite_cannot_hide_a_bad_answer_by_changing_layout():
    original = next(slide for slide in deck().slides if slide.layout == "quiz")
    revised = original.model_copy(deep=True)
    revised.layout, revised.quiz = "discussion", quiz(answer_index=0)
    ai = SimpleNamespace(mode="live", structured=AsyncMock(return_value=SlideRewrite(slide=revised)))
    with pytest.raises(ContentQualityError):
        await pipeline.repair_slide(ai, original, "Fix quiz", budgets(), context_text="", grade="2")
    assert original.layout == "quiz"


def test_hidden_quiz_is_checked_and_extra_cover_cannot_publish():
    lesson = deck()
    lesson.slides[3].quiz = quiz(answer_index=0)
    with pytest.raises(ContentQualityError):
        pipeline.assert_publishable(lesson)
    lesson.slides[3].quiz = None
    lesson.slides[3].layout = "cover"
    with pytest.raises(ContentQualityError):
        pipeline.assert_publishable(lesson)


async def test_missing_slide_count_gets_one_full_repair_without_filler():
    req, valid = request(), deck()
    incomplete = valid.model_copy(deep=True)
    incomplete.slides.pop()
    ai = SimpleNamespace(mode="live", structured=AsyncMock(side_effect=[outline(req), incomplete, valid]))
    course = offline.course_plan(req, CoursePlan)
    generated = await pipeline.generate_deck(ai, req=req, context_text="", course=course, lecture_number=1, budgets=budgets())
    assert len(generated.slides) == 10
    assert ai.structured.await_count == 3
    assert all(slide.title != "Talk it through" for slide in generated.slides)
    assert sum(phase.minutes for phase in generated.lesson_plan.phases) == 40


async def test_bad_slide_count_after_one_repair_fails_permanently():
    req, invalid = request(), deck()
    invalid.slides.pop()
    ai = SimpleNamespace(mode="live", structured=AsyncMock(side_effect=[outline(req), invalid, invalid]))
    with pytest.raises(ContentQualityError):
        await pipeline.generate_deck(ai, req=req, context_text="", course=offline.course_plan(req, CoursePlan), lecture_number=1, budgets=budgets())
    assert ai.structured.await_count == 3


def test_unknown_curriculum_codes_are_not_presented_as_alignment():
    plan = offline.course_plan(request(), CoursePlan)
    plan.learning_outcomes[0].code = "MADE-UP-OFFICIAL-CODE"
    assert pipeline.course_structure_issues(plan, request())
    lesson = deck()
    lesson.slides[0].outcome_codes = ["MADE-UP-OFFICIAL-CODE"]
    assert pipeline.deck_structure_issues(lesson, request())


def test_assessment_rejects_missing_questions_duplicate_options_and_wrong_answer_key():
    question = Question(qtype="mcq", difficulty="easy", bloom="apply", stem="What is 2 + 3?",
                        options=["4", "5", "6", "7"], answer="5", explanation="Two plus three is five.")
    assessment = AssessmentDoc(title="Addition", instructions="Answer.", sections=[{"title": "Check", "instructions": "", "questions": [question]}])
    assert not assessment_errors(assessment, 1)
    assert assessment_errors(assessment, 2)
    question.answer = "4"
    assert assessment_errors(assessment, 1)
    question.answer = "none"
    assert assessment_errors(assessment, 1)


def test_assessment_allows_shared_stems_with_distinct_answer_bearing_choices():
    first = Question(qtype="mcq", difficulty="easy", bloom="apply", stem="Which word is an adjective?",
                     options=["red", "run", "cat", "quickly"], answer="red", explanation="Red describes a noun.")
    second = first.model_copy(update={"options": ["tall", "swim", "dog", "slowly"], "answer": "tall",
                                      "explanation": "Tall describes a noun."})
    assessment = AssessmentDoc(title="Adjectives", instructions="Choose.",
        sections=[{"title": "Check", "instructions": "", "questions": [first, second]}])
    assert not assessment_errors(assessment, 2)
    assessment.sections[0].questions[1] = first.model_copy(deep=True)
    assert assessment_errors(assessment, 2)


@pytest.mark.parametrize("slides", [10, 20, 30, 40])
def test_offline_demo_has_exact_slide_count_without_pipeline_padding(slides):
    req = {**request(), "slides_per_lecture": slides}
    plan = offline.course_plan(req, CoursePlan)
    sample = offline.lesson_deck({**req, "lecture": plan.lectures[0].model_dump()}, LessonDeck)
    assert not pipeline.deck_structure_issues(sample, req)
    pipeline.assert_publishable(sample)


def test_offline_assessment_and_homework_obey_requested_question_count():
    from app.generation.specs import HomeworkDoc

    for schema in (AssessmentDoc, HomeworkDoc):
        sample = offline.assessment({"topic": "Addition", "num_questions": 10}, schema)
        assert not assessment_errors(sample, 10)


def outline(req):
    return pipeline.DeckOutline(slides=[pipeline.PlannedSlide(number=n, title=f"Slide {n}",
        layout="cover" if n == 1 else "concept", purpose="Teach the objective",
        teaching_content="Explain an example", minutes=req["lecture_minutes"] / req["slides_per_lecture"])
        for n in range(1, req["slides_per_lecture"] + 1)])

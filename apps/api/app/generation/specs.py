"""Typed intermediate representations for the generation pipeline.

REQUEST -> CoursePlan -> (per lecture) LessonPlan + SlideSpec[] -> QC -> PPTX
Everything here is validated with Pydantic and stored as JSON, so any stage can be re-run alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SlideLayout = Literal[
    "cover", "section", "objectives", "concept", "image_text", "two_column", "comparison", "process",
    "cycle", "timeline", "table", "key_vocabulary", "quiz", "discussion", "activity", "worked_example",
    "summary", "exit_ticket", "homework",
]
LAYOUT_KINDS: tuple[str, ...] = SlideLayout.__args__  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- course plan


class Outcome(BaseModel):
    code: str | None = None
    text: str


class LecturePlan(BaseModel):
    number: int
    title: str
    objectives: list[str]
    success_criteria: list[str]
    key_concepts: list[str] = Field(description="Concepts INTRODUCED in this lecture (not repeated elsewhere)")
    revisits: list[str] = Field(default_factory=list, description="Earlier concepts retrieved/practised")
    key_vocabulary: list[str]
    activity_idea: str
    assessment_idea: str
    homework_idea: str


class CoursePlan(BaseModel):
    title: str
    overview: str
    big_idea: str
    learning_outcomes: list[Outcome]
    prerequisites: list[str]
    diagnostic_questions: list[str]
    lectures: list[LecturePlan]
    revision_strategy: str
    assessment_strategy: str
    cross_curricular_links: list[str]
    local_context_links: list[str] = Field(default_factory=list, description="e.g. UAE/India context, national identity, moral education links")


# --------------------------------------------------------------------------- lesson plan


class LessonPhase(BaseModel):
    name: Literal["starter", "main", "activity", "plenary"]
    minutes: int
    description: str
    teacher_actions: str
    student_actions: str


class QuestionToAsk(BaseModel):
    question: str
    bloom_level: Literal["remember", "understand", "apply", "analyse", "evaluate", "create"]
    expected_response: str


class Misconception(BaseModel):
    misconception: str
    correction: str


class Differentiation(BaseModel):
    support: str
    core: str
    extension: str
    eal: str = Field(description="English-as-additional-language scaffolds")
    send: str = Field(description="Adaptations for students of determination")


class Homework(BaseModel):
    task: str
    estimated_minutes: int


class LessonPlan(BaseModel):
    lecture_number: int
    title: str
    duration_minutes: int
    objectives: list[str]
    success_criteria: list[str]
    phases: list[LessonPhase]
    questions_to_ask: list[QuestionToAsk]
    misconceptions: list[Misconception]
    differentiation: Differentiation
    resources: list[str]
    safety_notes: str | None = None
    homework: Homework
    exit_ticket: list[str]


# --------------------------------------------------------------------------- slides


class Bullet(BaseModel):
    text: str
    level: int = 0

    @field_validator("level")
    @classmethod
    def _clamp(cls, v: int) -> int:
        return max(0, min(2, v))


class Column(BaseModel):
    heading: str
    bullets: list[str]


class Step(BaseModel):
    label: str
    detail: str


class TableData(BaseModel):
    headers: list[str]
    rows: list[list[str]]


class Term(BaseModel):
    term: str
    meaning: str
    translation: str | None = None


class QuizItem(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class Visual(BaseModel):
    kind: Literal["none", "image", "diagram"] = "none"
    description: str = ""
    image_query: str = Field("", description="2-5 plain keywords for a stock photo search")
    alt_text: str = ""


class SlideDifferentiation(BaseModel):
    support: str | None = None
    extension: str | None = None


class SlideSpec(BaseModel):
    number: int
    layout: SlideLayout
    purpose: str
    title: str
    subtitle: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    table: TableData | None = None
    terms: list[Term] = Field(default_factory=list)
    quiz: QuizItem | None = None
    question: str | None = None
    visual: Visual = Field(default_factory=Visual)
    speaker_notes: str = ""
    teacher_instruction: str | None = None
    question_to_ask: str | None = None
    timing_minutes: float = 3
    outcome_codes: list[str] = Field(default_factory=list)
    differentiation: SlideDifferentiation = Field(default_factory=SlideDifferentiation)
    language: str = "en"
    # Filled by the pipeline (not by the model)
    asset_id: str | None = None
    sources: list[dict] = Field(default_factory=list)


class LessonDeck(BaseModel):
    """One AI call per lecture returns the lesson plan and its slides together (cheaper, coherent)."""

    lesson_plan: LessonPlan
    slides: list[SlideSpec]


class SlideRewrite(BaseModel):
    slide: SlideSpec


# --------------------------------------------------------------------------- assessments


class Question(BaseModel):
    qtype: Literal["mcq", "true_false", "short_answer", "long_answer", "fill_blank", "matching", "application",
                   "case_based"]
    difficulty: Literal["easy", "medium", "hard"]
    bloom: Literal["remember", "understand", "apply", "analyse", "evaluate", "create"]
    stem: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str
    marks: int = 1


class QuestionSection(BaseModel):
    title: str
    instructions: str
    questions: list[Question]


class AssessmentDoc(BaseModel):
    title: str
    instructions: str
    sections: list[QuestionSection]
    case_study: str | None = None
    rubric: list[str] = Field(default_factory=list)


class HomeworkDoc(BaseModel):
    title: str
    instructions: str
    tasks: list[str]
    estimated_minutes: int
    questions: list[Question]
    extension_task: str | None = None
    support_hint: str | None = None

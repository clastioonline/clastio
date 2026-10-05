"""Typed intermediate representations for the generation pipeline.

REQUEST -> CoursePlan -> (per lecture) LessonPlan + SlideSpec[] -> QC -> PPTX
Everything here is validated with Pydantic and stored as JSON, so any stage can be re-run alone.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SlideLayout = Literal[
    "cover", "section", "objectives", "concept", "image_text", "two_column", "comparison", "process",
    "cycle", "timeline", "table", "chart", "key_vocabulary", "quiz", "discussion", "activity", "worked_example",
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


class ChartSeries(BaseModel):
    name: str
    values: list[float] = Field(min_length=1, max_length=12)


    @field_validator("values")
    @classmethod
    def finite_values(cls, values):
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Chart values must be finite")
        return values


class ChartData(BaseModel):
    kind: Literal["bar", "line", "pie"] = "bar"
    categories: list[str] = Field(min_length=1, max_length=12)
    series: list[ChartSeries] = Field(min_length=1, max_length=4)
    unit: str = ""
    source: str = Field(min_length=1, description="Source of the data; label classroom/example data explicitly")

    @field_validator("series")
    @classmethod
    def matching_lengths(cls, value, info):
        categories = info.data.get("categories", [])
        if any(len(s.values) != len(categories) for s in value):
            raise ValueError("Each series must match the categories")
        if info.data.get("kind") == "pie":
            if len(value) != 1 or any(v < 0 for v in value[0].values) or sum(value[0].values) <= 0:
                raise ValueError("Pie charts require one nonnegative series with a positive total")
        return value


class Term(BaseModel):
    term: str
    meaning: str
    translation: str | None = None


class QuizItem(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class CountingGroup(BaseModel):
    count: int = Field(ge=0, le=20)
    label: str
    color: Literal["red", "green", "blue", "black", "white"]


class Visual(BaseModel):
    kind: Literal["none", "image", "diagram"] = "none"
    description: str = ""
    image_query: str = Field("", description="2-5 plain keywords for a stock photo search")
    alt_text: str = ""
    fit: Literal["contain", "cover"] = "contain"
    source_image_key: str | None = Field(None, description="Exact image_key from the template or teacher-supplied image catalog; null for a new visual")
    counting_groups: list[CountingGroup] = Field(default_factory=list,
        description="Two parts for an exact, editable counting diagram; use for early addition instead of a stock image")
    show_total: bool = True


class SlideDifferentiation(BaseModel):
    support: str | None = None
    extension: str | None = None


class ManualObjectEdit(BaseModel):
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    width: float | None = Field(default=None, gt=0, le=1)
    height: float | None = Field(default=None, gt=0, le=1)
    text: str | None = Field(default=None, max_length=10000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    font_size: float | None = Field(default=None, ge=8, le=120)
    font_family: str | None = Field(default=None, min_length=1, max_length=100)
    bold: bool | None = None


class SlideSpec(BaseModel):
    number: int
    layout: SlideLayout
    purpose: str
    title: str
    teaching_stage: Literal["topic", "engage", "objective", "explore", "explain", "elaborate", "evaluate", "self_reflect"] | None = None
    subtitle: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    table: TableData | None = None
    chart: ChartData | None = None
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
    manual_objects: dict[str, ManualObjectEdit] = Field(default_factory=dict, max_length=150)


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

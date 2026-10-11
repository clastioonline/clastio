"""Phase 1 contracts for inspection-aligned drafts; regulators do not approve AI output."""
from __future__ import annotations

import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.generation.specs import LessonDeck

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
TitleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
SubjectText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
GradeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
CurriculumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
LanguageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
EducationStage = Literal['early_years', 'primary', 'secondary', 'university']
Framework = Literal['khda', 'adek', 'moe', 'other', 'not_specified']


class StrictContent(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class TeacherPlanningPreferences(StrictContent):
    inclusion_notes: str = Field(default='', max_length=2000,
        description='Aggregate classroom barriers and support; never individual student identifiers or diagnoses.')
    ell_scaffolds: list[Text] = Field(default_factory=list, max_length=12)
    sen_scaffolds: list[Text] = Field(default_factory=list, max_length=12)
    preferred_assessment_tools: list[Text] = Field(default_factory=list, max_length=12)
    planning_format: str = Field(default='', max_length=1000)
    use_uae_context: bool = True


class LearningObjective(StrictContent):
    id: Identifier
    description: Text
    observable_action: Literal['identify', 'describe', 'explain', 'compare', 'classify', 'calculate',
        'construct', 'justify', 'evaluate', 'design', 'demonstrate', 'analyse', 'apply', 'solve',
        'create', 'observe', 'predict', 'present', 'model', 'write', 'summarise', 'investigate']
    success_measure: Text
    bloom_level: Literal['remember', 'understand', 'apply', 'analyse', 'evaluate', 'create']


class SuccessCriterion(StrictContent):
    id: Identifier
    objective_ids: list[Identifier] = Field(min_length=1, max_length=12)
    description: Text
    observable_evidence: Text


class ContextConnection(StrictContent):
    relevant: bool
    connection_or_reason: Text
    classroom_application: Text


class UAEContext(StrictContent):
    national_identity: ContextConnection
    moral_education: ContextConnection
    arabic_culture: ContextConnection


class CrossCurricularLink(StrictContent):
    subject: SubjectText
    activity: Text
    evidence_of_learning: Text


class InclusionStrategy(StrictContent):
    learning_barrier: Text
    scaffold: Text
    assessment_accommodation: Text


class PlanningDifferentiation(StrictContent):
    sen: list[InclusionStrategy] = Field(min_length=1, max_length=8,
        description='Strategies for additional learning needs/students of determination; no individual diagnoses or names.')
    ell: list[InclusionStrategy] = Field(min_length=1, max_length=8,
        description='Concrete ELL/EAL language scaffolds such as vocabulary, sentence frames and visual support.')
    core: Text
    extension: Text


class FormativeAssessment(StrictContent):
    id: Identifier
    objective_ids: list[Identifier] = Field(min_length=1, max_length=12)
    tool: Text
    question_or_task: Text
    expected_response: Text
    evidence_to_record: Text
    teaching_response: Text


class PlanningPhase(StrictContent):
    name: Text
    duration_minutes: float = Field(gt=0, le=180)
    objective_ids: list[Identifier] = Field(min_length=1, max_length=12)
    teacher_actions: Text
    student_actions: Text
    assessment_ids: list[Identifier] = Field(max_length=12)


class SourceReference(StrictContent):
    title: TitleText
    url_or_file_id: Text
    page_or_section: Text
    relevance: Text

    @field_validator('url_or_file_id')
    @classmethod
    def reference_syntax(cls, value):
        try:
            UUID(value)
            return value
        except ValueError:
            url = HttpUrl(value)
            if url.scheme != 'https' or url.username or url.password:
                raise ValueError('Source references need an HTTPS URL or an uploaded-file UUID.') from None
            return str(url)


class PlannerReview(StrictContent):
    alignment_status: Literal['teacher_review_required']
    framework_references: list[SourceReference] = Field(max_length=20)
    evidence_gaps: list[Text] = Field(max_length=20)
    teacher_checks: list[Text] = Field(min_length=1, max_length=20)


class UAEPlanContent(StrictContent):
    schema_version: Literal[1]
    title: TitleText
    topic: TitleText
    subject: SubjectText
    grade: GradeText
    curriculum: CurriculumText
    language: LanguageText
    education_stage: EducationStage
    framework: Framework
    duration_minutes: int = Field(ge=5, le=180)
    learning_objectives: list[LearningObjective] = Field(min_length=1, max_length=12)
    success_criteria: list[SuccessCriterion] = Field(min_length=1, max_length=24)
    cross_curricular_links: list[CrossCurricularLink] = Field(min_length=1, max_length=12)
    uae_context: UAEContext
    differentiation: PlanningDifferentiation
    formative_assessment: list[FormativeAssessment] = Field(min_length=1, max_length=24)
    lesson_sequence: list[PlanningPhase] = Field(min_length=1, max_length=16)
    prerequisites: list[Text] = Field(max_length=12)
    homework: Text
    resources: list[Text] = Field(max_length=24)
    source_references: list[SourceReference] = Field(max_length=24)
    review_checks: PlannerReview

    @model_validator(mode='after')
    def backward_design_alignment(self):
        objectives = {item.id for item in self.learning_objectives}
        assessments = {item.id for item in self.formative_assessment}
        if len(objectives) != len(self.learning_objectives) or len(assessments) != len(self.formative_assessment):
            raise ValueError('Objective and assessment identifiers must be unique.')
        if len({item.id for item in self.success_criteria}) != len(self.success_criteria):
            raise ValueError('Success criterion identifiers must be unique.')
        for label, items in [('success criteria', self.success_criteria), ('assessments', self.formative_assessment),
                             ('lesson phases', self.lesson_sequence)]:
            linked = {identifier for item in items for identifier in item.objective_ids}
            if linked - objectives:
                raise ValueError(f'{label} contain an unknown objective identifier.')
            if objectives - linked:
                raise ValueError(f'Every objective needs linked {label}.')
        assessment_targets = {assessment.id: set(assessment.objective_ids) for assessment in self.formative_assessment}
        if any(set(phase.assessment_ids) - assessments for phase in self.lesson_sequence):
            raise ValueError('Lesson phases contain an unknown assessment identifier.')
        if any(not assessment_targets[identifier].issubset(set(phase.objective_ids))
               for phase in self.lesson_sequence for identifier in phase.assessment_ids):
            raise ValueError('Each phase assessment must measure that phase’s stated objectives.')
        if assessments - {identifier for phase in self.lesson_sequence for identifier in phase.assessment_ids}:
            raise ValueError('Every formative assessment must appear in the lesson sequence.')
        if not math.isclose(sum(phase.duration_minutes for phase in self.lesson_sequence), self.duration_minutes, abs_tol=.01):
            raise ValueError('Lesson phases must total the requested lesson duration.')
        if self.education_stage == 'university' and self.framework in {'khda', 'adek', 'moe'}:
            raise ValueError('School inspection alignment cannot be claimed for a university lesson.')
        return self


class DemoHook(StrictContent):
    teacher_says: Text
    learner_interaction: Text
    materials: list[Text] = Field(max_length=10)


class DemoScriptStep(StrictContent):
    order: int = Field(ge=1, le=30)
    start_seconds: int = Field(ge=0, lt=900)
    end_seconds: int = Field(gt=0, le=900)
    slide_numbers: list[int] = Field(min_length=1, max_length=12)
    teacher_says: Text
    teacher_does: Text
    expected_student_response: Text
    formative_check: Text
    transition: Text


class DemoClassContent(StrictContent):
    lesson_plan: UAEPlanContent
    hook: DemoHook
    teacher_script: list[DemoScriptStep] = Field(min_length=3, max_length=30)
    slide_payload: LessonDeck

    @model_validator(mode='after')
    def complete_micro_lesson(self):
        if self.lesson_plan.duration_minutes != 15:
            raise ValueError('A demo micro-lesson must last exactly 15 minutes.')
        if self.slide_payload.lesson_plan.duration_minutes != 15 or self.slide_payload.lesson_plan.title.strip().casefold() != self.lesson_plan.title.strip().casefold():
            raise ValueError('The PPT and teacher script must use the same lesson title and 15-minute plan.')
        approved = {objective.description.casefold() for objective in self.lesson_plan.learning_objectives}
        rendered = {objective.strip().casefold() for objective in self.slide_payload.lesson_plan.objectives}
        if not approved.issubset(rendered):
            raise ValueError('The PPT must preserve every approved demo learning objective.')
        approved_criteria = {criterion.description.casefold() for criterion in self.lesson_plan.success_criteria}
        rendered_criteria = {criterion.strip().casefold() for criterion in self.slide_payload.lesson_plan.success_criteria}
        if not approved_criteria.issubset(rendered_criteria):
            raise ValueError('The PPT must preserve the approved demo success criteria.')
        cursor = 0
        numbers = {slide.number for slide in self.slide_payload.slides}
        if [slide.number for slide in self.slide_payload.slides] != list(range(1, len(numbers)+1)):
            raise ValueError('Demo slides must be numbered consecutively.')
        if not numbers or len(numbers) > 12:
            raise ValueError('Use 1–12 purposeful demo slides.')
        assigned_seconds = {number: 0.0 for number in numbers}
        for order, step in enumerate(self.teacher_script, 1):
            if step.order != order or step.start_seconds != cursor or step.end_seconds <= cursor:
                raise ValueError('The teacher script must be ordered, continuous and positive in duration.')
            if set(step.slide_numbers) - numbers:
                raise ValueError('The teacher script references a missing slide.')
            if len(set(step.slide_numbers)) != len(step.slide_numbers):
                raise ValueError('A script step cannot list the same slide twice.')
            for number in step.slide_numbers:
                assigned_seconds[number] += (step.end_seconds-step.start_seconds)/len(step.slide_numbers)
            cursor = step.end_seconds
        if cursor != 900:
            raise ValueError('The teacher script must cover all 900 seconds.')
        if numbers - {number for step in self.teacher_script for number in step.slide_numbers}:
            raise ValueError('Every demo slide must be mapped to the teacher script.')
        if any(slide.timing_minutes <= 0 for slide in self.slide_payload.slides) or not math.isclose(
            sum(slide.timing_minutes for slide in self.slide_payload.slides), 15, abs_tol=.01):
            raise ValueError('Demo slide timings must total 15 minutes.')
        if any(not math.isclose(slide.timing_minutes*60, assigned_seconds[slide.number], abs_tol=.6)
               for slide in self.slide_payload.slides):
            raise ValueError('Demo slide timing must be derived from its teacher-script steps.')
        if sum(phase.minutes for phase in self.slide_payload.lesson_plan.phases) != 15:
            raise ValueError('The PPT lesson-plan phases must also total 15 minutes.')
        return self


class ResourceChapter(StrictContent):
    number: int = Field(ge=1, le=12)
    title: TitleText
    learning_goals: list[Text] = Field(min_length=1, max_length=12)
    explanation: Text
    definitions: list[Text] = Field(min_length=1, max_length=24)
    worked_examples: list[Text] = Field(min_length=1, max_length=12)
    uae_case_study: Text
    summary: Text
    practice_questions: list[Text] = Field(min_length=1, max_length=12)
    expected_answers: list[Text] = Field(min_length=1, max_length=12)
    source_references: list[SourceReference] = Field(max_length=24)

    @model_validator(mode='after')
    def questions_have_answers(self):
        if len(self.practice_questions) != len(self.expected_answers):
            raise ValueError('Every practice question needs an expected answer.')
        return self


class GeneratedResourceContent(StrictContent):
    schema_version: Literal[1]
    title: TitleText
    topic: TitleText
    subject: SubjectText
    education_stage: EducationStage
    grade: str | None = Field(default=None, max_length=30)
    curriculum: CurriculumText
    language: LanguageText
    kind: Literal['subject_primer', 'study_guide']
    origin: Literal['generated']
    overview: Text
    chapters: list[ResourceChapter] = Field(min_length=1, max_length=12)
    source_references: list[SourceReference] = Field(max_length=24)
    review_checks: PlannerReview

    @model_validator(mode='after')
    def chapter_sequence(self):
        if [chapter.number for chapter in self.chapters] != list(range(1, len(self.chapters)+1)):
            raise ValueError('Resource chapters must be numbered consecutively.')
        if self.education_stage != 'university' and not (self.grade or '').strip():
            raise ValueError('School resources need a grade or year.')
        return self

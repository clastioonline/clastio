"""Owner-scoped educator drafts, bounded AI workflows and reusable study resources."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import Field, StrictInt, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import get_ai
from app.core.db import get_sessionmaker, utcnow
from app.core.errors import AppError, NotFound
from app.core.storage import get_storage
from app.generation.educator_prompts import (
    DEMO_SCRIPT_SYSTEM,
    PLAN_SYSTEM,
    RESOURCE_CHAPTER_SYSTEM,
    RESOURCE_OUTLINE_SYSTEM,
)
from app.generation.educator_specs import (
    CurriculumText,
    DemoClassContent,
    DemoHook,
    DemoScriptStep,
    EducationStage,
    Framework,
    GeneratedResourceContent,
    GradeText,
    LanguageText,
    PlannerReview,
    ResourceChapter,
    SourceReference,
    StrictContent,
    SubjectText,
    TeacherPlanningPreferences,
    Text,
    TitleText,
    UAEPlanContent,
)
from app.generation.quality import ContentQualityError
from app.jobs.queue import (
    JobContext,
    PermanentJobError,
    enqueue,
    handler,
    on_failure,
    run_inline_if_configured,
)
from app.models import (
    ClassSection,
    Course,
    DemoClass,
    DigitalResource,
    GenerationJob,
    Lesson,
    LessonPlan,
    Project,
    SourceChunk,
    TeacherProfile,
    UploadedFile,
    User,
)
from app.services import usage
from app.services.context import build_context

PROMPT_VERSION = 'educator-v1.1'
SOURCE_BYTES = 24000
PLAN_FIELDS = tuple(UAEPlanContent.model_fields)
OFFICIAL_REFERENCES = {
    'khda': [
        {'title': 'UAE School Inspection Framework 2015–16',
         'url_or_file_id': 'https://web.khda.gov.ae/en/Resources/Publications/School-Inspection/UAE-School-Inspection-Framework-2015-16',
         'page_or_section': 'Teaching, assessment and learning', 'relevance': 'School planning reference; not approval of this draft.'},
        {'title': 'Dubai inclusive education policy framework',
         'url_or_file_id': 'https://web.khda.gov.ae/en/Resources/Publications/School-Inspection/Dubai-inclusive-education-policy-framework',
         'page_or_section': 'Inclusive education', 'relevance': 'Classroom participation and access to learning.'},
        {'title': 'KHDA legislation and current education requirements',
         'url_or_file_id': 'https://web.khda.gov.ae/en/About-Us/Legislation',
         'page_or_section': 'Inclusive education requirements and administrative resolutions',
         'relevance': 'Check the currently applicable requirements alongside published framework guidance.'},
    ],
    'adek': [
        {'title': 'ADEK Teaching and Learning policies',
         'url_or_file_id': 'https://www.adek.gov.ae/Education-System/Education-Policies/School-Policies-Teaching-and-Learning',
         'page_or_section': 'Curriculum, assessment, inclusion and cultural consideration',
         'relevance': 'Policy collection; the teacher checks the applicable policy version and school requirements.'},
    ],
}
PLANNER_SYSTEM = PLAN_SYSTEM


class SourceRequest(StrictContent):
    source_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    source_page_ranges: dict[str, list[StrictInt]] = Field(default_factory=dict, max_length=5)

    @model_validator(mode='after')
    def selected_pages(self):
        selected = {str(identifier) for identifier in self.source_file_ids}
        if len(selected) != len(self.source_file_ids):
            raise ValueError('Choose each source once.')
        for identifier, pages in self.source_page_ranges.items():
            if identifier not in selected or len(pages) != 2 or any(type(page) is not int for page in pages):
                raise ValueError('Chapter ranges need two PDF page numbers for a selected source.')
            if not 1 <= pages[0] <= pages[1] or pages[1]-pages[0]+1 > 80:
                raise ValueError('Select an ordered chapter range of at most 80 PDF pages.')
        return self


class PlanRequest(SourceRequest):
    topic: TitleText
    subject: SubjectText
    grade: GradeText
    curriculum: CurriculumText
    language: LanguageText = 'en'
    education_stage: EducationStage = 'secondary'
    framework: Framework = 'not_specified'
    duration_minutes: int = Field(default=45, ge=5, le=180)
    instructions: str = Field(default='', max_length=6000)
    prerequisites: str = Field(default='', max_length=2000)
    class_section_id: uuid.UUID | None = None

    @model_validator(mode='after')
    def stage_framework(self):
        if self.education_stage == 'university' and self.framework in {'khda', 'adek', 'moe'}:
            raise ValueError('Choose Other or Not specified for university planning.')
        return self


class DemoRequest(PlanRequest):
    grade: str = Field(min_length=1, max_length=20)
    duration_minutes: Literal[15] = 15
    template_id: uuid.UUID | None = None
    lesson_plan_id: uuid.UUID | None = None


class ResourceRequest(SourceRequest):
    topic: TitleText
    subject: SubjectText
    grade: GradeText | None = None
    curriculum: CurriculumText
    language: LanguageText = 'en'
    education_stage: EducationStage = 'secondary'
    kind: Literal['subject_primer', 'study_guide'] = 'subject_primer'
    chapter_count: int = Field(default=4, ge=1, le=6)
    instructions: str = Field(default='', max_length=6000)

    @model_validator(mode='after')
    def school_grade(self):
        if self.education_stage != 'university' and not self.grade:
            raise ValueError('Select a grade or year for school resources.')
        return self


class ChapterOutline(StrictContent):
    number: int = Field(ge=1, le=6)
    title: TitleText
    learning_goals: list[Text] = Field(min_length=1, max_length=6)
    scope: Text


class ResourceOutline(StrictContent):
    title: TitleText
    overview: Text
    chapters: list[ChapterOutline] = Field(min_length=1, max_length=6)
    review_checks: PlannerReview


class DemoSlideBrief(StrictContent):
    number: int = Field(ge=1, le=8)
    title: TitleText
    purpose: Text
    layout: Literal['cover', 'objectives', 'concept', 'image_text', 'worked_example', 'activity', 'quiz', 'summary', 'exit_ticket']
    content: list[Text] = Field(min_length=1, max_length=6)
    student_task: Text
    expected_answer: Text
    visual_brief: Text
    source_references: list[SourceReference] = Field(default_factory=list, max_length=8)


class DemoScriptContent(StrictContent):
    hook: DemoHook
    teacher_script: list[DemoScriptStep] = Field(min_length=3, max_length=16)
    slides: list[DemoSlideBrief] = Field(min_length=3, max_length=8)

    @model_validator(mode='after')
    def complete_script(self):
        numbers = [slide.number for slide in self.slides]
        if numbers != list(range(1, len(numbers)+1)):
            raise ValueError('Demo slide briefs must be numbered consecutively.')
        if self.slides[0].layout != 'cover' or sum(slide.layout == 'cover' for slide in self.slides) != 1:
            raise ValueError('A demo uses exactly one opening cover for the interactive hook.')
        cursor = 0
        mapped = set()
        for order, step in enumerate(self.teacher_script, 1):
            if step.order != order or step.start_seconds != cursor or step.end_seconds <= cursor:
                raise ValueError('Script steps must be consecutive, positive and continuous from zero.')
            if set(step.slide_numbers)-set(numbers) or len(step.slide_numbers) != len(set(step.slide_numbers)):
                raise ValueError('Script steps reference unique existing slide numbers.')
            cursor = step.end_seconds
            mapped.update(step.slide_numbers)
        if cursor != 900 or mapped != set(numbers):
            raise ValueError('The script must cover 900 seconds and every slide.')
        return self


async def owned(db: AsyncSession, model, identifier, owner_id, *, for_update=False):
    row = await db.get(model, identifier, with_for_update=True) if for_update else await db.get(model, identifier)
    if row is None or row.owner_id != owner_id:
        raise NotFound(model.__name__)
    return row


async def validate_sources(db: AsyncSession, user: User, request: SourceRequest) -> list[UploadedFile]:
    books = []
    for identifier in request.source_file_ids:
        book = await owned(db, UploadedFile, identifier, user.id)
        if book.kind != 'source':
            raise AppError('invalid_source', 'Select a saved book or notes file.', 400)
        if book.status != 'ready':
            raise AppError('source_not_ready', f'{book.filename} has not finished indexing.', 409)
        pages = request.source_page_ranges.get(str(identifier))
        if pages and (not book.page_count or pages[1] > book.page_count):
            raise AppError('invalid_pages', 'The chapter range exceeds the PDF page count.', 400)
        books.append(book)
    return books


async def validate_links(db, user, request):
    if request.class_section_id:
        section = await db.get(ClassSection, request.class_section_id)
        if not section or section.user_id != user.id:
            raise NotFound('Class')
    if isinstance(request, DemoRequest) and request.lesson_plan_id:
        plan = await owned(db, LessonPlan, request.lesson_plan_id, user.id)
        if plan.status not in {'ready', 'reviewed'} or plan.duration_minutes != 15:
            raise AppError('invalid_demo_plan', 'Select a ready 15-minute lesson plan.', 409)
        if any(not float(phase['duration_minutes']).is_integer() for phase in plan.lesson_sequence):
            raise AppError('invalid_demo_plan', 'Demo PPT plans need whole-minute phases. Create a fresh demo or edit the selected plan timing.', 400)
        for field in ('topic', 'subject', 'grade', 'curriculum', 'language', 'education_stage', 'framework'):
            if getattr(plan, field) != getattr(request, field):
                raise AppError('demo_plan_mismatch', 'Use the same topic, grade, subject, education stage, curriculum and framework as the selected plan.', 400)
    if isinstance(request, DemoRequest) and request.template_id:
        from app.services.courses import resolve_template
        await resolve_template(db, user.id, request.template_id, refresh=False)


def resource_fingerprint(request: ResourceRequest, books: list[UploadedFile], preferences=None) -> str:
    scope = request.model_dump(mode='json')
    for field in ('topic', 'subject', 'grade', 'curriculum', 'language'):
        if isinstance(scope.get(field), str):
            scope[field] = ' '.join(scope[field].split()).casefold()
    scope['instructions'] = ' '.join(scope['instructions'].split())
    scope['source_file_ids'] = sorted(scope['source_file_ids'])
    scope['source_hashes'] = sorted((str(book.id), book.sha256) for book in books)
    scope['planning_preferences'] = preferences or {}
    scope['prompt_version'] = PROMPT_VERSION
    scope['schema_version'] = 1
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


async def create_plan(db, user, request: PlanRequest):
    validate_offline_language(request)
    await validate_links(db, user, request)
    await validate_sources(db, user, request)
    cost = await usage.credit_cost('lesson_plan_doc')
    await usage.check(db, user, 'credits', cost, jobs=1)
    row = LessonPlan(owner_id=user.id, title=request.topic, topic=request.topic, subject=request.subject,
        grade=request.grade, curriculum=request.curriculum, language=request.language,
        education_stage=request.education_stage, framework=request.framework, duration_minutes=request.duration_minutes,
        class_section_id=request.class_section_id, status='queued', version=1, schema_version=1,
        review_checks={'request': request.model_dump(mode='json'), 'teacher_review_required': True})
    db.add(row)
    await db.flush()
    job = await enqueue(db, 'educator_plan', {'lesson_plan_id': str(row.id)}, owner_id=user.id,
                        credits_reserved=cost, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    await db.refresh(row)
    return row, job.id


async def create_demo(db, user, request: DemoRequest):
    validate_offline_language(request)
    await validate_links(db, user, request)
    await validate_sources(db, user, request)
    cost = await usage.credit_cost('lesson_plan_doc') + await usage.credit_cost('slide', 8)
    await usage.check(db, user, 'credits', cost, jobs=1)
    row = DemoClass(owner_id=user.id, title=request.topic, topic=request.topic, subject=request.subject,
        grade=request.grade, curriculum=request.curriculum, language=request.language,
        framework=request.framework, duration_minutes=15, status='queued', version=1,
        lesson_plan_id=request.lesson_plan_id,
        review_checks={'request': request.model_dump(mode='json'), 'teacher_review_required': True})
    db.add(row)
    await db.flush()
    job = await enqueue(db, 'educator_demo', {'demo_class_id': str(row.id)}, owner_id=user.id,
                        credits_reserved=cost, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    await db.refresh(row)
    return row, job.id


async def create_resource(db, user, request: ResourceRequest):
    validate_offline_language(request)
    books = await validate_sources(db, user, request)
    profile = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    fingerprint = resource_fingerprint(request, books, getattr(profile, 'planning_preferences', None))
    # Same teacher requests serialize with all existing credit reservations. The owner/cache
    # unique constraint is an additional database guard against duplicate resources.
    await usage.lock_user(db, user.id)
    row = (await db.execute(select(DigitalResource).where(
        DigitalResource.owner_id == user.id, DigitalResource.cache_key == fingerprint))).scalars().first()
    if row and row.status in {'ready', 'reviewed', 'queued', 'generating'}:
        job = await latest_job(db, 'resource_id', row.id, row.owner_id)
        await db.commit()
        return row, job.id if job and row.status in {'queued', 'generating'} else None, True
    cost = await usage.credit_cost('lesson_plan_doc', request.chapter_count)
    await usage.check(db, user, 'credits', cost, jobs=1)
    if row:
        row.status, row.error = 'queued', None
        row.pdf_key = None
        row.content = {'request': request.model_dump(mode='json')}
        row.version += 1
    else:
        row = DigitalResource(owner_id=user.id, title=request.topic, topic=request.topic, subject=request.subject,
            grade=request.grade, curriculum=request.curriculum, language=request.language,
            education_stage=request.education_stage, kind=request.kind, origin='generated',
            cache_key=fingerprint, status='queued', version=1, schema_version=1,
            content={'request': request.model_dump(mode='json')},
            license_metadata={'description': 'AI-generated teaching draft, not an official textbook.', 'shared': False})
        db.add(row)
    await db.flush()
    job = await enqueue(db, 'educator_resource', {'resource_id': str(row.id)}, owner_id=user.id,
                        credits_reserved=cost, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    await db.refresh(row)
    return row, job.id, False


async def latest_job(db, field, identifier, owner_id):
    return (await db.execute(select(GenerationJob).where(
        GenerationJob.owner_id == owner_id,
        or_(GenerationJob.payload[field].astext == str(identifier),
            GenerationJob.payload['entity_id'].astext == str(identifier))).order_by(GenerationJob.created_at.desc()).limit(1))).scalars().first()


def plan_content(row: LessonPlan) -> dict[str, Any] | None:
    if row.status not in {'ready', 'reviewed'}:
        return None
    data = {field: getattr(row, field) for field in PLAN_FIELDS}
    data['review_checks'] = {key: value for key, value in (row.review_checks or {}).items() if key in PlannerReview.model_fields}
    return UAEPlanContent.model_validate(data).model_dump(mode='json')


def summary(row):
    result = {field: getattr(row, field) for field in (
        'title', 'topic', 'subject', 'grade', 'curriculum', 'language', 'status', 'version', 'error')}
    result.update(id=str(row.id), created_at=row.created_at.isoformat() if row.created_at else None)
    for field in ('education_stage', 'framework', 'duration_minutes', 'kind', 'origin'):
        if hasattr(row, field):
            result[field] = getattr(row, field)
    if isinstance(row, DemoClass):
        result['education_stage'] = (row.review_checks or {}).get('request', {}).get('education_stage', 'secondary')
    return result


async def detail(db, row):
    result = summary(row)
    if isinstance(row, LessonPlan):
        result['content'] = plan_content(row)
        review = row.review_checks or {}
        field = 'lesson_plan_id'
    elif isinstance(row, DemoClass):
        result['content'] = {'lesson_plan': (row.review_checks or {}).get('plan_content'),
            'hook': row.hook, 'teacher_script': row.teacher_script, 'slide_payload': row.slide_payload} if row.status in {'ready', 'reviewed'} else None
        review, field = row.review_checks or {}, 'demo_class_id'
        result['lesson_plan_id'] = str(row.lesson_plan_id) if row.lesson_plan_id else None
        result['lesson_id'] = str(row.lesson_id) if row.lesson_id else None
    else:
        if (row.content or {}).get('resource_type') == 'copilot_task':
            result['resource_type'] = 'copilot_task'
            result['content'] = {'resource_type': 'copilot_task', 'printable_task': row.content.get('printable_task')} if row.status in {'ready', 'reviewed'} else None
        else:
            result['content'] = {key: value for key, value in (row.content or {}).items() if key in GeneratedResourceContent.model_fields} if row.status in {'ready', 'reviewed'} else None
        review, field = (row.content or {}).get('review_checks', {}), 'resource_id'
    result['request'] = (row.content or {}).get('request') or (row.content or {}).get('options', {}) if isinstance(row, DigitalResource) else review.get('request', {})
    result['review_checks'] = review
    keys = {**((row.content or {}).get('export_keys', {}) if isinstance(row, DigitalResource) else {}),
            **review.get('export_keys', {})}
    keys = {**keys, **({'pdf': row.pdf_key} if row.pdf_key else {})}
    if isinstance(row, DemoClass) and row.pptx_key:
        keys['pptx'] = row.pptx_key
    result['downloads'] = {ext: get_storage().signed_url(key, f'{row.title[:100]}.{ext}') for ext, key in keys.items() if key}
    if isinstance(row, DemoClass) and row.lesson_id:
        lesson = await db.get(Lesson, row.lesson_id)
        if lesson and lesson.owner_id == row.owner_id:
            # The script is the saved demo draft. Downloads of its presentation
            # follow the editable lesson so a teacher never receives stale slides.
            if lesson.pptx_key:
                result['downloads']['pptx'] = get_storage().signed_url(lesson.pptx_key, f'{row.title[:100]}.pptx')
            if lesson.pdf_key:
                result['downloads']['slides_pdf'] = get_storage().signed_url(lesson.pdf_key, f'{row.title[:100]} slides.pdf')
            result['presentation_version'] = lesson.version
    job = await latest_job(db, field, row.id, row.owner_id)
    result['job'] = {'id': str(job.id), 'status': job.status, 'stage': job.stage,
        'progress': job.progress, 'error': job.error, 'result': job.result} if job else None
    return result


async def cleanup_export_files(row):
    """Delete only predictable keys inside this owner's educator artifact namespace."""
    import logging

    kind = {LessonPlan: 'plan', DemoClass: 'demo', DigitalResource: 'resource'}[type(row)]
    prefix = f'educator/{row.owner_id}/{kind}/{row.id}/'
    keys = {f'{prefix}v{version}.{extension}' for version in range(1, (row.version or 1)+1)
            for extension in ('docx', 'pdf', 'pptx')}
    if isinstance(row, DigitalResource) and (row.content or {}).get('resource_type') == 'copilot_task':
        keys.update(f'educator/{row.owner_id}/copilot/{row.id}.{extension}' for extension in ('docx', 'pdf'))
        keys.update(f'educator/{row.owner_id}/task/{row.id}/v{version}.{extension}'
            for version in range(1, (row.version or 1)+1) for extension in ('docx', 'pdf'))
    for key in keys:
        try:
            await get_storage().delete(key)
        except Exception:
            # A missing file or temporarily unavailable object store must not
            # prevent the account's database records from being removed.
            logging.getLogger('educator').warning('educator_artifact_cleanup_failed')


async def delete_record(db, row):
    job = await latest_job(db, 'entity_id', row.id, row.owner_id)
    fields = {LessonPlan: 'lesson_plan_id', DemoClass: 'demo_class_id', DigitalResource: 'resource_id'}
    generation = await latest_job(db, fields[type(row)], row.id, row.owner_id)
    if row.status in {'queued', 'generating'} or any(
        item and item.status in {'queued', 'running'} for item in (job, generation)):
        raise AppError('task_running', 'Wait for this resource to finish before deleting it.', 409)
    await db.delete(row)
    await db.commit()
    await cleanup_export_files(row)


async def source_evidence(db, user, request) -> tuple[str, list[dict[str, Any]]]:
    books = await validate_sources(db, user, request)
    blocks, references, used = [], [], 0
    for book in books:
        pages = request.source_page_ranges.get(str(book.id))
        query = select(SourceChunk).where(SourceChunk.file_id == book.id, SourceChunk.owner_id == user.id)
        if pages:
            chunks = (await db.execute(query.where(SourceChunk.page.between(*pages)).order_by(SourceChunk.page, SourceChunk.id).limit(150))).scalars().all()
            material = [{'page': chunk.page, 'text': chunk.text} for chunk in chunks]
        else:
            from app.services.sources import retrieve
            material = await retrieve(db, user.id, f'{request.subject}: {request.topic}', k=8, file_ids=[str(book.id)])
        for chunk in material:
            page = chunk['page']
            prefix = f'[{book.id} PDF page {page}] '
            block = prefix + chunk['text']
            size = len(block.encode()) + (1 if blocks else 0)
            if used+size > SOURCE_BYTES:
                continue
            used += size
            blocks.append(block)
            reference = {'title': book.filename, 'url_or_file_id': str(book.id), 'page_or_section': str(page),
                         'relevance': f'Teacher-selected reference for {request.topic}.'}
            if reference not in references:
                references.append(reference)
    return '\n'.join(blocks), references


async def teaching_evidence(db, user, request):
    context, _ = await build_context(db, user, class_section_id=getattr(request, 'class_section_id', None),
                                   include_sources=False)
    profile = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    if profile and profile.planning_preferences:
        preferences = TeacherPlanningPreferences.model_validate(profile.planning_preferences)
        context += '\nTEACHER PLANNING PREFERENCES: ' + json.dumps(preferences.model_dump(mode='json'), ensure_ascii=False)
    material, references = await source_evidence(db, user, request)
    framework = OFFICIAL_REFERENCES.get(getattr(request, 'framework', 'other'), [])
    return context, material, references, framework


def validate_offline_language(request):
    if get_ai().mode == 'offline' and request.language != 'en':
        raise AppError('offline_language', 'Offline educator examples support English. Connect OpenRouter for generation in the selected language.', 400)


async def resource_out(db, row):
    return await detail(db, row)


async def retry_resource(db, user, identifier):
    row = await owned(db, DigitalResource, identifier, user.id, for_update=True)
    if row.status != 'failed':
        raise AppError('not_failed', 'Retry is available for failed resources. Change the brief to create another ready guide.', 409)
    await usage.lock_user(db, user.id)
    if (row.content or {}).get('resource_type') == 'copilot_task':
        from app.api.routes.copilot_resources import CopilotRequest
        request = CopilotRequest.model_validate((row.content or {}).get('options'))
        await validate_sources(db, user, request)
        cost = await usage.credit_cost('worksheet')
        kind, payload = 'copilot_resource', {'resource_id': str(row.id), 'cost': cost}
    else:
        request = ResourceRequest.model_validate((row.content or {}).get('request'))
        await validate_sources(db, user, request)
        validate_offline_language(request)
        cost = await usage.credit_cost('lesson_plan_doc', request.chapter_count)
        kind, payload = 'educator_resource', {'resource_id': str(row.id)}
    await usage.check(db, user, 'credits', cost, jobs=1)
    row.status, row.error, row.pdf_key = 'queued', None, None
    job = await enqueue(db, kind, payload, owner_id=user.id, credits_reserved=cost, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    return job.id


def check_references(items, evidence):
    allowed = {(item['url_or_file_id'], item['page_or_section'], item['title']) for item in evidence}
    for reference in items:
        if (reference.url_or_file_id, reference.page_or_section, reference.title) not in allowed:
            raise ContentQualityError('A generated citation was not present in the supplied evidence. No draft was published.')


def check_plan_scope(plan, request):
    for field in ('topic', 'subject', 'grade', 'curriculum', 'language', 'education_stage', 'framework', 'duration_minutes'):
        if getattr(plan, field) != getattr(request, field):
            raise ContentQualityError(f'The lesson plan changed the requested {field.replace("_", " ")}.')


def evidence_review(content, references, framework, *, offline=False):
    review = content.review_checks
    check_references(content.source_references, references)
    check_references(review.framework_references, framework)
    if not references:
        gap = 'No textbook excerpts were supplied. Check subject facts and coverage against the school-prescribed text.'
        if gap not in review.evidence_gaps and len(review.evidence_gaps) < 20:
            review.evidence_gaps.append(gap)
    elif len(review.evidence_gaps) < 20:
        review.evidence_gaps.append('Selected textbook excerpts support this draft; check full chapter coverage against the original book.')
    if offline and len(review.evidence_gaps) < 20:
        review.evidence_gaps.append('Offline demonstration content: replace the illustrative material before teaching.')


async def generate_plan(ai, request, context, material, references, framework, owner_id, job_id):
    if ai.mode == 'offline':
        result = offline_plan(request)
    else:
        result = await ai.structured(task='educator_plan', tier='planning', system=PLANNER_SYSTEM,
            prompt=json.dumps({'REQUEST': request.model_dump(mode='json'), 'TEACHER_CONTEXT': context,
                'DEMO_PHASE_TIMING': {'Hook': 2, 'Model and explain': 7, 'Guided application': 4, 'Exit check': 2} if isinstance(request, DemoRequest) else None,
                'TIMING_RULE': 'For a demo, use the exact four whole-minute phase timings above so the script and PPT can preserve them.' if isinstance(request, DemoRequest) else 'Use the requested duration exactly.',
                'SUPPLIED EVIDENCE': references, 'FRAMEWORK REFERENCES': framework,
                'TEXTBOOK EXCERPTS': material}, ensure_ascii=False), schema=UAEPlanContent,
            max_tokens=10000, owner_id=owner_id, job_id=job_id, prompt_version=PROMPT_VERSION, cache=True)
    check_plan_scope(result, request)
    if isinstance(request, DemoRequest) and any(not float(phase.duration_minutes).is_integer() for phase in result.lesson_sequence):
        raise ContentQualityError('Demo plan phases need whole-minute timings for the matching presentation.')
    evidence_review(result, references, framework, offline=ai.mode == 'offline')
    return result


def apply_plan(row, content, extras=None):
    payload = content.model_dump(mode='json')
    for field in PLAN_FIELDS:
        setattr(row, field, payload[field])
    row.review_checks = {**payload['review_checks'], **(extras or {}),
                        'teacher_review_required': True, 'prompt_version': PROMPT_VERSION}


async def _save_exports(kind, content, owner_id, identifier, version=1):
    import asyncio

    from app.engine.exports import educator_documents as builders
    from app.engine.qc.visual import RenderError

    builder = {'plan': builders.build_plan_docx, 'demo': builders.build_demo_docx,
               'resource': builders.build_resource_docx, 'task': builders.build_task_docx}[kind]
    docx = await asyncio.to_thread(builder, content)
    prefix = f'educator/{owner_id}/{kind}/{identifier}/v{version}'
    keys = {'docx': prefix+'.docx'}
    await get_storage().put(keys['docx'], docx)
    warnings = []
    try:
        pdf = await builders.educator_docx_to_pdf(docx)
        keys['pdf'] = prefix+'.pdf'
        await get_storage().put(keys['pdf'], pdf, 'application/pdf')
    except RenderError:
        warnings.append('PDF conversion is unavailable; the printable DOCX remains downloadable.')
    return keys, warnings


async def _job_start(ctx, model, field):
    async with get_sessionmaker()() as db:
        if ctx.owner_id is None:
            raise PermanentJobError('An educator job needs an account.')
        row = await owned(db, model, uuid.UUID(ctx.payload[field]), ctx.owner_id)
        user = await db.get(User, ctx.owner_id)
        if not user or user.status != 'active':
            raise PermanentJobError('This account is no longer available.')
        if row.status in {'ready', 'reviewed'}:
            return row, user, None, None
        raw = (row.content or {}).get('request') if model is DigitalResource else (row.review_checks or {}).get('request')
        request = {LessonPlan: PlanRequest, DemoClass: DemoRequest, DigitalResource: ResourceRequest}[model].model_validate(raw)
        if isinstance(request, PlanRequest):
            await validate_links(db, user, request)
        row.status, row.error = 'generating', None
        await db.commit()
        evidence = await teaching_evidence(db, user, request)
        return row, user, request, evidence


@handler('educator_plan', queue='ai')
async def handle_plan(ctx: JobContext):
    await ctx.progress(5, 'Reading selected textbook evidence')
    row, user, request, evidence = await _job_start(ctx, LessonPlan, 'lesson_plan_id')
    if request is None:
        return {'lesson_plan_id': str(row.id), 'cached': True}
    await ctx.progress(25, 'Planning objectives, inclusion and assessment')
    content = await generate_plan(get_ai(), request, *evidence, user.id, ctx.job_id)
    await ctx.progress(75, 'Preparing printable lesson plan')
    keys, warnings = await _save_exports('plan', content.model_dump(mode='json'), user.id, row.id, row.version)
    async with get_sessionmaker()() as db:
        row = await owned(db, LessonPlan, row.id, user.id)
        apply_plan(row, content, {'request': request.model_dump(mode='json'), 'export_keys': keys,
            'export_warnings': warnings, 'supplied_evidence': evidence[2]})
        row.pdf_key, row.status, row.error = keys.get('pdf'), 'ready', None
        await usage.consume(db, user.id, await usage.credit_cost('lesson_plan_doc'), 'educator_plan', str(row.id))
        await db.commit()
    return {'lesson_plan_id': str(row.id), 'files': list(keys)}


def demo_legacy_plan(plan):
    from app.generation.specs import Differentiation, Homework, LessonPhase, QuestionToAsk
    from app.generation.specs import LessonPlan as SlideLessonPlan
    return SlideLessonPlan(lecture_number=1, title=plan.title, duration_minutes=15,
        objectives=[item.description for item in plan.learning_objectives],
        success_criteria=[item.description for item in plan.success_criteria],
        phases=[LessonPhase(name='starter' if index == 0 else 'plenary' if index == len(plan.lesson_sequence)-1
            else 'activity' if index == len(plan.lesson_sequence)-2 else 'main',
            minutes=int(phase.duration_minutes), description=phase.name,
            teacher_actions=phase.teacher_actions, student_actions=phase.student_actions)
            for index, phase in enumerate(plan.lesson_sequence)],
        questions_to_ask=[QuestionToAsk(question=item.question_or_task, bloom_level='apply',
            expected_response=item.expected_response) for item in plan.formative_assessment], misconceptions=[],
        differentiation=Differentiation(support='; '.join(item.scaffold for item in plan.differentiation.sen),
            core=plan.differentiation.core, extension=plan.differentiation.extension,
            eal='; '.join(item.scaffold for item in plan.differentiation.ell),
            send='; '.join(item.assessment_accommodation for item in plan.differentiation.sen)),
        resources=plan.resources, homework=Homework(task=plan.homework, estimated_minutes=10),
        exit_ticket=[item.question_or_task for item in plan.formative_assessment])


async def generate_demo(ai, request, plan, context, material, references, framework, budgets, owner_id, job_id,
                        *, template_slots=None, source_images=None):
    from app.generation.lesson_workflow import SlideBatch
    from app.generation.pipeline import assert_publishable
    from app.generation.specs import LessonDeck

    if ai.mode == 'offline':
        script = offline_demo_script(plan)
    else:
        script = await ai.structured(task='educator_demo_script', tier='content', system=DEMO_SCRIPT_SYSTEM,
            prompt=json.dumps({'TASK': 'Create a high-impact micro-lesson script with 3–8 slide briefs. '
                'Continuous script steps cover 0–900 seconds. Hook involves every learner, modelling contains '
                'a complete explanation/example, practice has concrete SEN/ELL support, and exit check reveals '
                'objective progress. Include teacher dialogue, expected responses, transitions and slide mappings. '
                'Preserve the approved objectives and criteria. Use exactly one opening cover for the hook; '
                'the remaining slides contain the explanation, activity and exit assessment. '
                'Slide briefs must contain teaching content, not placeholders.',
                'APPROVED_PLAN': plan.model_dump(mode='json'), 'TEACHER_CONTEXT': context,
                'TEMPLATE_SLOTS': template_slots or [],
                'SUPPLIED EVIDENCE': references, 'TEXTBOOK EXCERPTS': material}, ensure_ascii=False),
            schema=DemoScriptContent, max_tokens=9500, owner_id=owner_id, job_id=job_id,
            prompt_version=PROMPT_VERSION, cache=True)
    timings = {brief.number: 0.0 for brief in script.slides}
    for brief in script.slides:
        check_references(brief.source_references, references)
    for step in script.teacher_script:
        for number in step.slide_numbers:
            timings[number] += (step.end_seconds-step.start_seconds)/len(step.slide_numbers)/60
    slides = []
    for offset in range(0, len(script.slides), 3):
        briefs = script.slides[offset:offset+3]
        if ai.mode == 'offline':
            batch = offline_slide_batch(briefs, request.language)
        else:
            batch = await ai.structured(task='educator_demo_slides', tier='content',
                system='You format approved classroom teaching content into strict SlideBatch JSON. '
                    'Preserve explanations, worked examples, student questions and answer notes. '
                    'Use exact slide numbers/layouts. Student-facing text totals at most 120 words per slide. '
                    'Use clear short definitions, real content, purposeful native diagrams or relevant stock-photo keywords. '
                    'Never invent citations, image keys, assets or manual objects. Fill unused fields with schema defaults.',
                prompt=json.dumps({'BRIEFS': [brief.model_dump(mode='json') for brief in briefs],
                    'SCRIPT': [step.model_dump(mode='json') for step in script.teacher_script if set(step.slide_numbers)&{brief.number for brief in briefs}],
                    'BUDGETS': budgets, 'GRADE': request.grade, 'LANGUAGE': request.language,
                    'TEMPLATE_SLOTS': template_slots or [],
                    'SOURCE_IMAGES': [{'image_key': key, 'description': value.get('description', '')}
                        for key, value in (source_images or {}).items()],
                    'SUCCESS_CRITERIA': [item.description for item in plan.success_criteria]}, ensure_ascii=False),
                schema=SlideBatch, max_tokens=6000, owner_id=owner_id, job_id=job_id,
                prompt_version=PROMPT_VERSION, cache=True)
        if [(slide.number, slide.layout) for slide in batch.slides] != [(brief.number, brief.layout) for brief in briefs]:
            raise ContentQualityError('Demo slides did not match their approved script and layout mapping.')
        for slide in batch.slides:
            slide.timing_minutes = timings[slide.number]
            slide.asset_id, slide.manual_objects = None, {}
            if slide.visual.source_image_key not in (source_images or {}):
                slide.visual.source_image_key = None
            slide.language = request.language
            slide.outcome_codes = []  # No verified curriculum standard codes are supplied by this request.
            if slide.number == 1:
                slide.title = plan.title
            slide.sources = []
            brief = next(brief for brief in briefs if brief.number == slide.number)
            for reference in brief.source_references:
                try:
                    identifier = str(uuid.UUID(reference.url_or_file_id))
                    page = int(reference.page_or_section)
                except ValueError:
                    continue
                slide.sources.append({'file_id': identifier, 'file': reference.title, 'page': page})
            for step in script.teacher_script:
                if slide.number in step.slide_numbers:
                    slide.speaker_notes += f'\nTeacher: {step.teacher_says}\nExpected response: {step.expected_student_response}\nCheck: {step.formative_check}'
            slides.append(slide)
    deck = LessonDeck(lesson_plan=demo_legacy_plan(plan), slides=slides)
    assert_publishable(deck)
    return DemoClassContent(lesson_plan=plan, hook=script.hook, teacher_script=script.teacher_script, slide_payload=deck)


async def ensure_demo_lesson(db, row, request, plan, template_id, deck):
    """Create an ordinary editable presentation without making a second AI planning call."""
    from app.generation.specs import CoursePlan, LecturePlan, Outcome

    project_id = uuid.uuid5(row.id, 'demo-project')
    course_id = uuid.uuid5(row.id, 'demo-course')
    lesson_id = uuid.uuid5(row.id, 'demo-lesson')
    objectives = [item.description for item in plan.learning_objectives]
    criteria = [item.description for item in plan.success_criteria]
    course_plan = CoursePlan(title=plan.title, overview=f'15-minute demo class: {plan.topic}',
        big_idea=plan.topic, learning_outcomes=[Outcome(text=text) for text in objectives],
        prerequisites=plan.prerequisites,
        diagnostic_questions=[assessment.question_or_task for assessment in plan.formative_assessment],
        lectures=[LecturePlan(number=1, title=plan.title, objectives=objectives, success_criteria=criteria,
            key_concepts=[plan.topic], key_vocabulary=[], activity_idea=plan.differentiation.core,
            assessment_idea=plan.formative_assessment[-1].question_or_task, homework_idea=plan.homework)],
        revision_strategy='Use formative evidence to identify the next teaching step.',
        assessment_strategy='; '.join(assessment.tool for assessment in plan.formative_assessment),
        cross_curricular_links=[f'{link.subject}: {link.activity}' for link in plan.cross_curricular_links],
        local_context_links=[connection.classroom_application for connection in (
            plan.uae_context.national_identity, plan.uae_context.moral_education,
            plan.uae_context.arabic_culture) if connection.relevant])
    project = await db.get(Project, project_id)
    if project is None:
        project = Project(id=project_id, owner_id=row.owner_id, title=plan.title, kind='course',
            status='generating', class_section_id=request.class_section_id)
        db.add(project)
        await db.flush()
    course = await db.get(Course, course_id)
    if course is None:
        course = Course(id=course_id, project_id=project.id, owner_id=row.owner_id,
            topic=request.topic, subject=request.subject, grade=request.grade,
            curriculum=request.curriculum, language=request.language, num_lectures=1,
            slides_per_lecture=len(deck.slides), lecture_minutes=15, template_id=template_id,
            class_section_id=request.class_section_id, outcome_codes=[],
            options={'demo_class_id': str(row.id), 'outcomes': [{'text': text} for text in objectives],
                'instructions': request.instructions, 'source_file_ids': [str(identifier) for identifier in request.source_file_ids],
                'source_page_ranges': request.source_page_ranges, 'flexible_slides': False,
                'image_mode': 'auto', 'framework': request.framework, 'education_stage': request.education_stage},
            plan=course_plan.model_dump(mode='json'), status='generating')
        db.add(course)
        await db.flush()
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        lesson = Lesson(id=lesson_id, owner_id=row.owner_id, course_id=course.id, number=1,
            title=plan.title, plan=deck.lesson_plan.model_dump(mode='json'), status='generating', version=0)
        db.add(lesson)
        # The persistent demo's FK update may otherwise be ordered before the
        # new lesson INSERT because these models have no ORM relationship.
        await db.flush()
    row.lesson_id = lesson_id
    return lesson, course, project


@handler('educator_demo', queue='ai')
async def handle_demo(ctx: JobContext):
    from app.ai.service import template_content_model
    from app.core.config import get_settings
    from app.engine.qc.visual import RenderError
    from app.generation import pipeline
    from app.generation.budgets import compute_budgets
    from app.services import assets
    from app.services.courses import inspect_with_progress, resolve_template, save_lesson_output

    await ctx.progress(5, 'Reading teaching context and textbook excerpts')
    row, user, request, evidence = await _job_start(ctx, DemoClass, 'demo_class_id')
    if request is None:
        return {'demo_class_id': str(row.id), 'cached': True}
    async with get_sessionmaker()() as db:
        template = await resolve_template(db, user.id, request.template_id)
        if not template:
            raise PermanentJobError('No presentation template is available.')
        spec, base = template.spec, await get_storage().get(template.base_storage_key)
        approved = await owned(db, LessonPlan, request.lesson_plan_id, user.id) if request.lesson_plan_id else None
        plan = UAEPlanContent.model_validate(plan_content(approved)) if approved else None
        if plan:
            check_plan_scope(plan, request)
    ai, budgets = get_ai(), compute_budgets(spec)
    await ctx.progress(15, 'Creating the 15-minute backward-design plan')
    if plan is None:
        plan = await generate_plan(ai, request, *evidence, user.id, ctx.job_id)
    await ctx.progress(30, 'Writing teacher dialogue and matching slide batches')
    template_routing = template_content_model.set(get_settings().model_template_content if spec.get('preserve_slots') else None)
    try:
        content = await generate_demo(ai, request, plan, *evidence, budgets, user.id, ctx.job_id,
            template_slots=spec.get('template_slots') if spec.get('preserve_slots') else None,
            source_images=spec.get('source_images'))
    finally:
        template_content_model.reset(template_routing)
    await ctx.progress(60, 'Finding relevant visuals and building the PowerPoint')
    from app.generation.template_slots import prepare_template_images
    prepare_template_images(content.slide_payload.slides, spec, subject=request.subject, topic=request.topic)
    async with get_sessionmaker()() as db:
        images, image_counts = await assets.resolve_images(db, owner_id=user.id,
            slides=content.slide_payload.slides, colors=spec['colors'], job_id=ctx.job_id,
            allow_ai_images=0, image_mode='auto', teaching_context=f'{request.grade} {request.subject}: {request.topic}',
            source_images=spec.get('source_images'), require_real_image=bool(spec.get('preserve_slots')))
        await db.commit()
    outcome = await pipeline.render_with_qc(ai, base_pptx=base, template_spec=spec,
        deck=content.slide_payload, budgets=budgets, images=images, language=request.language,
        core_props={'title': plan.title, 'author': user.name or 'Teacher'},
        context_text=evidence[0], grade=request.grade, owner_id=user.id, job_id=ctx.job_id, max_rounds=2)
    if any(report.get('overflow') for report in outcome.reports):
        raise ContentQualityError('The demo presentation still has overflowing content. No presentation was published.')
    # Repairs can change slide content, but never the approved plan, timing, or script mapping.
    DemoClassContent.model_validate(content.model_dump())
    await ctx.progress(76, 'Checking rendered slides and preparing previews')
    visual, visual_warning = None, None
    try:
        visual = await inspect_with_progress(ctx, outcome.pptx, pct=76)
    except (RenderError, OSError) as exc:
        visual_warning = 'Rendered slide checks and previews are unavailable: ' + str(exc)[:200]
    if visual is not None and visual.failing_slides:
        raise ContentQualityError('The demo presentation failed rendered slide checks. No presentation was published.')
    await ctx.progress(85, 'Saving script and printable materials')
    keys, warnings = await _save_exports('demo', content.model_dump(mode='json'), user.id, row.id, row.version)
    if visual_warning:
        warnings.append(visual_warning)
    pptx_key = f'educator/{user.id}/demo/{row.id}/v{row.version}.pptx'
    await get_storage().put(pptx_key, outcome.pptx)
    async with get_sessionmaker()() as db:
        row = await owned(db, DemoClass, row.id, user.id)
        lesson, course, project = await ensure_demo_lesson(db, row, request, plan, template.id, content.slide_payload)
        await db.commit()
    await save_lesson_output(lesson.id, content.slide_payload, outcome.pptx, visual, qc={
        'generation_job_id': str(ctx.job_id), 'render': outcome.reports, 'repairs': outcome.repairs,
        'images': image_counts, 'visual_error': visual_warning,
        'visual': {str(number): issues for number, issues in visual.issues.items()} if visual else {},
        'content_quality': {'status': 'structural_checks_passed', 'fact_check_status': 'teacher_review_required'},
    }, reason='demo generated')
    async with get_sessionmaker()() as db:
        row = await owned(db, DemoClass, row.id, user.id)
        course = await owned(db, Course, course.id, user.id)
        project = await owned(db, Project, project.id, user.id)
        course.status, project.status = 'ready', 'ready'
        if not row.lesson_plan_id:
            draft = LessonPlan(owner_id=user.id, class_section_id=request.class_section_id,
                status='ready', version=1, **{field: getattr(plan, field) for field in ('title', 'topic', 'subject', 'grade', 'curriculum', 'language')})
            saved_request = request.model_dump(mode='json', include=set(PlanRequest.model_fields))
            apply_plan(draft, plan, {'request': saved_request, 'supplied_evidence': evidence[2]})
            db.add(draft)
            await db.flush()
            row.lesson_plan_id = draft.id
        row.title, row.hook = plan.title, content.hook.model_dump(mode='json')
        row.teacher_script = [step.model_dump(mode='json') for step in content.teacher_script]
        row.slide_payload = content.slide_payload.model_dump(mode='json')
        row.source_references = [item.model_dump(mode='json') for item in plan.source_references]
        row.review_checks = {**plan.review_checks.model_dump(mode='json'), 'request': request.model_dump(mode='json'),
            'plan_content': plan.model_dump(mode='json'), 'export_keys': keys, 'export_warnings': warnings,
            'teacher_review_required': True, 'prompt_version': PROMPT_VERSION, 'render_reports': outcome.reports,
            'image_counts': image_counts, 'supplied_evidence': evidence[2]}
        row.pdf_key, row.pptx_key, row.status = keys.get('pdf'), pptx_key, 'ready'
        cost = await usage.credit_cost('lesson_plan_doc') + await usage.credit_cost('slide', len(content.slide_payload.slides))
        await usage.consume(db, user.id, cost, 'educator_demo', str(row.id))
        await db.commit()
    return {'demo_class_id': str(row.id), 'lesson_plan_id': str(row.lesson_plan_id),
        'lesson_id': str(row.lesson_id), 'files': [*keys, 'pptx']}


async def generate_resource(ai, request, context, material, references, owner_id, job_id):
    if ai.mode == 'offline':
        outline = offline_resource_outline(request)
    else:
        outline = await ai.structured(task='educator_resource_outline', tier='content', system=RESOURCE_OUTLINE_SYSTEM,
            prompt=json.dumps({'TASK': 'Outline exactly the requested chapter_count non-overlapping chapters '
                'for an AI-generated subject primer/study guide, never an official textbook. Cover requested '
                'scope at the given education stage, with definitions, complete solved examples, UAE illustrative '
                'case studies, summaries and answer-bearing practice. Do not invent sourced facts.',
                'REQUEST': request.model_dump(mode='json'), 'TEACHER_CONTEXT': context,
                'SUPPLIED EVIDENCE': references, 'TEXTBOOK EXCERPTS': material}, ensure_ascii=False),
            schema=ResourceOutline, max_tokens=5000, owner_id=owner_id, job_id=job_id,
            prompt_version=PROMPT_VERSION, cache=True)
    if [chapter.number for chapter in outline.chapters] != list(range(1, request.chapter_count+1)):
        raise ContentQualityError('The guide outline did not cover the requested chapter count.')
    check_references(outline.review_checks.framework_references, [])
    chapters = []
    for chapter in outline.chapters:
        if ai.mode == 'offline':
            generated = offline_resource_chapter(request, chapter)
        else:
            generated = await ai.structured(task='educator_resource_chapter', tier='content', system=RESOURCE_CHAPTER_SYSTEM,
                prompt=json.dumps({'TASK': 'Write one comprehensive chapter for a teacher-reviewed guide. '
                    'Explain concepts before assuming knowledge, give concrete definitions and step-by-step solved '
                    'examples, an illustrative UAE case study (label invented scenarios as illustrative), summary, '
                    'practice and a complete paired answer key. Each example must actually teach this chapter, '
                    'never generic filler. Preserve the exact chapter number and title. Cite only supplied evidence.',
                    'SCOPE': {key: value for key, value in request.model_dump(mode='json').items() if key != 'source_file_ids'},
                    'CHAPTER': chapter.model_dump(mode='json'), 'OTHER_CHAPTERS': [entry.title for entry in outline.chapters],
                    'SUPPLIED EVIDENCE': references, 'TEXTBOOK EXCERPTS': material}, ensure_ascii=False),
                schema=ResourceChapter, max_tokens=6500, owner_id=owner_id, job_id=job_id,
                prompt_version=PROMPT_VERSION, cache=True)
        if generated.number != chapter.number or generated.title != chapter.title:
            raise ContentQualityError('A guide chapter changed its approved outline mapping.')
        check_references(generated.source_references, references)
        chapters.append(generated)
    source_references = list({(item.url_or_file_id, item.page_or_section): item
                              for chapter in chapters for item in chapter.source_references}.values())[:24]
    content = GeneratedResourceContent(schema_version=1, title=outline.title, topic=request.topic,
        subject=request.subject, education_stage=request.education_stage, grade=request.grade,
        curriculum=request.curriculum, language=request.language, kind=request.kind, origin='generated',
        overview=outline.overview, chapters=chapters, source_references=source_references, review_checks=outline.review_checks)
    evidence_review(content, references, [], offline=ai.mode == 'offline')
    return content


@handler('educator_resource', queue='ai')
async def handle_resource(ctx: JobContext):
    await ctx.progress(10, 'Reading selected sources and planning the guide')
    row, user, request, evidence = await _job_start(ctx, DigitalResource, 'resource_id')
    if request is None:
        return {'resource_id': str(row.id), 'cached': True}
    context, material, references, _ = evidence
    await ctx.progress(25, 'Writing bounded chapters with examples and answers')
    content = await generate_resource(get_ai(), request, context, material, references, user.id, ctx.job_id)
    await ctx.progress(85, 'Preparing the reusable printable guide')
    keys, warnings = await _save_exports('resource', content.model_dump(mode='json'), user.id, row.id, row.version)
    async with get_sessionmaker()() as db:
        row = await owned(db, DigitalResource, row.id, user.id)
        row.content = {**content.model_dump(mode='json'), 'request': request.model_dump(mode='json'),
            'review_checks': {**content.review_checks.model_dump(mode='json'), 'export_keys': keys,
                'export_warnings': warnings, 'prompt_version': PROMPT_VERSION}}
        row.title, row.chapters = content.title, [chapter.model_dump(mode='json') for chapter in content.chapters]
        row.source_references = [item.model_dump(mode='json') for item in content.source_references]
        row.pdf_key, row.status = keys.get('pdf'), 'ready'
        await usage.consume(db, user.id, await usage.credit_cost('lesson_plan_doc', request.chapter_count),
                            'educator_resource', str(row.id))
        await db.commit()
    return {'resource_id': str(row.id), 'chapters': len(content.chapters), 'files': list(keys)}


async def mark_failed(ctx, error, model, field):
    async with get_sessionmaker()() as db:
        row = await db.get(model, uuid.UUID(ctx.payload[field]))
        if row and row.owner_id == ctx.owner_id and row.status not in {'ready', 'reviewed'}:
            row.status, row.error = 'failed', error[:1000]
            await db.commit()


@on_failure('educator_plan')
async def plan_failed(ctx, error):
    await mark_failed(ctx, error, LessonPlan, 'lesson_plan_id')


@on_failure('educator_demo')
async def demo_failed(ctx, error):
    await mark_failed(ctx, error, DemoClass, 'demo_class_id')
    async with get_sessionmaker()() as db:
        row = await db.get(DemoClass, uuid.UUID(ctx.payload['demo_class_id']))
        if row and row.owner_id == ctx.owner_id and row.status == 'failed' and row.lesson_id:
            lesson = await db.get(Lesson, row.lesson_id)
            if lesson and lesson.owner_id == ctx.owner_id:
                lesson.status, lesson.error = 'failed', error[:1000]
                course = await db.get(Course, lesson.course_id)
                if course:
                    course.status, course.error = 'failed', error[:1000]
            await db.commit()


@on_failure('educator_resource')
async def resource_failed(ctx, error):
    await mark_failed(ctx, error, DigitalResource, 'resource_id')


async def update_plan(db, user, identifier, content, version):
    row = await owned(db, LessonPlan, identifier, user.id, for_update=True)
    if row.status not in {'ready', 'reviewed'}:
        raise AppError('not_ready', 'Wait for the plan to finish generating before editing.', 409)
    if row.version != version:
        raise AppError('version_conflict', 'This plan changed. Refresh before saving.', 409)
    request = PlanRequest.model_validate((row.review_checks or {})['request'])
    check_plan_scope(content, request)
    # A manual edit must not trigger a paid embedding/retrieval request. Generated
    # drafts retain the exact supplied evidence; older drafts use their saved citations.
    await validate_sources(db, user, request)
    references = (row.review_checks or {}).get('supplied_evidence', row.source_references or [])
    framework = OFFICIAL_REFERENCES.get(request.framework, [])
    evidence_review(content, references, framework)
    apply_plan(row, content, {'request': request.model_dump(mode='json'), 'supplied_evidence': references})
    row.version += 1
    row.status, row.pdf_key, row.reviewed_at = 'ready', None, None
    await db.commit()
    return row


async def review_plan(db, user, identifier, version, notes):
    row = await owned(db, LessonPlan, identifier, user.id, for_update=True)
    if row.status not in {'ready', 'reviewed'} or row.version != version:
        raise AppError('version_conflict', 'Review the latest ready plan before approving it.', 409)
    UAEPlanContent.model_validate(plan_content(row))
    row.status, row.reviewed_at = 'reviewed', utcnow()
    row.review_checks = {**(row.review_checks or {}), 'teacher_review_required': False,
        'reviewed_version': row.version, 'review_notes': notes, 'reviewed_by': str(user.id)}
    await db.commit()
    return row


async def start_export(db, user, kind, identifier):
    model = {'plan': LessonPlan, 'demo': DemoClass, 'resource': DigitalResource}[kind]
    row = await owned(db, model, identifier, user.id)
    if row.status not in {'ready', 'reviewed'}:
        raise AppError('not_ready', 'Generate this draft before exporting it.', 409)
    job = await enqueue(db, 'educator_export', {'kind': kind, 'entity_id': str(identifier), 'version': row.version},
                        owner_id=user.id, dedupe=True, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    return job.id


@handler('educator_export', queue='docs')
async def handle_export(ctx):
    kind = ctx.payload['kind']
    model = {'plan': LessonPlan, 'demo': DemoClass, 'resource': DigitalResource}[kind]
    async with get_sessionmaker()() as db:
        row = await owned(db, model, uuid.UUID(ctx.payload['entity_id']), ctx.owner_id)
        if row.version != ctx.payload['version']:
            raise PermanentJobError('The draft changed. Export the latest version.')
        if kind == 'plan':
            content = plan_content(row)
        elif kind == 'demo':
            content = {'lesson_plan': row.review_checks['plan_content'], 'hook': row.hook,
                'teacher_script': row.teacher_script, 'slide_payload': row.slide_payload}
        else:
            content = row.content.get('printable_task') if row.content.get('resource_type') == 'copilot_task' else {
                key: value for key, value in row.content.items() if key in GeneratedResourceContent.model_fields}
            builder_kind = 'task' if row.content.get('resource_type') == 'copilot_task' else 'resource'
    if content is None:
        raise PermanentJobError('The draft is no longer ready for export.')
    await ctx.progress(30, 'Preparing printable documents')
    keys, warnings = await _save_exports(builder_kind if kind == 'resource' else kind, content, ctx.owner_id, row.id, row.version)
    async with get_sessionmaker()() as db:
        row = await owned(db, model, row.id, ctx.owner_id)
        if row.version != ctx.payload['version']:
            raise PermanentJobError('The draft changed during export. Export the latest version.')
        row.pdf_key = keys.get('pdf')
        if kind == 'resource':
            row.content = {**row.content, 'review_checks': {**row.content['review_checks'],
                'export_keys': keys, 'export_warnings': warnings}}
        else:
            row.review_checks = {**row.review_checks, 'export_keys': keys, 'export_warnings': warnings}
        await db.commit()
    return {'entity_id': str(row.id), 'files': list(keys)}


def offline_plan(request):
    """Explicitly labelled, deterministic examples for local no-key testing."""
    objective = f'Explain one key idea about {request.topic} using an example.'
    context = {'relevant': True, 'connection_or_reason': 'Illustrative UAE classroom application; check the topic-specific link.',
               'classroom_application': 'Connect the example to a familiar school or UAE community setting.'}
    strategy = {'learning_barrier': 'Dense text or a multistep task', 'scaffold': 'Chunk instructions and model a labelled example.',
                'assessment_accommodation': 'Accept an oral explanation or annotated diagram against the same criterion.'}
    minutes = [2, 7, 4, 2] if isinstance(request, DemoRequest) else [request.duration_minutes*weight/10 for weight in (1, 4, 3, 2)]
    return UAEPlanContent.model_validate({'schema_version': 1, 'title': request.topic, 'topic': request.topic,
        'subject': request.subject, 'grade': request.grade, 'curriculum': request.curriculum, 'language': request.language,
        'education_stage': request.education_stage, 'framework': request.framework, 'duration_minutes': request.duration_minutes,
        'learning_objectives': [{'id': 'o1', 'description': objective, 'observable_action': 'explain',
            'success_measure': 'Give a correct explanation and one relevant example.', 'bloom_level': 'understand'}],
        'success_criteria': [{'id': 'c1', 'objective_ids': ['o1'], 'description': 'I can explain the idea and give an example.',
            'observable_evidence': 'An explanation that links the example to the idea.'}],
        'cross_curricular_links': [{'subject': 'Literacy', 'activity': 'Explain the reasoning using a complete sentence.',
            'evidence_of_learning': 'Use a key term accurately.'}],
        'uae_context': {'national_identity': context, 'moral_education': {**context, 'classroom_application': 'Listen respectfully and justify a choice.'},
            'arabic_culture': {**context, 'classroom_application': 'Offer a checked Arabic/English vocabulary card where relevant.'}},
        'differentiation': {'sen': [strategy], 'ell': [{**strategy, 'learning_barrier': 'Unfamiliar subject vocabulary',
            'scaffold': 'Use a picture glossary and the sentence frame: This example shows __ because __.'}],
            'core': 'Explain the modelled idea using a new example.', 'extension': 'Justify a contrasting example and explain a limitation.'},
        'formative_assessment': [{'id': 'a1', 'objective_ids': ['o1'], 'tool': 'Mini-whiteboard exit check',
            'question_or_task': f'Explain an example of {request.topic}.', 'expected_response': 'A correct, relevant explanation linked to the idea.',
            'evidence_to_record': 'Accuracy of vocabulary, explanation and connection.', 'teaching_response': 'Remodel any misconception before the next task.'}],
        'lesson_sequence': [{'name': name, 'duration_minutes': duration, 'objective_ids': ['o1'],
            'teacher_actions': action, 'student_actions': task, 'assessment_ids': ['a1'] if index == 3 else []}
            for index, (name, duration, action, task) in enumerate(zip(
                ['Hook', 'Model and explain', 'Guided application', 'Exit check'], minutes,
                ['Ask learners to compare two examples.', 'Model a checked topic-specific example.', 'Prompt explanations and offer scaffolds.', 'Collect and assess a short response.'],
                ['State an observation.', 'Explain the example to a partner.', 'Apply the idea to a new example.', 'Show evidence of the learning objective.'], strict=True))],
        'prerequisites': [request.prerequisites or 'Check learners’ prior understanding before the explanation.'],
        'homework': 'Explain one additional example using the checked class vocabulary.', 'resources': ['Whiteboards', 'Teacher-checked example cards'],
        'source_references': [], 'review_checks': {'alignment_status': 'teacher_review_required', 'framework_references': [],
            'evidence_gaps': ['Offline demonstration: this is an illustrative planning scaffold, not subject research.'],
            'teacher_checks': ['Replace illustrative content with checked topic-specific explanations.', 'Check SEN/ELL access and school planning requirements.']}})


def offline_demo_script(plan):
    titles = ['Notice and predict', 'Learning intention', 'Model the key idea', 'Guided practice', 'Explain your reasoning', 'Exit check']
    timings = [90, 60, 240, 240, 150, 120]
    slides, script, cursor = [], [], 0
    for number, (title, seconds) in enumerate(zip(titles, timings, strict=True), 1):
        task = plan.formative_assessment[0].question_or_task if number == 6 else f'Explain a checked example of {plan.topic}.'
        slides.append(DemoSlideBrief(number=number, title=title, purpose=title,
            layout='cover' if number == 1 else 'objectives' if number == 2 else 'exit_ticket' if number == 6 else 'concept',
            content=[plan.learning_objectives[0].description, plan.success_criteria[0].description],
            student_task=task, expected_answer=plan.formative_assessment[0].expected_response,
            visual_brief='Use teacher-checked example cards and editable labels.'))
        script.append(DemoScriptStep(order=number, start_seconds=cursor, end_seconds=cursor+seconds,
            slide_numbers=[number], teacher_says=f'Let’s explore {plan.topic}. {task}',
            teacher_does='Model an example and use the support glossary.',
            expected_student_response=plan.formative_assessment[0].expected_response,
            formative_check='Listen for a correct explanation and link to the example.', transition='Share, then move to the next task.'))
        cursor += seconds
    return DemoScriptContent(hook=DemoHook(teacher_says='Compare these two teacher-checked examples. What do you notice?',
        learner_interaction='Think, pair and share one observation.', materials=['Example cards']), teacher_script=script, slides=slides)


def offline_slide_batch(briefs, language):
    from app.generation.lesson_workflow import SlideBatch
    from app.generation.specs import Bullet, SlideSpec
    return SlideBatch(slides=[SlideSpec(number=brief.number, layout=brief.layout, purpose=brief.purpose,
        title=brief.title, bullets=[Bullet(text=line) for line in brief.content], question=brief.student_task,
        speaker_notes='Offline illustrative draft. '+brief.expected_answer, language=language) for brief in briefs])


def offline_resource_outline(request):
    return ResourceOutline(title=f'{request.topic} — {request.kind.replace("_", " ")}'[:300],
        overview='Offline illustrative study scaffold. Replace example content with verified subject explanations.',
        chapters=[ChapterOutline(number=number, title=f'{request.topic}: part {number}'[:300],
            learning_goals=[f'Explain a checked idea about {request.topic}.'], scope='Teacher-selected subtopic and examples.')
            for number in range(1, request.chapter_count+1)],
        review_checks=PlannerReview(alignment_status='teacher_review_required', framework_references=[],
            evidence_gaps=['Offline demonstration; the content is a scaffold rather than subject research.'],
            teacher_checks=['Verify every definition, example and answer against the prescribed material.']))


def offline_resource_chapter(request, chapter):
    return ResourceChapter(number=chapter.number, title=chapter.title, learning_goals=chapter.learning_goals,
        explanation=f'Illustrative scaffold for {request.topic}. Start with a checked definition, model an example and explain why it fits.',
        definitions=['Key term: insert the verified subject definition before using this scaffold.'],
        worked_examples=['Choose a checked example -> identify the key term -> explain the connection -> compare a contrasting example.'],
        uae_case_study='Illustrative UAE school scenario: learners compare two classroom examples and justify their reasoning.',
        summary='Explain the definition, show a relevant example and check the reasoning.',
        practice_questions=['How does your selected example illustrate the key idea?'],
        expected_answers=['A checked explanation that uses the key definition accurately and links it to the example.'], source_references=[])

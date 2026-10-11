"""Evidence, cost bounds, owner isolation and script/slide alignment without paid calls."""
from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.api.routes import educator as routes
from app.core.errors import AppError, NotFound
from app.generation.educator_specs import DemoClassContent, SourceReference, UAEPlanContent
from app.generation.quality import ContentQualityError
from app.models import DemoClass, DigitalResource, LessonPlan
from app.services import educator

OWNER = uuid.UUID('11111111-1111-4111-8111-111111111111')
SOURCE = uuid.UUID('22222222-2222-4222-8222-222222222222')


def request(kind='plan', **changes):
    data = {'topic': 'Ecosystems', 'subject': 'Science', 'grade': '6', 'curriculum': 'british',
            'framework': 'khda', **changes}
    cls = {'plan': educator.PlanRequest, 'demo': educator.DemoRequest, 'resource': educator.ResourceRequest}[kind]
    if kind == 'resource':
        data.pop('framework', None)
    return cls(**data)


def rows_result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    result.scalars.return_value.first.return_value = rows[0] if rows else None
    return result


def book(**changes):
    return SimpleNamespace(id=SOURCE, owner_id=OWNER, sha256='a'*64, kind='source', status='ready',
                           filename='Science.pdf', page_count=40, **changes)


def saved_resource(status='ready', **changes):
    data = dict(id=uuid.uuid4(), owner_id=OWNER, title='Ecosystems guide', topic='Ecosystems',
        subject='Science', grade='6', curriculum='british', language='en', education_stage='secondary',
        kind='subject_primer', origin='generated', cache_key='f'*64, status=status, version=1,
        content={}, chapters=[])
    return DigitalResource(**{**data, **changes})


@pytest.mark.parametrize('changes', [
    {'source_page_ranges': {str(SOURCE): [1, 2]}},
    {'source_file_ids': [SOURCE], 'source_page_ranges': {str(SOURCE): [5, 4]}},
    {'source_file_ids': [SOURCE], 'source_page_ranges': {str(SOURCE): [1, 81]}},
    {'source_file_ids': [SOURCE], 'source_page_ranges': {str(SOURCE): [True, 4]}},
    {'source_file_ids': [SOURCE, SOURCE]},
    {'education_stage': 'university', 'framework': 'adek'},
])
def test_planner_rejects_invalid_source_ranges_and_university_school_framework(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_demo_duration_is_fixed_and_school_guides_need_grade():
    with pytest.raises(ValidationError):
        request('demo', duration_minutes=20)
    with pytest.raises(ValidationError):
        request('resource', grade=None)
    assert request('resource', grade=None, education_stage='university').grade is None


async def test_owner_scope_is_enforced_for_even_admin_and_linked_sources():
    row = SimpleNamespace(owner_id=uuid.uuid4())
    db = AsyncMock()
    db.get.return_value = row
    with pytest.raises(NotFound):
        await educator.owned(db, LessonPlan, uuid.uuid4(), OWNER)
    with pytest.raises(NotFound):
        await educator.validate_sources(db, SimpleNamespace(id=OWNER, role='admin'), request(source_file_ids=[SOURCE]))


async def test_book_must_be_indexed_and_selected_pdf_pages_must_exist():
    db = AsyncMock()
    b = book()
    db.get.return_value = b
    b.status = 'queued'
    with pytest.raises(AppError, match='finished indexing'):
        await educator.validate_sources(db, SimpleNamespace(id=OWNER), request(source_file_ids=[SOURCE]))
    b.status = 'ready'
    with pytest.raises(AppError, match='page count'):
        await educator.validate_sources(db, SimpleNamespace(id=OWNER),
            request(source_file_ids=[SOURCE], source_page_ranges={str(SOURCE): [30, 41]}))


def test_resource_fingerprint_normalizes_scope_and_invalidates_sources_and_versions(monkeypatch):
    a = request('resource', source_file_ids=[SOURCE], topic='  Ecosystems  ')
    b = request('resource', source_file_ids=[SOURCE], topic='ecosystems')
    assert educator.resource_fingerprint(a, [book()]) == educator.resource_fingerprint(b, [book()])
    changed_book = book()
    changed_book.sha256 = 'b'*64
    assert educator.resource_fingerprint(a, [book()]) != educator.resource_fingerprint(a, [changed_book])
    assert educator.resource_fingerprint(a, [book()]) != educator.resource_fingerprint(
        request('resource', source_file_ids=[SOURCE], source_page_ranges={str(SOURCE): [2, 4]}), [book()])
    old = educator.resource_fingerprint(a, [book()])
    monkeypatch.setattr(educator, 'PROMPT_VERSION', 'educator-v2')
    assert educator.resource_fingerprint(a, [book()]) != old


async def test_ready_resource_cache_reserves_no_credits_and_enqueues_nothing(monkeypatch):
    saved = saved_resource()
    db = AsyncMock()
    db.execute.return_value = rows_result([saved])
    monkeypatch.setattr(educator, 'get_ai', lambda: SimpleNamespace(mode='live'))
    monkeypatch.setattr(educator, 'validate_sources', AsyncMock(return_value=[]))
    lock, check, enqueue = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(educator.usage, 'lock_user', lock)
    monkeypatch.setattr(educator.usage, 'check', check)
    monkeypatch.setattr(educator, 'enqueue', enqueue)
    monkeypatch.setattr(educator, 'latest_job', AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    row, job_id, cached = await educator.create_resource(db, SimpleNamespace(id=OWNER), request('resource'))
    assert row is saved and cached and job_id is None
    check.assert_not_awaited()
    enqueue.assert_not_awaited()
    lock.assert_awaited_once_with(db, OWNER)
    db.commit.assert_awaited_once()


async def test_running_cache_returns_existing_job_without_another_charge(monkeypatch):
    saved = saved_resource('generating')
    job = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    db.execute.return_value = rows_result([saved])
    monkeypatch.setattr(educator, 'get_ai', lambda: SimpleNamespace(mode='live'))
    monkeypatch.setattr(educator, 'validate_sources', AsyncMock(return_value=[]))
    monkeypatch.setattr(educator.usage, 'lock_user', AsyncMock())
    monkeypatch.setattr(educator.usage, 'check', AsyncMock())
    monkeypatch.setattr(educator, 'enqueue', AsyncMock())
    monkeypatch.setattr(educator, 'latest_job', AsyncMock(return_value=job))
    _, job_id, cached = await educator.create_resource(db, SimpleNamespace(id=OWNER), request('resource'))
    assert job_id == job.id and cached
    educator.usage.check.assert_not_awaited()
    educator.enqueue.assert_not_awaited()


async def test_planning_system_has_backward_design_and_model_cannot_forge_citations():
    req = request()
    generated = educator.offline_plan(req)
    generated.source_references = [SourceReference(title='Invented book', url_or_file_id=str(SOURCE),
        page_or_section='999', relevance='Unsupported page')]
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=generated))
    with pytest.raises(ContentQualityError, match='supplied evidence'):
        await educator.generate_plan(ai, req, '', '', [], [], OWNER, uuid.uuid4())
    params = ai.structured.await_args.kwargs
    assert params['tier'] == 'planning' and params['schema'] is UAEPlanContent
    assert 'UAE Master Teacher and School Inspector' in params['system']
    assert 'SEN' in params['system'] and 'ELL' in params['system']
    assert params['owner_id'] == OWNER and params['cache']


async def test_model_cannot_change_the_teachers_requested_curriculum():
    req = request()
    generated = educator.offline_plan(req)
    generated.curriculum = 'cbse'
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=generated))
    with pytest.raises(ContentQualityError, match='curriculum'):
        await educator.generate_plan(ai, req, '', '', [], [], OWNER, uuid.uuid4())


async def test_real_reference_is_allowed_but_missing_subject_evidence_is_visible():
    req = request()
    generated = educator.offline_plan(req)
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=generated))
    result = await educator.generate_plan(ai, req, '', '', [], educator.OFFICIAL_REFERENCES['khda'], OWNER, uuid.uuid4())
    assert any('No textbook excerpts' in gap for gap in result.review_checks.evidence_gaps)
    assert result.review_checks.alignment_status == 'teacher_review_required'


@pytest.mark.parametrize('change', ['gap', 'order', 'omitted_slide', 'unknown_slide', 'duplicate_slide', 'short'])
def test_script_cannot_hide_gaps_or_unmapped_slides(change):
    script = educator.offline_demo_script(educator.offline_plan(request('demo'))).model_dump()
    if change == 'gap':
        script['teacher_script'][1]['start_seconds'] += 1
    elif change == 'order':
        script['teacher_script'][0]['order'] = 2
    elif change == 'omitted_slide':
        script['teacher_script'][-1]['slide_numbers'] = [5]
    elif change == 'unknown_slide':
        script['teacher_script'][0]['slide_numbers'] = [999]
    elif change == 'duplicate_slide':
        script['teacher_script'][0]['slide_numbers'] = [1, 1]
    else:
        script['teacher_script'][-1]['end_seconds'] = 899
    with pytest.raises(ValidationError):
        educator.DemoScriptContent.model_validate(script)


async def test_demo_uses_bounded_batches_and_preserves_approved_plan_and_exact_script_timing():
    req = request('demo')
    plan = educator.offline_plan(req)
    script = educator.offline_demo_script(plan)
    batches = [educator.offline_slide_batch(script.slides[offset:offset+3], 'en') for offset in (0, 3)]
    # A malicious model must not smuggle a teacher's other asset or arbitrary editor objects.
    batches[0].slides[0].asset_id = str(uuid.uuid4())
    batches[0].slides[0].visual.source_image_key = 'unowned-storage-key'
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[script, *batches]))
    result = await educator.generate_demo(ai, req, plan, '', '', [], [], {}, OWNER, uuid.uuid4())
    DemoClassContent.model_validate(result.model_dump())
    assert [call.kwargs['task'] for call in ai.structured.await_args_list] == [
        'educator_demo_script', 'educator_demo_slides', 'educator_demo_slides']
    assert result.slide_payload.lesson_plan.objectives == [item.description for item in plan.learning_objectives]
    assert [phase.minutes for phase in result.slide_payload.lesson_plan.phases] == [2, 7, 4, 2]
    assert result.slide_payload.lesson_plan.differentiation.send == plan.differentiation.sen[0].assessment_accommodation
    assert result.slide_payload.lesson_plan.differentiation.eal == plan.differentiation.ell[0].scaffold
    assert [slide.timing_minutes for slide in result.slide_payload.slides] == [1.5, 1, 4, 4, 2.5, 2]
    assert result.slide_payload.slides[0].asset_id is None
    assert result.slide_payload.slides[0].visual.source_image_key is None
    assert 'Expected response:' in result.slide_payload.slides[0].speaker_notes


async def test_demo_formatter_cannot_renumber_or_drop_approved_slides():
    req = request('demo')
    plan = educator.offline_plan(req)
    script = educator.offline_demo_script(plan)
    batch = educator.offline_slide_batch(script.slides[:3], 'en')
    batch.slides.pop()
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[script, batch]))
    with pytest.raises(ContentQualityError, match='approved script'):
        await educator.generate_demo(ai, req, plan, '', '', [], [], {}, OWNER, uuid.uuid4())


async def test_resource_generation_is_one_outline_then_one_call_per_chapter():
    req = request('resource', chapter_count=3)
    outline = educator.offline_resource_outline(req)
    chapters = [educator.offline_resource_chapter(req, chapter) for chapter in outline.chapters]
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[outline, *chapters]))
    generated = await educator.generate_resource(ai, req, '', '', [], OWNER, uuid.uuid4())
    assert len(generated.chapters) == 3
    assert generated.origin == 'generated' and generated.kind == 'subject_primer'
    assert [call.kwargs['task'] for call in ai.structured.await_args_list] == ['educator_resource_outline'] + ['educator_resource_chapter']*3
    assert all(call.kwargs['tier'] == 'content' for call in ai.structured.await_args_list)
    assert all(chapter.practice_questions and len(chapter.practice_questions) == len(chapter.expected_answers) for chapter in generated.chapters)


async def test_bad_outline_never_triggers_expensive_chapter_calls():
    req = request('resource', chapter_count=3)
    outline = educator.offline_resource_outline(req)
    outline.chapters.pop()
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=outline))
    with pytest.raises(ContentQualityError, match='chapter count'):
        await educator.generate_resource(ai, req, '', '', [], OWNER, uuid.uuid4())
    assert ai.structured.await_count == 1


async def test_bad_chapter_mapping_is_not_published():
    req = request('resource', chapter_count=1)
    outline = educator.offline_resource_outline(req)
    chapter = educator.offline_resource_chapter(req, outline.chapters[0])
    chapter.number = 2
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[outline, chapter]))
    with pytest.raises(ContentQualityError, match='outline mapping'):
        await educator.generate_resource(ai, req, '', '', [], OWNER, uuid.uuid4())


async def test_pdf_converter_failure_preserves_docx_and_explicit_warning(monkeypatch):
    from app.engine.exports import educator_documents
    from app.engine.qc.visual import RenderError
    content = educator.offline_plan(request()).model_dump()
    storage = SimpleNamespace(put=AsyncMock())
    monkeypatch.setattr(educator, 'get_storage', lambda: storage)
    monkeypatch.setattr(educator_documents, 'educator_docx_to_pdf', AsyncMock(side_effect=RenderError('Unavailable')))
    keys, warnings = await educator._save_exports('plan', content, OWNER, uuid.uuid4())
    assert list(keys) == ['docx'] and 'PDF conversion is unavailable' in warnings[0]
    assert storage.put.await_count == 1


async def test_copilot_detail_keeps_printable_task_and_merges_downloads(monkeypatch):
    resource = saved_resource(content={'resource_type': 'copilot_task', 'printable_task': {'title': 'Reading task'},
        'export_keys': {'docx': 'task.docx'}, 'review_checks': {'export_keys': {'pdf': 'task.pdf'}}})
    storage = SimpleNamespace(signed_url=lambda key, filename: f'/signed/{key}')
    monkeypatch.setattr(educator, 'get_storage', lambda: storage)
    monkeypatch.setattr(educator, 'latest_job', AsyncMock(return_value=None))
    result = await educator.resource_out(AsyncMock(), resource)
    assert result['content']['printable_task']['title'] == 'Reading task'
    assert result['resource_type'] == 'copilot_task'
    assert result['downloads'] == {'docx': '/signed/task.docx', 'pdf': '/signed/task.pdf'}


async def test_approval_does_not_claim_regulatory_certification(monkeypatch):
    content = educator.offline_plan(request())
    row = LessonPlan(owner_id=OWNER, id=uuid.uuid4(), status='ready', version=2)
    educator.apply_plan(row, content, {'request': request().model_dump(mode='json')})
    db = AsyncMock()
    monkeypatch.setattr(educator, 'owned', AsyncMock(return_value=row))
    await educator.review_plan(db, SimpleNamespace(id=OWNER), row.id, 2, 'Checked examples.')
    assert row.status == 'reviewed'
    assert row.review_checks['alignment_status'] == 'teacher_review_required'
    assert row.review_checks['reviewed_version'] == 2 and not row.review_checks['teacher_review_required']


async def test_stale_plan_edits_are_rejected_before_ai_or_export(monkeypatch):
    row = LessonPlan(owner_id=OWNER, id=uuid.uuid4(), status='ready', version=2)
    monkeypatch.setattr(educator, 'owned', AsyncMock(return_value=row))
    with pytest.raises(AppError, match='changed'):
        await educator.update_plan(AsyncMock(), SimpleNamespace(id=OWNER), row.id, educator.offline_plan(request()), 1)


async def test_filtered_library_query_always_restricts_owner():
    db = AsyncMock()
    db.execute.return_value = rows_result([])
    await routes.list_resources(SimpleNamespace(id=OWNER), db, 'Science', 'university', 'british', None, 'en', 100)
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert str(OWNER) in sql and 'digital_resources.owner_id' in sql
    assert "education_stage = 'university'" in sql and "language = 'en'" in sql


def test_offline_examples_cannot_silently_claim_to_be_arabic(monkeypatch):
    monkeypatch.setattr(educator, 'get_ai', lambda: SimpleNamespace(mode='offline'))
    with pytest.raises(AppError, match='support English'):
        educator.validate_offline_language(request(language='ar'))


async def test_explicit_page_evidence_is_bounded_by_utf8_bytes_and_exact_pages(monkeypatch):
    b = book()
    req = request(source_file_ids=[SOURCE], source_page_ranges={str(SOURCE): [5, 6]})
    db = AsyncMock()
    db.execute.return_value = rows_result([SimpleNamespace(page=5, text='أ'*1000), SimpleNamespace(page=6, text='ب'*1000)])
    monkeypatch.setattr(educator, 'validate_sources', AsyncMock(return_value=[b]))
    monkeypatch.setattr(educator, 'SOURCE_BYTES', 2200)
    text, refs = await educator.source_evidence(db, SimpleNamespace(id=OWNER), req)
    assert len(text.encode()) <= 2200 and [ref['page_or_section'] for ref in refs] == ['5']
    query = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert 'BETWEEN 5 AND 6' in query and str(OWNER) in query


async def test_retry_reserves_again_only_for_failed_resource_and_keeps_options(monkeypatch):
    row = saved_resource('failed', content={'request': request('resource', chapter_count=2).model_dump(mode='json')})
    db = AsyncMock()
    job = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(educator, 'owned', AsyncMock(return_value=row))
    monkeypatch.setattr(educator, 'validate_sources', AsyncMock(return_value=[]))
    monkeypatch.setattr(educator, 'get_ai', lambda: SimpleNamespace(mode='live'))
    monkeypatch.setattr(educator.usage, 'lock_user', AsyncMock())
    monkeypatch.setattr(educator.usage, 'credit_cost', AsyncMock(return_value=8))
    monkeypatch.setattr(educator.usage, 'check', AsyncMock())
    monkeypatch.setattr(educator, 'enqueue', AsyncMock(return_value=job))
    monkeypatch.setattr(educator, 'run_inline_if_configured', AsyncMock())
    content = copy.deepcopy(row.content)
    assert await educator.retry_resource(db, SimpleNamespace(id=OWNER), row.id) == job.id
    assert row.status == 'queued' and row.content == content
    assert educator.enqueue.await_args.kwargs['credits_reserved'] == 8
    with pytest.raises(AppError, match='failed resources'):
        await educator.retry_resource(db, SimpleNamespace(id=OWNER), row.id)
    assert educator.enqueue.await_count == 1


def test_demo_model_is_preserved_as_existing_pipeline_payload():
    assert 'slide_payload' in DemoClass.__table__.c
    assert set(DemoClassContent.model_fields) == {'lesson_plan', 'hook', 'teacher_script', 'slide_payload'}


async def test_demo_editor_persistence_uses_the_existing_course_contract():
    from app.generation.specs import CoursePlan
    from app.models import Course, Lesson, Project

    db=AsyncMock()
    db.get.return_value=None
    db.add=MagicMock()
    row=DemoClass(id=uuid.uuid4(),owner_id=OWNER,title='Ecosystems',topic='Ecosystems',subject='Science',grade='6',curriculum='british',status='generating')
    req=request('demo')
    plan=educator.offline_plan(req)
    content=await educator.generate_demo(SimpleNamespace(mode='offline'),req,plan,'','',[],[],{},OWNER,uuid.uuid4())
    lesson,course,project=await educator.ensure_demo_lesson(db,row,req,plan,template_id=None,deck=content.slide_payload)
    assert isinstance(lesson,Lesson) and isinstance(course,Course) and isinstance(project,Project)
    assert lesson.owner_id==course.owner_id==project.owner_id==OWNER
    assert row.lesson_id==lesson.id
    assert db.flush.await_count == 3, 'Project, course and lesson must exist before foreign-key links are updated.'
    assert course.lecture_minutes==15
    assert CoursePlan.model_validate(course.plan).lectures[0].objectives==content.slide_payload.lesson_plan.objectives
    assert course.options['demo_class_id']==str(row.id)


async def test_demo_downloads_follow_the_current_edited_presentation(monkeypatch):
    from app.models import Lesson
    row=DemoClass(id=uuid.uuid4(),owner_id=OWNER,title='Demo',topic='Ecosystems',subject='Science',grade='6',curriculum='british',language='en',status='ready',version=1,error=None,review_checks={},hook={},teacher_script=[],slide_payload={},pptx_key='old.pptx',pdf_key=None,lesson_plan_id=None,lesson_id=uuid.uuid4())
    lesson=Lesson(id=row.lesson_id,owner_id=OWNER,pptx_key='latest.pptx',pdf_key='latest-slides.pdf',version=3)
    db=AsyncMock()
    db.get.return_value=lesson
    monkeypatch.setattr(educator,'latest_job',AsyncMock(return_value=None))
    monkeypatch.setattr(educator,'get_storage',lambda:SimpleNamespace(signed_url=lambda key,*args:key))
    result=await educator.detail(db,row)
    assert result['downloads']['pptx']=='latest.pptx'
    assert result['downloads']['slides_pdf']=='latest-slides.pdf'
    assert result['presentation_version']==3


async def test_cleanup_cannot_follow_model_supplied_or_other_owner_storage_keys(monkeypatch):
    row=saved_resource(content={'export_keys':{'pdf':'uploads/another-owner/source.pdf'},'resource_type':'copilot_task'},version=2)
    storage=SimpleNamespace(delete=AsyncMock())
    monkeypatch.setattr(educator,'get_storage',lambda:storage)
    await educator.cleanup_export_files(row)
    keys=[call.args[0] for call in storage.delete.await_args_list]
    assert keys and all(key.startswith('educator/'+str(OWNER)+'/') for key in keys)
    assert 'uploads/another-owner/source.pdf' not in keys


def test_preserved_template_cover_and_body_images_follow_the_actual_donor_mapping():
    from app.generation.specs import SlideSpec
    from app.generation.template_slots import prepare_template_images
    spec={'preserve_slots':True,'template_slots':[{'index':0,'slots':[{'role':'title'},{'role':'image'}]},
                                               {'index':1,'slots':[{'role':'title'},{'role':'body'}]},
                                               {'index':2,'slots':[{'role':'title'},{'role':'body'},{'role':'image'}]}]}
    slides=[SlideSpec(number=index,title='Mangroves',layout='cover' if index==1 else 'concept',purpose='Explain') for index in range(1,5)]
    prepare_template_images(slides,spec,topic='Mangroves',subject='Science')
    assert [slide.template_image_slot for slide in slides]==[True,False,True,True]
    assert slides[0].visual.kind=='image' and slides[0].visual.image_query
    assert all(slide.visual.image_query for slide in slides if slide.template_image_slot)


async def test_books_can_record_university_stage_and_clear_an_old_stage(monkeypatch):
    from app.api.routes import content
    from app.services import book_library
    db=AsyncMock()
    saved=SimpleNamespace(filename='Textbook.pdf',meta={'book':{'education_stage':'secondary','source_url':''}})
    monkeypatch.setattr(book_library,'owned_book',AsyncMock(return_value=saved))
    monkeypatch.setattr(book_library,'book_out',lambda book:{'metadata':book.meta['book']})
    fields={'title':'Mathematics','curriculum':'other','subject':'Mathematics','grade':'Undergraduate year 1','language':'en'}
    await content.update_book_metadata(uuid.uuid4(),content.BookMetadata(**fields,education_stage='university'),SimpleNamespace(id=OWNER),db)
    assert saved.meta['book']['education_stage']=='university'
    await content.update_book_metadata(uuid.uuid4(),content.BookMetadata(**fields,education_stage=None),SimpleNamespace(id=OWNER),db)
    assert saved.meta['book']['education_stage'] is None

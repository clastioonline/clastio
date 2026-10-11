"""Copilot privacy, reusable generation, class scope, spending and printable exports."""

import json
import re
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.api.routes import copilot_resources as routes
from app.core.errors import AppError, NotFound
from app.engine.exports import educator_documents as builders
from app.engine.qc.visual import RenderError
from app.generation.educator_specs import CopilotTask, SourceReference
from app.jobs.queue import PermanentJobError
from app.models import Conversation, ConversationMessage, DigitalResource, User
from app.services import copilot_resources as service


def database():
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.return_value = None
    db.add = Mock()
    return db


def rows(values):
    return SimpleNamespace(first=lambda: next(iter(values), None),
        scalars=lambda: SimpleNamespace(all=lambda: values,
        first=lambda: next(iter(values), None)))


def options(**changes):
    return {'request': 'Generate a differentiated reading task about UAE mangroves.',
            'topic': 'Mangrove ecosystems', 'subject': 'Science', 'grade': '6',
            'education_stage': 'secondary', 'curriculum': 'british', 'language': 'en',
            'framework': 'khda', 'source_file_ids': [], **changes}


def mock_usage(monkeypatch):
    quota = AsyncMock()
    consume = AsyncMock()
    monkeypatch.setattr(service.usage, 'lock_user', AsyncMock())
    monkeypatch.setattr(service.usage, 'credit_cost', AsyncMock(return_value=3))
    monkeypatch.setattr(service.usage, 'check', quota)
    monkeypatch.setattr(service.usage, 'consume', consume)
    return quota, consume


@pytest.mark.parametrize('status', ['ready', 'reviewed', 'queued', 'generating'])
async def test_cached_task_reuses_saved_resource_without_new_quota_or_model_calls(monkeypatch, status):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    saved = SimpleNamespace(id=uuid.uuid4(), status=status)
    existing_job = SimpleNamespace(id=uuid.uuid4()) if status in {'queued', 'generating'} else None
    db.execute.side_effect = [rows([]), rows([saved]), rows([existing_job] if existing_job else [])]
    quota, consume = mock_usage(monkeypatch)
    enqueue = AsyncMock()
    ai = Mock()
    monkeypatch.setattr(service, 'enqueue', enqueue)
    monkeypatch.setattr(service, 'get_ai', ai)
    row, job_id, cached = await service.create_task(db, user, options())
    assert row is saved and cached
    assert job_id == (existing_job.id if existing_job else None)
    quota.assert_not_awaited()
    consume.assert_not_awaited()
    enqueue.assert_not_awaited()
    ai.assert_not_called()
    queries = [str(call.args[0].compile(dialect=postgresql.dialect(),
        compile_kwargs={'literal_binds': True})) for call in db.execute.call_args_list]
    assert str(user.id) in queries[1] and 'digital_resources.owner_id' in queries[1]
    assert str(user.id) in queries[2] and 'generation_jobs.owner_id' in queries[2]


async def test_failed_cached_request_cannot_silently_charge_for_an_automatic_retry(monkeypatch):
    db = database()
    db.execute.side_effect = [rows([]), rows([SimpleNamespace(status='failed')])]
    quota, consume = mock_usage(monkeypatch)
    enqueue = AsyncMock()
    monkeypatch.setattr(service, 'enqueue', enqueue)
    with pytest.raises(AppError) as error:
        await service.create_task(db, SimpleNamespace(id=uuid.uuid4()), options())
    assert error.value.code == 'task_failed' and error.value.status == 409
    quota.assert_not_awaited()
    consume.assert_not_awaited()
    enqueue.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.parametrize('violation', ['missing', 'other_owner', 'wrong_kind', 'not_ready'])
async def test_selected_sources_must_be_private_owned_and_indexed_before_spending(monkeypatch, violation):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    identifier = uuid.uuid4()
    book = SimpleNamespace(id=identifier, owner_id=user.id, kind='source', status='ready')
    if violation == 'missing':
        book = None
    elif violation == 'other_owner':
        book.owner_id = uuid.uuid4()
    elif violation == 'wrong_kind':
        book.kind = 'template'
    else:
        book.status = 'processing'
    db.get.return_value = book
    quota, _ = mock_usage(monkeypatch)
    enqueue = AsyncMock()
    monkeypatch.setattr(service, 'enqueue', enqueue)
    with pytest.raises(AppError) as error:
        await service.create_task(db, user, options(source_file_ids=[str(identifier)]))
    assert isinstance(error.value, NotFound) if violation != 'not_ready' else error.value.status == 409
    quota.assert_not_awaited()
    enqueue.assert_not_awaited()
    db.execute.assert_not_awaited()


async def test_source_deduplication_uses_each_selected_file_once():
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    identifier = uuid.uuid4()
    book = SimpleNamespace(id=identifier, owner_id=user.id, kind='source', status='ready')
    db.get.return_value = book
    assert await service.owned_sources(db, user, [str(identifier), str(identifier)]) == [book]
    db.get.assert_awaited_once()


def test_task_cache_cannot_reuse_another_class_language_curriculum_or_changed_source():
    key = service.task_cache_key(options(), [('book', 'sha1')], {'sen_scaffolds': ['Visual supports']})
    changes = [{'grade': '5'}, {'subject': 'Mathematics'}, {'language': 'ar'}, {'curriculum': 'moe'},
               {'request': 'Create a different reading task.'}]
    for change in changes:
        assert service.task_cache_key(options(**change), [('book', 'sha1')],
            {'sen_scaffolds': ['Visual supports']}) != key
    assert service.task_cache_key(options(), [('book', 'sha2')], {'sen_scaffolds': ['Visual supports']}) != key
    assert service.task_cache_key(options(), [('book', 'sha1')], {'sen_scaffolds': ['Chunked text']}) != key


async def test_new_request_reserves_one_bounded_job_without_consuming_credits_early(monkeypatch):
    db = database()
    db.execute.side_effect = [rows([]), rows([])]
    quota, consume = mock_usage(monkeypatch)
    job = SimpleNamespace(id=uuid.uuid4())
    enqueue = AsyncMock(return_value=job)
    inline = AsyncMock()
    monkeypatch.setattr(service, 'enqueue', enqueue)
    monkeypatch.setattr(service, 'run_inline_if_configured', inline)
    user = SimpleNamespace(id=uuid.uuid4())
    row, job_id, cached = await service.create_task(db, user, options())
    assert row.owner_id == user.id and row.content['resource_type'] == 'copilot_task'
    assert row.content['options']['grade'] == '6'
    assert not cached and job_id == job.id
    quota.assert_awaited_once_with(db, user, 'credits', 3, jobs=1)
    assert enqueue.call_args.kwargs['credits_reserved'] == 3
    assert enqueue.call_args.kwargs['max_attempts'] == 1
    assert enqueue.call_args.kwargs['owner_id'] == user.id
    consume.assert_not_awaited()
    db.commit.assert_awaited_once()
    inline.assert_awaited_once_with([job.id])


async def test_printable_history_query_is_owner_scoped_and_excludes_generic_guides(monkeypatch):
    from app.services import educator
    db = database()
    identifier = uuid.uuid4()
    saved = SimpleNamespace(id=identifier)
    db.execute.return_value = rows([saved])
    serializer = AsyncMock(return_value={'id': str(identifier)})
    monkeypatch.setattr(educator, 'resource_out', serializer)
    user = SimpleNamespace(id=uuid.uuid4())
    assert await routes.printable_history(user, db) == {'items': [{'id': str(identifier)}]}
    serializer.assert_awaited_once_with(db, saved)
    query = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect(),
        compile_kwargs={'literal_binds': True}))
    assert 'digital_resources.owner_id' in query and str(user.id) in query
    assert 'resource_type' in query and 'copilot_task' in query
    assert 'LIMIT 50' in query


async def test_create_endpoint_awaits_resource_serialization_and_returns_reused_job(monkeypatch):
    from app.services import educator
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    row = SimpleNamespace(id=uuid.uuid4())
    job_id = uuid.uuid4()
    creator = AsyncMock(return_value=(row, job_id, True))
    serializer = AsyncMock(return_value={'id': str(row.id), 'title': 'Saved reading task'})
    conversation = SimpleNamespace(id=uuid.uuid4())
    prepare = AsyncMock(return_value=(conversation, []))
    record = AsyncMock()
    monkeypatch.setattr(service, 'create_task', creator)
    monkeypatch.setattr(service, 'prepare_conversation', prepare)
    monkeypatch.setattr(service, 'record_queued_response', record)
    monkeypatch.setattr(educator, 'resource_out', serializer)
    body = routes.CopilotRequest.model_validate(options())
    result = await routes.create_printable(body, user, db)
    assert result == {'resource': {'id': str(row.id), 'title': 'Saved reading task'},
                      'job_id': str(job_id), 'cached': True, 'conversation_id': str(conversation.id)}
    creator.assert_awaited_once_with(db, user, {**body.model_dump(mode='json'),
        'conversation_id': str(conversation.id), '_conversation_context': []})
    prepare.assert_awaited_once_with(db, user, body)
    record.assert_awaited_once_with(db, conversation, row, True)
    serializer.assert_awaited_once_with(db, row)
    db.refresh.assert_awaited_once_with(row)


@pytest.mark.parametrize('change', [{'grade': None}, {'grade': '   '}, {'education_stage': 'invalid'},
                                   {'source_file_ids': ['not-a-uuid']}])
def test_invalid_school_task_scope_is_rejected_at_the_endpoint(change):
    with pytest.raises(ValidationError):
        routes.CopilotRequest.model_validate(options(**change))


def test_university_task_can_omit_school_grade():
    body = routes.CopilotRequest.model_validate(options(education_stage='university', grade=None,
        framework='not_specified'))
    assert body.grade is None


def test_offline_mangrove_sample_keeps_requested_scope_and_clearly_marks_unverified_sample():
    task = service.offline_task(options())
    assert task.subject == 'Science' and task.grade == '6'
    assert task.curriculum == 'british' and task.language == 'en'
    assert 'Mangroves' in task.reading_text and 'UAE mangrove habitat' in task.reading_text
    assert task.review_checks.alignment_status == 'teacher_review_required'
    assert any('offline sample' in gap.lower() for gap in task.review_checks.evidence_gaps)
    assert not task.source_references
    assert task.support.sen[0].scaffold and task.support.ell[0].scaffold


def test_arabic_offline_task_contains_arabic_content_and_remains_flagged_as_a_sample():
    task = service.offline_task(options(language='ar'))
    assert task.language == 'ar'
    assert re.search(r'[\u0600-\u06FF]', task.reading_text)
    assert re.search(r'[\u0600-\u06FF]', task.instructions)
    assert all(re.search(r'[\u0600-\u06FF]', question.question) for question in task.questions)
    assert any('offline' in gap.lower() or 'دون اتصال' in gap for gap in task.review_checks.evidence_gaps)


def setup_handler(monkeypatch, *, mode='offline', pdf_failure=False, source_ids=None):
    from app.services import educator
    db = database()
    user = SimpleNamespace(id=uuid.uuid4(), status='active')
    identifier = uuid.uuid4()
    selected_ids = source_ids or []
    opts = options(source_file_ids=[str(value) for value in selected_ids])
    row = SimpleNamespace(id=identifier, owner_id=user.id, status='queued', error=None,
        topic=opts['topic'], subject=opts['subject'], content={'options': opts}, pdf_key=None)
    books = {value: SimpleNamespace(id=value, owner_id=user.id, kind='source', status='ready', sha256='sha')
             for value in selected_ids}
    async def get(model, key):
        if model is DigitalResource:
            return row
        if model is User:
            return user
        return books.get(key)
    db.get.side_effect = get
    db.execute.return_value = rows([])
    monkeypatch.setattr(service, 'get_sessionmaker', lambda: lambda: db)
    context = AsyncMock(return_value=('Saved teacher reference facts', {}))
    monkeypatch.setattr(service, 'build_context', context)
    evidence = AsyncMock(return_value=('Saved teacher textbook excerpts', [
        {'title': 'Selected book', 'url_or_file_id': str(source_id), 'page_or_section': '12',
         'relevance': 'Source of the habitat explanation'} for source_id in selected_ids]))
    monkeypatch.setattr(educator, 'source_evidence', evidence)
    task = service.offline_task(opts)
    ai = SimpleNamespace(mode=mode, structured=AsyncMock(return_value=task))
    monkeypatch.setattr(service, 'get_ai', lambda: ai)
    docx = Mock(return_value=b'PK teacher document')
    pdf = AsyncMock(side_effect=RenderError('Conversion unavailable')) if pdf_failure else AsyncMock(return_value=b'%PDF-1.7 fixture')
    monkeypatch.setattr(builders, 'build_task_docx', docx)
    monkeypatch.setattr(builders, 'educator_docx_to_pdf', pdf)
    storage = SimpleNamespace(put=AsyncMock())
    monkeypatch.setattr(service, 'get_storage', lambda: storage)
    _, consume = mock_usage(monkeypatch)
    ctx = SimpleNamespace(job_id=uuid.uuid4(), owner_id=user.id,
        payload={'resource_id': str(identifier), 'cost': 3}, progress=AsyncMock())
    return SimpleNamespace(db=db, user=user, row=row, books=books, context=context, evidence=evidence, task=task,
        ai=ai, docx=docx, pdf=pdf, storage=storage, consume=consume, ctx=ctx)


async def test_offline_generation_persists_printable_content_and_exports_without_paid_calls(monkeypatch):
    state = setup_handler(monkeypatch)
    assert await service.handle_task(state.ctx) == {'resource_id': str(state.row.id)}
    assert state.row.status == 'ready' and state.row.pdf_key.endswith('.pdf')
    content = CopilotTask.model_validate(state.row.content['printable_task'])
    assert content.reading_text and content.questions[0].expected_answer
    assert content.review_checks.evidence_gaps
    assert state.row.content['resource_type'] == 'copilot_task'
    assert state.row.chapters[0]['reading_text'] == content.reading_text
    state.ai.structured.assert_not_awaited()
    assert state.storage.put.await_count == 2
    state.consume.assert_awaited_once_with(state.db, state.user.id, 3, 'copilot_resource', str(state.row.id))


async def test_pdf_failure_keeps_docx_and_preview_ready_with_an_explicit_warning(monkeypatch):
    state = setup_handler(monkeypatch, pdf_failure=True)
    await service.handle_task(state.ctx)
    assert state.row.status == 'ready' and state.row.pdf_key is None
    assert set(state.row.content['export_keys']) == {'docx'}
    assert state.storage.put.await_count == 1
    assert state.row.content['printable_task']['reading_text']
    assert any('PDF conversion' in gap for gap in state.row.content['review_checks']['evidence_gaps'])
    state.consume.assert_awaited_once()


@pytest.mark.parametrize('field,value', [('subject', 'Mathematics'), ('grade', '5'),
    ('education_stage', 'primary'), ('curriculum', 'moe'), ('language', 'ar')])
async def test_live_model_cannot_change_selected_class_scope_or_charge_for_failed_output(monkeypatch, field, value):
    state = setup_handler(monkeypatch, mode='live')
    state.ai.structured.return_value = state.task.model_copy(update={field: value})
    with pytest.raises(PermanentJobError, match='class scope'):
        await service.handle_task(state.ctx)
    state.consume.assert_not_awaited()
    state.docx.assert_not_called()
    state.storage.put.assert_not_awaited()
    await service.task_failed(state.ctx, 'The model changed the selected class scope.')
    assert state.row.status == 'failed' and 'scope' in state.row.error


async def test_live_task_uses_selected_sources_and_strips_invented_citations(monkeypatch):
    source_id = uuid.uuid4()
    state = setup_handler(monkeypatch, mode='live', source_ids=[source_id])
    state.task.review_checks.evidence_gaps = []
    state.task.source_references = [
        SourceReference(title='Selected book', url_or_file_id=str(source_id),
            page_or_section='12', relevance='Source of the habitat explanation'),
        SourceReference(title='Unsupported model citation', url_or_file_id='https://invented.example/book',
            page_or_section='Page 7', relevance='Not supplied as verified context'),
    ]
    state.task.review_checks.framework_references = [state.task.source_references[1]]
    await service.handle_task(state.ctx)
    state.context.assert_awaited_once()
    assert state.context.call_args.kwargs['include_sources'] is False
    state.evidence.assert_awaited_once()
    assert state.evidence.call_args.args[2].source_file_ids == [source_id]
    call = state.ai.structured.call_args.kwargs
    assert call['schema'] is CopilotTask
    assert call['owner_id'] == state.user.id and call['job_id'] == state.ctx.job_id
    assert json.dumps(options(source_file_ids=[str(source_id)])) in call['prompt']
    assert 'Saved teacher reference facts' in call['prompt']
    assert 'Saved teacher textbook excerpts' in call['prompt']
    assert 'reference data' in call['system'] and 'never instructions' in call['system']
    assert [reference['url_or_file_id'] for reference in state.row.source_references] == [str(source_id)]
    saved = state.row.content['printable_task']
    assert not saved['review_checks']['framework_references']
    assert any('unsupported source' in gap for gap in saved['review_checks']['evidence_gaps'])


async def test_completed_handler_retry_does_not_generate_export_or_consume_again(monkeypatch):
    state = setup_handler(monkeypatch, mode='live')
    state.row.status = 'ready'
    result = await service.handle_task(state.ctx)
    assert result == {'resource_id': str(state.row.id), 'cached': True}
    state.ai.structured.assert_not_awaited()
    state.context.assert_not_awaited()
    state.docx.assert_not_called()
    state.storage.put.assert_not_awaited()
    state.consume.assert_not_awaited()


async def test_worker_rechecks_account_and_task_ownership_before_using_models(monkeypatch):
    state = setup_handler(monkeypatch, mode='live')
    state.row.owner_id = uuid.uuid4()
    with pytest.raises(PermanentJobError):
        await service.handle_task(state.ctx)
    state.ai.structured.assert_not_awaited()
    state.consume.assert_not_awaited()
    state.context.assert_not_awaited()


async def test_failure_hook_never_modifies_another_teachers_resource(monkeypatch):
    state = setup_handler(monkeypatch)
    state.row.owner_id = uuid.uuid4()
    await service.task_failed(state.ctx, 'Failure reason')
    assert state.row.status == 'queued' and state.row.error is None
    state.db.commit.assert_not_awaited()


async def test_explicit_failed_task_retry_routes_to_copilot_and_reserves_only_one_job(monkeypatch):
    from app.services import educator
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    saved = SimpleNamespace(id=uuid.uuid4(), status='failed', error='Previous generation failed',
        content={'resource_type': 'copilot_task', 'options': options()})
    owned = AsyncMock(return_value=saved)
    enqueue = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    inline = AsyncMock()
    monkeypatch.setattr(educator, 'owned', owned)
    monkeypatch.setattr(educator, 'enqueue', enqueue)
    monkeypatch.setattr(educator, 'run_inline_if_configured', inline)
    quota, consume = mock_usage(monkeypatch)
    job_id = await educator.retry_resource(db, user, saved.id)
    assert saved.status == 'queued' and saved.error is None
    assert job_id == enqueue.return_value.id
    enqueue.assert_awaited_once_with(db, 'copilot_resource', {'resource_id': str(saved.id), 'cost': 3},
        owner_id=user.id, credits_reserved=3, max_attempts=1)
    quota.assert_awaited_once_with(db, user, 'credits', 3, jobs=1)
    consume.assert_not_awaited()

    owned.assert_awaited_once_with(db, DigitalResource, saved.id, user.id, for_update=True)
    with pytest.raises(AppError) as error:
        await educator.retry_resource(db, user, saved.id)
    assert error.value.status == 409 and error.value.code == 'not_failed'
    assert enqueue.await_count == 1 and quota.await_count == 1
    consume.assert_not_awaited()


@pytest.mark.parametrize('change', [
    {'request': '      '}, {'subject': '   '}, {'curriculum': '   '},
    {'education_stage': 'university', 'grade': None, 'framework': 'khda'},
    {'source_page_ranges': {str(uuid.uuid4()): [1, 2]}},
    {'invented_field': 'Ignored fields must not silently change a task'},
])
def test_copilot_rejects_ambiguous_scope_and_unselected_page_ranges(change):
    with pytest.raises(ValidationError):
        routes.CopilotRequest.model_validate(options(**change))


def test_copilot_cache_reuses_across_conversations_but_distinguishes_followup_context():
    first = options(conversation_id=str(uuid.uuid4()), _conversation_context=[])
    second = options(conversation_id=str(uuid.uuid4()), _conversation_context=[])
    assert service.task_cache_key(first, [], {}) == service.task_cache_key(second, [], {})
    second['_conversation_context'] = [{'role': 'reference', 'content': 'Earlier reading task about mangroves.'}]
    assert service.task_cache_key(first, [], {}) != service.task_cache_key(second, [], {})


@pytest.mark.parametrize('violation', ['other_owner', 'legacy_channel', 'missing'])
async def test_copilot_conversation_ownership_checked_before_reading_messages(violation):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(id=uuid.uuid4(), owner_id=user.id, channel='copilot')
    if violation == 'other_owner':
        conversation.owner_id = uuid.uuid4()
    elif violation == 'legacy_channel':
        conversation.channel = 'web'
    else:
        conversation = None
    db.get.return_value = conversation
    with pytest.raises(NotFound):
        await service.conversation_detail(db, user, uuid.uuid4())
    db.execute.assert_not_awaited()
    db.add.assert_not_called()


async def test_new_copilot_conversation_saves_a_user_message_and_returns_empty_context(monkeypatch):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(service.usage, 'lock_user', AsyncMock())
    body = routes.CopilotRequest.model_validate(options())
    conversation, history = await service.prepare_conversation(db, user, body)
    assert conversation.owner_id == user.id and conversation.channel == 'copilot'
    assert history == [] and conversation.id is not None
    saved = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(saved[0], Conversation)
    assert isinstance(saved[1], ConversationMessage)
    assert saved[1].conversation_id == conversation.id and saved[1].content == body.request
    assert saved[1].role == 'user'


async def test_followup_copilot_context_includes_only_owned_latest_task(monkeypatch):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(id=uuid.uuid4(), owner_id=user.id, channel='copilot')
    resource = SimpleNamespace(id=uuid.uuid4(), owner_id=user.id, status='ready',
        content={'printable_task': {'reading_text': 'Earlier mangrove reading', 'support': {'core': 'Explain the food chain'}}})
    message = SimpleNamespace(role='assistant', content='A task is ready.',
        actions=[{'type': 'copilot_resource', 'resource_id': str(resource.id)}])
    db.get.side_effect = [conversation, resource]
    db.execute.side_effect = [rows([]), rows([message])]
    monkeypatch.setattr(service.usage, 'lock_user', AsyncMock())
    body = routes.CopilotRequest.model_validate(options(conversation_id=str(conversation.id), request='Make it easier.'))
    saved_conversation, history = await service.prepare_conversation(db, user, body)
    assert saved_conversation is conversation
    assert history[0]['content'] == 'A task is ready.'
    assert 'Earlier mangrove reading' in history[1]['content']
    assert history[1]['role'] == 'reference'
    assert db.add.call_args.args[0].role == 'user'


async def test_copilot_does_not_overlap_paid_generation_in_same_conversation(monkeypatch):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(id=uuid.uuid4(), owner_id=user.id, channel='copilot')
    db.get.return_value = conversation
    db.execute.return_value = rows([uuid.uuid4()])
    monkeypatch.setattr(service.usage, 'lock_user', AsyncMock())
    with pytest.raises(AppError) as error:
        await service.prepare_conversation(db, user, routes.CopilotRequest.model_validate(
            options(conversation_id=str(conversation.id))))
    assert error.value.code == 'reply_pending'
    db.add.assert_not_called()


async def test_cached_ready_answer_is_stored_in_current_copilot_conversation():
    db = database()
    conversation = SimpleNamespace(id=uuid.uuid4())
    resource = SimpleNamespace(id=uuid.uuid4(), title='Mangrove task', status='ready')
    await service.record_queued_response(db, conversation, resource, True)
    message = db.add.call_args.args[0]
    assert message.role == 'assistant' and message.conversation_id == conversation.id
    assert message.actions[0]['resource_id'] == str(resource.id)
    assert message.actions[0]['href'] == f'/copilot?id={resource.id}'
    assert 'ready' in message.content
    db.commit.assert_awaited_once()


async def test_unprovided_page_is_removed_even_when_source_book_is_selected(monkeypatch):
    source_id = uuid.uuid4()
    state = setup_handler(monkeypatch, mode='live', source_ids=[source_id])
    state.task.source_references = [SourceReference(title='Selected book', url_or_file_id=str(source_id),
        page_or_section='13', relevance='Page not supplied to the model')]
    await service.handle_task(state.ctx)
    assert not state.row.source_references
    assert any('unsupported source' in gap for gap in state.row.content['review_checks']['evidence_gaps'])


async def test_completed_generation_adds_persistent_response_to_owned_conversation(monkeypatch):
    state = setup_handler(monkeypatch)
    conversation = SimpleNamespace(id=uuid.uuid4(), owner_id=state.user.id, channel='copilot')
    state.row.content['options']['conversation_id'] = str(conversation.id)
    original_get = state.db.get.side_effect
    async def get(model, key):
        if model is Conversation:
            return conversation
        return await original_get(model, key)
    state.db.get.side_effect = get
    await service.handle_task(state.ctx)
    message = state.db.add.call_args.args[0]
    assert isinstance(message, ConversationMessage)
    assert message.conversation_id == conversation.id and message.role == 'assistant'
    assert 'answer key' in message.content
    assert message.actions[0]['resource_id'] == str(state.row.id)


async def test_worker_never_consumes_another_teachers_conversation(monkeypatch):
    state = setup_handler(monkeypatch, mode='live')
    conversation = SimpleNamespace(id=uuid.uuid4(), owner_id=uuid.uuid4(), channel='copilot')
    state.row.content['options']['conversation_id'] = str(conversation.id)
    original_get = state.db.get.side_effect
    async def get(model, key):
        if model is Conversation:
            return conversation
        return await original_get(model, key)
    state.db.get.side_effect = get
    with pytest.raises(NotFound):
        await service.handle_task(state.ctx)
    state.ai.structured.assert_not_awaited()
    state.context.assert_not_awaited()
    state.evidence.assert_not_awaited()
    state.consume.assert_not_awaited()


async def test_failure_hook_preserves_ready_saved_task(monkeypatch):
    state = setup_handler(monkeypatch)
    state.row.status = 'ready'
    await service.task_failed(state.ctx, 'Job bookkeeping failed after generation')
    assert state.row.status == 'ready' and state.row.error is None
    state.db.commit.assert_not_awaited()


def test_multilingual_context_is_bounded_by_bytes_without_splitting_unicode():
    result = service.bounded_text('القرم' * 5000, 16000)
    assert len(result.encode('utf-8')) <= 16000
    assert '\ufffd' not in result

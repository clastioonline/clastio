"""Source reuse, complete chapter allocation and bounded slide generation contracts."""
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from test_content_quality import budgets, deck, request

from app.ai import budget
from app.ai.base import Usage
from app.ai.compatible_provider import CompatibleProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.core.errors import AppError, NotFound
from app.generation import lesson_workflow, offline, pipeline
from app.generation.quality import ContentQualityError
from app.generation.specs import CoursePlan
from app.services import book_library, chapter_knowledge


def database():
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.return_value = None
    db.add = Mock()
    return db


def rows(values):
    return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: values, first=lambda: next(iter(values), None)))


async def test_saved_book_url_skips_download_and_reindex(monkeypatch):
    db = database()
    book = SimpleNamespace(status='ready')
    db.execute.return_value = rows([book])
    download = AsyncMock()
    monkeypatch.setattr(book_library, 'download_public_image', download)
    saved, job = await book_library.import_pdf(db, SimpleNamespace(id=uuid.uuid4()), url='https://publisher.example/book.pdf',
        title='Book', metadata={}, rights_confirmed=True, max_bytes=1000)
    assert saved is book and job is None
    download.assert_not_awaited()


async def test_rights_and_pdf_validation_precede_storage(monkeypatch):
    db = database()
    db.execute.return_value = rows([])
    download = AsyncMock(return_value=b'<html>Login</html>')
    store = AsyncMock()
    monkeypatch.setattr(book_library, 'download_public_image', download)
    monkeypatch.setattr(book_library, 'store_upload', store)
    user = SimpleNamespace(id=uuid.uuid4())
    args = dict(url='https://publisher.example/book.pdf', title='Book', metadata={}, max_bytes=1000)
    with pytest.raises(AppError, match='Confirm'):
        await book_library.import_pdf(db, user, rights_confirmed=False, **args)
    download.assert_not_awaited()
    with pytest.raises(AppError, match='direct'):
        await book_library.import_pdf(db, user, rights_confirmed=True, **args)
    store.assert_not_awaited()


async def test_book_owner_cannot_access_another_library():
    db = database()
    db.get.return_value = SimpleNamespace(owner_id=uuid.uuid4(), kind='source')
    with pytest.raises(NotFound):
        await book_library.owned_book(db, SimpleNamespace(id=uuid.uuid4()), uuid.uuid4())


async def test_discovery_cache_does_not_call_search(monkeypatch):
    db = database()
    db.get.return_value = SimpleNamespace(value={'results': 'Saved official sources'})
    ai = SimpleNamespace(text=AsyncMock())
    monkeypatch.setattr('app.ai.service.get_ai', lambda: ai)
    result = await book_library.discover(db, SimpleNamespace(id=uuid.uuid4()), 'UAE grade 10 mathematics')
    assert result['cached'] and result['results'] == 'Saved official sources'
    ai.text.assert_not_awaited()


async def test_chapter_cache_skips_retrieval_and_all_models(monkeypatch):
    db = database()
    cached = {'topics': [{'title': 'Equations'}], 'missing_material': []}
    db.get.return_value = SimpleNamespace(value=cached)
    monkeypatch.setattr(chapter_knowledge, 'get_sessionmaker', lambda: lambda: db)
    ai = SimpleNamespace(text=AsyncMock(), structured=AsyncMock())
    monkeypatch.setattr(chapter_knowledge, 'get_ai', lambda: ai)
    course = SimpleNamespace(options={}, owner_id=uuid.uuid4(), topic='Algebra', grade='10',
                             subject='Mathematics', curriculum='moe', language='en')
    assert await chapter_knowledge.prepare(course, '') == cached
    ai.text.assert_not_awaited()
    ai.structured.assert_not_awaited()


async def test_selected_pdf_pages_used_without_live_search(monkeypatch):
    db = database()
    book = SimpleNamespace(id=uuid.uuid4(), sha256='sha', filename='algebra.pdf')
    db.execute.side_effect = [rows([book]), rows([SimpleNamespace(page=12, text='A variable represents an unknown value.')]), None]
    monkeypatch.setattr(chapter_knowledge, 'get_sessionmaker', lambda: lambda: db)
    pack = chapter_knowledge.ChapterPack(topics=[chapter_knowledge.ChapterTopic(title='Variables', explanation='An unknown value')])
    ai = SimpleNamespace(mode='live', text=AsyncMock(), structured=AsyncMock(return_value=pack))
    monkeypatch.setattr(chapter_knowledge, 'get_ai', lambda: ai)
    course = SimpleNamespace(options={'source_file_ids':[str(book.id)], 'source_page_ranges':{str(book.id):[12,15]}},
        owner_id=uuid.uuid4(), topic='Algebra', grade='10', subject='Mathematics', curriculum='moe', language='en')
    await chapter_knowledge.prepare(course, '')
    ai.text.assert_not_awaited()
    assert '[algebra.pdf PDF p.12]' in ai.structured.call_args.kwargs['prompt']
    sql = str(db.execute.call_args_list[1].args[0])
    assert 'BETWEEN' in sql
    db.commit.assert_awaited_once()


def generation_fixture(flexible=False):
    req = {**request(), 'workflow_version':2, 'flexible_slides':flexible}
    course = offline.course_plan(req, CoursePlan)
    existing = deck()
    material = lesson_workflow.LessonMaterial(lesson_plan=existing.lesson_plan,
        blocks=[lesson_workflow.TeachingBlock(number=s.number, title=s.title, purpose=s.purpose,
                    definition='Addition combines quantities.', explanation='A full student explanation',
                    worked_example='2 + 3 = 5', student_question='What is 2 + 3?', expected_answer='5') for s in existing.slides])
    outline = pipeline.DeckOutline(slides=[pipeline.PlannedSlide(number=s.number, title=s.title, layout=s.layout,
                    purpose=s.purpose, teaching_content='Specific example', minutes=4) for s in existing.slides])
    batches = [lesson_workflow.SlideBatch(slides=existing.slides[start:start+3]) for start in range(0,10,3)]
    return req, course, material, outline, batches


async def test_teaching_content_then_layout_then_three_slide_batches():
    req, course, material, outline, batches = generation_fixture()
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[material,outline,*batches]))
    result = await pipeline.generate_deck(ai, req=req, context_text='Book facts', course=course,
                                         lecture_number=1, budgets=budgets())
    tasks = [call.kwargs['task'] for call in ai.structured.call_args_list]
    assert tasks == ['lesson_teaching','lesson_outline'] + ['lesson_deck_batch']*4
    assert len(result.slides) == 10 and sum(s.timing_minutes for s in result.slides) == pytest.approx(40)
    for call in ai.structured.call_args_list[2:]:
        payload = json.loads(call.kwargs['prompt'].split('\nReturn only')[0])
        assert len(payload['approved_content']) <= 3
        assert all(block['worked_example'] == '2 + 3 = 5' for block in payload['approved_content'])


async def test_invalid_batch_retries_once_then_prevents_publication():
    req, course, material, outline, batches = generation_fixture()
    bad = batches[0].model_copy(deep=True)
    bad.slides[0].number = 999
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[material,outline,bad,bad]))
    with pytest.raises(ContentQualityError, match='sequence/layout'):
        await pipeline.generate_deck(ai, req=req, context_text='', course=course,lecture_number=1,budgets=budgets())
    assert ai.structured.await_count == 4
    assert ai.structured.call_args.kwargs['cache'] is False


def test_missing_chapter_topic_cannot_pass_plan():
    req = request()
    plan = offline.course_plan(req, CoursePlan)
    assert any('Equations' in issue for issue in pipeline.course_structure_issues(plan,{**req,'chapter_topics':['Equations']}))
    plan.lectures[0].key_concepts.append('Equations')
    assert not pipeline.course_structure_issues(plan,{**req,'chapter_topics':['Equations']})


def test_flexible_bounds_and_no_silent_content_clipping():
    assert lesson_workflow.slide_bounds({'slides_per_lecture':12,'flexible_slides':True}) == (9,15)
    assert lesson_workflow.slide_bounds({'slides_per_lecture':30,'flexible_slides':True}) == (27,30)
    slide = deck().slides[1]
    slide.bullets = ['A complete definition with several necessary explanatory words.']
    assert pipeline.enforce_budgets(slide, {'bullet_max_words':2}).bullets == slide.bullets


def test_search_provider_reported_cost_includes_request_fees():
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=100, cost=0.007))
    usage = OpenRouterProvider._usage(response)
    assert usage.reported_cost_usd == 0.007
    assert budget.price({},usage) == Decimal('0.007')
    provider = object.__new__(CompatibleProvider)
    provider.name = 'perplexity'
    response.usage.cost = {'total_cost':0.008}
    assert provider._usage(response).reported_cost_usd == 0.008
    with pytest.raises(ValueError):
        budget.price({},Usage(reported_cost_usd=float('nan')))


async def test_flexible_workflow_preserves_more_slides_than_target():
    req, course, material, outline, batches = generation_fixture(True)
    req['slides_per_lecture'] = 8
    ai = SimpleNamespace(mode='live', structured=AsyncMock(side_effect=[material,outline,*batches]))
    result = await pipeline.generate_deck(ai,req=req,context_text='',course=course,lecture_number=1,budgets=budgets())
    assert len(result.slides) == 10


async def test_empty_teaching_material_stops_before_paid_formatting():
    req, course, material, _, _ = generation_fixture()
    material.blocks[1].explanation = ''
    material.blocks[1].worked_example = ''
    material.blocks[1].student_question = ''
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=material))
    with pytest.raises(ContentQualityError,match='Incomplete teaching'):
        await pipeline.generate_deck(ai,req=req,context_text='',course=course,lecture_number=1,budgets=budgets())
    assert ai.structured.await_count == 1


async def test_multiple_arabic_sources_obey_one_byte_allowance(monkeypatch):
    db = database()
    books = [SimpleNamespace(id=uuid.uuid4(), sha256=str(i), filename=f'book{i}.pdf') for i in range(3)]
    db.execute.side_effect = [rows(books), None]
    monkeypatch.setattr(chapter_knowledge,'get_sessionmaker',lambda:lambda:db)
    retrieve = AsyncMock(side_effect=[[{'file':book.filename,'page':1,'text':'شرح ' * 4000}] for book in books])
    monkeypatch.setattr('app.services.sources.retrieve',retrieve)
    pack = chapter_knowledge.ChapterPack(topics=[chapter_knowledge.ChapterTopic(title='Variables',explanation='Unknown values')])
    ai = SimpleNamespace(mode='live',text=AsyncMock(),structured=AsyncMock(return_value=pack))
    monkeypatch.setattr(chapter_knowledge,'get_ai',lambda:ai)
    course = SimpleNamespace(options={'source_file_ids':[str(book.id) for book in books]}, owner_id=uuid.uuid4(),
                             topic='Algebra',grade='10',subject='Mathematics',curriculum='moe',language='ar')
    result = await chapter_knowledge.prepare(course,'')
    material = ai.structured.call_args.kwargs['prompt'].split('BOOK MATERIAL:\n')[1].split('\nRESEARCH:')[0]
    assert len(material.encode()) <= 40000
    assert any('allowance' in warning for warning in result['missing_material'])
    ai.text.assert_not_awaited()


async def test_ready_source_is_not_embedded_again(monkeypatch):
    from app.services import sources
    db = database()
    db.get.return_value = SimpleNamespace(status='ready')
    db.execute.return_value = SimpleNamespace(first=lambda: (uuid.uuid4(),))
    monkeypatch.setattr(sources,'get_sessionmaker',lambda:lambda:db)
    storage = SimpleNamespace(get=AsyncMock())
    ai = SimpleNamespace(embed=AsyncMock())
    monkeypatch.setattr(sources,'get_storage',lambda:storage)
    monkeypatch.setattr(sources,'get_ai',lambda:ai)
    assert await sources.index_source(uuid.uuid4()) == {'cached':True}
    storage.get.assert_not_awaited()
    ai.embed.assert_not_awaited()


async def test_pdf_index_preserves_physical_page_count_and_bookmarks(monkeypatch):
    import pymupdf

    from app.services import sources
    with pymupdf.open() as document:
        document.new_page()
        document.new_page().insert_text((50,50),'Variables represent unknown values.')
        document.new_page().insert_text((50,50),'Equations express equality.')
        document.set_toc([[1,'Variables',2],[1,'Equations',3]])
        data = document.tobytes()
    db = database()
    file = SimpleNamespace(id=uuid.uuid4(),owner_id=uuid.uuid4(),storage_key='book.pdf',status='queued',meta={})
    db.get.return_value = file
    monkeypatch.setattr(sources,'get_sessionmaker',lambda:lambda:db)
    monkeypatch.setattr(sources,'get_storage',lambda:SimpleNamespace(get=AsyncMock(return_value=data)))
    ai = SimpleNamespace(embed=AsyncMock(side_effect=lambda values,**kwargs:[[0.0]*1536 for _ in values]))
    monkeypatch.setattr(sources,'get_ai',lambda:ai)
    async def native_only(data,pages,owner):
        return pages
    monkeypatch.setattr('app.services.pdf_ingestion.extract_scanned',native_only)
    await sources.index_source(file.id)
    assert file.page_count == 3
    assert file.meta['chapters'] == [{'title':'Variables','start':2,'end':2},{'title':'Equations','start':3,'end':3}]
    assert file.status == 'ready'


async def test_slide_citations_use_only_approved_block_references():
    req, course, material, outline, batches = generation_fixture()
    source = {'file_id':str(uuid.uuid4()),'file':'Algebra.pdf','page':12}
    req['source_catalog'] = {'[Algebra.pdf PDF p.12]':source}
    material.blocks[1].source_references = ['[Algebra.pdf PDF p.12]','invented page']
    ai = SimpleNamespace(mode='live',structured=AsyncMock(side_effect=[material,outline,*batches]))
    result = await pipeline.generate_deck(ai,req=req,context_text='',course=course,lecture_number=1,budgets=budgets())
    assert result.slides[1].sources == [source]
    assert all(not slide.sources for index,slide in enumerate(result.slides) if index != 1)

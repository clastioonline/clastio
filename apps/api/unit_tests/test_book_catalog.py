"""Prevent curriculum substitutions, private upload exposure and repeat catalogue indexing."""
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql
from starlette.exceptions import HTTPException
from starlette.requests import Request
from test_book_workflow import database, rows

from app.api.routes import content
from app.core.deps import require
from app.core.errors import AppError, NotFound
from app.models import SourceChunk
from app.services import book_catalog, book_library


def discovered(**patch):
    return book_library.DiscoveredBook(**{
        'title':'UAE Mathematics', 'curriculum':'moe','publisher':'UAE Ministry of Education',
        'subject':'Mathematics','grade':'10','language':'en','edition':'2026–2027',
        'source_url':'https://minhaji.moe.gov.ae/','pdf_url':None,'access':'school_login',**patch})


def test_directory_covers_all_app_subjects_without_mixing_ncert():
    for curriculum in book_catalog.CURRICULA:
        directory = book_catalog.source_directory(curriculum)
        assert [item['subject'] for item in directory] == book_catalog.SUBJECTS
        if curriculum != 'cbse':
            assert 'ncert.nic.in' not in json.dumps(directory)
    assert all('minhaji.moe.gov.ae' in json.dumps(item) for item in book_catalog.source_directory('moe'))
    assert 'https://ncert.nic.in/textbook.php' in json.dumps(book_catalog.source_directory('cbse'))


@pytest.mark.parametrize('curriculum',['moe','british','american','ib','icse','other'])
def test_ncert_rejected_even_when_model_mislabels_curriculum(curriculum):
    wrong = discovered(title='NCERT Mathematics',publisher='NCERT',curriculum=curriculum,
                       source_url='https://ncert.nic.in/textbook.php')
    assert book_library.matching_discovery(book_library.DiscoveryResult(books=[wrong]),curriculum) == []


def test_ncert_permitted_only_for_cbse_and_scope_must_match():
    book = discovered(title='NCERT Mathematics',publisher='NCERT',curriculum='cbse',source_url='https://ncert.nic.in/textbook.php')
    result = book_library.DiscoveryResult(books=[book])
    assert len(book_library.matching_discovery(result,'cbse')) == 1
    assert book_library.matching_discovery(result,'moe') == []
    assert book_library.matching_discovery(result,'cbse',grade='9') == []
    assert book_library.matching_discovery(result,'cbse',subject='Physics') == []
    assert book_library.matching_discovery(result,'cbse',language='ar') == []


def test_school_login_result_cannot_supply_a_public_pdf_link():
    book = discovered(pdf_url='https://publisher.example/not-public.pdf')
    result = book_library.matching_discovery(book_library.DiscoveryResult(books=[book]),'moe')
    assert result[0]['pdf_url'] is None
    assert result[0]['access'] == 'school_login'


async def test_discovery_cache_keys_include_curriculum_and_version(monkeypatch):
    db = database()
    db.get.return_value = SimpleNamespace(value={'books':[],'results':'Cached'})
    user = SimpleNamespace(id=uuid.uuid4())
    ai = SimpleNamespace(text=AsyncMock())
    monkeypatch.setattr('app.ai.service.get_ai',lambda:ai)
    for curriculum in ['moe','cbse']:
        result = await book_library.discover(db,user,'Grade 10 mathematics',curriculum=curriculum)
        assert result['cached']
    keys = [call.args[1] for call in db.get.call_args_list]
    assert keys[0] != keys[1]
    assert keys[0] != book_library.cache_key(user.id,'book_find','grade 10 mathematics')
    ai.text.assert_not_awaited()


async def test_wrong_curriculum_search_response_is_filtered_and_cached(monkeypatch):
    db = database()
    wrong = discovered(title='NCERT Mathematics',publisher='NCERT',source_url='https://ncert.nic.in/textbook.php')
    ai = SimpleNamespace(text=AsyncMock(return_value=book_library.DiscoveryResult(books=[wrong]).model_dump_json()))
    monkeypatch.setattr('app.ai.service.get_ai',lambda:ai)
    result = await book_library.discover(db,SimpleNamespace(id=uuid.uuid4()),'maths',curriculum='moe')
    assert result['books'] == []
    assert 'ncert.nic.in' not in result['results']
    assert 'No verified matching textbook' in result['unavailable_reason']
    db.commit.assert_awaited_once()
    assert 'NCERT is permitted ONLY' in ai.text.call_args.kwargs['system']


async def test_ncert_import_under_moe_rejected_before_download(monkeypatch):
    download = AsyncMock()
    monkeypatch.setattr(book_library,'download_public_image',download)
    with pytest.raises(AppError,match='CBSE'):
        await book_library.import_pdf(database(),SimpleNamespace(id=uuid.uuid4()),url='https://ncert.nic.in/book.pdf',
            title='Mathematics',metadata={'curriculum':'moe'},rights_confirmed=True,max_bytes=1000)
    download.assert_not_awaited()


def test_catalogue_query_requires_ready_admin_book_and_explicit_sharing():
    query = book_catalog.published_query()
    sql = str(query.compile(dialect=postgresql.dialect(),compile_kwargs={'literal_binds':True}))
    assert "users.role = 'admin'" in sql and "users.status = 'active'" in sql
    assert "uploaded_files.status = 'ready'" in sql
    assert 'sharing_rights_confirmed' in sql and 'published' in sql


async def test_teacher_and_support_cannot_publish_to_shared_catalogue():
    for user in [SimpleNamespace(role='teacher',admin_role=None),SimpleNamespace(role='admin',admin_role='support')]:
        with pytest.raises(HTTPException) as error:
            await require('settings.modify')(user)
        assert error.value.status_code == 403


async def test_unpublished_or_private_book_cannot_be_copied():
    db = database()
    db.execute.return_value = rows([])
    with pytest.raises(NotFound):
        await book_catalog.copy_to_library(db,SimpleNamespace(id=uuid.uuid4()),uuid.uuid4(),1000)


async def test_already_saved_catalogue_book_skips_storage_and_index(monkeypatch):
    db = database()
    source = SimpleNamespace(id=uuid.uuid4(),sha256='hash')
    saved = SimpleNamespace(status='ready')
    db.execute.side_effect = [rows([source]),rows([saved])]
    monkeypatch.setattr('app.services.usage.lock_user',AsyncMock())
    storage = SimpleNamespace(get=AsyncMock())
    monkeypatch.setattr(book_catalog,'get_storage',lambda:storage)
    assert await book_catalog.copy_to_library(db,SimpleNamespace(id=uuid.uuid4()),source.id,1000) is saved
    storage.get.assert_not_awaited()
    assert db.execute.await_count == 2


async def test_shared_pdf_copy_reuses_embeddings_and_retains_attribution(monkeypatch):
    db = database()
    source = SimpleNamespace(id=uuid.uuid4(),sha256='hash',size_bytes=100,storage_key='shared.pdf',
        filename='Mathematics.pdf',page_count=80,meta={'book':{'curriculum':'moe','subject':'Mathematics'},
        'chapters':[{'title':'Algebra','start':12,'end':18}],
        'catalogue':{'published':True,'license':'School permission','license_url':'https://school.example/permission'}})
    saved = SimpleNamespace(id=uuid.uuid4(),status='queued',meta={})
    db.execute.side_effect = [rows([source]),rows([]),None]
    monkeypatch.setattr('app.services.usage.lock_user',AsyncMock())
    quota = AsyncMock()
    monkeypatch.setattr('app.services.usage.check_storage',quota)
    monkeypatch.setattr(book_catalog,'get_storage',lambda:SimpleNamespace(get=AsyncMock(return_value=b'%PDF-1.7')))
    store = AsyncMock(return_value=(saved,True))
    monkeypatch.setattr('app.services.uploads.store_upload',store)
    ai = SimpleNamespace(embed=AsyncMock())
    monkeypatch.setattr('app.ai.service.get_ai',lambda:ai)
    user = SimpleNamespace(id=uuid.uuid4())
    assert await book_catalog.copy_to_library(db,user,source.id,1000) is saved
    assert saved.status == 'ready' and saved.page_count == 80
    assert 'catalogue' not in saved.meta
    assert saved.meta['attribution']['license'] == 'School permission'
    copied = db.execute.call_args.args[0]
    assert copied.table is SourceChunk.__table__
    assert 'source_chunks.embedding' in str(copied)
    assert store.call_args.kwargs['owner_id'] == user.id
    ai.embed.assert_not_awaited()
    db.commit.assert_awaited_once()


async def test_publication_requires_grade_edition_and_full_sharing_rights(monkeypatch):
    db = database()
    user = SimpleNamespace(id=uuid.uuid4())
    book = SimpleNamespace(id=uuid.uuid4(),status='ready',mime='application/pdf',filename='Mathematics.pdf',
        meta={'book':{'title':'Mathematics','curriculum':'moe','subject':'Mathematics','grade':'10','language':'en','edition':'2026'}})
    monkeypatch.setattr(book_library,'owned_book',AsyncMock(return_value=book))
    request = Request({'type':'http','headers':[]})
    body = content.BookPublication(published=True)
    with pytest.raises(AppError,match='permission'):
        await content.publish_book(book.id,body,request,user,db)
    del book.meta['book']['edition']
    with pytest.raises(AppError,match='edition'):
        await content.publish_book(book.id,body,request,user,db)
    assert 'catalogue' not in book.meta
    db.commit.assert_not_awaited()


async def test_private_metadata_edit_does_not_publish_a_book(monkeypatch):
    db = database()
    book = SimpleNamespace(filename='Maths.pdf',meta={})
    monkeypatch.setattr(book_library,'owned_book',AsyncMock(return_value=book))
    monkeypatch.setattr(book_library,'book_out',lambda book:{'metadata':book.meta['book']})
    body = content.BookMetadata(title='Mathematics',curriculum='moe',subject='Mathematics',grade='10',language='en')
    await content.update_book_metadata(uuid.uuid4(),body,SimpleNamespace(id=uuid.uuid4()),db)
    assert 'catalogue' not in book.meta
    assert book.meta['book']['curriculum'] == 'moe'


async def test_provider_citations_do_not_break_json_book_response(monkeypatch):
    db = database()
    payload = book_library.DiscoveryResult(books=[discovered()]).model_dump_json()
    ai = SimpleNamespace(text=AsyncMock(return_value=payload+'\n\nSources:\n[1](https://minhaji.moe.gov.ae/)'))
    monkeypatch.setattr('app.ai.service.get_ai',lambda:ai)
    result = await book_library.discover(db,SimpleNamespace(id=uuid.uuid4()),'Mathematics',curriculum='moe')
    assert len(result['books']) == 1
    assert result['books'][0]['curriculum'] == 'moe'


@pytest.mark.parametrize('url',['javascript:alert(1)','https://bad host/book.pdf','https://:secret@publisher.example/book.pdf','https://[invalid/book.pdf'])
def test_malformed_or_credentialed_book_links_are_not_displayed(url):
    book = discovered(source_url=url)
    assert book_library.matching_discovery(book_library.DiscoveryResult(books=[book]),'moe') == []

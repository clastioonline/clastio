"""External reading records must not imply stored files or school syllabus alignment."""
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

from test_book_workflow import database, rows

from app.services import book_catalog
from app.services.book_sources import textbook_sources


def test_official_collections_prioritise_uae_and_british_and_keep_ncert_scoped():
    collections = textbook_sources()['collections']
    assert collections[0]['curriculum'] == 'moe'
    assert collections[0]['access'] == 'school_login'
    assert collections[1]['curriculum'] == 'british'
    assert {item['id'] for item in collections if item['curriculum'] == 'british'} >= {
        'british-cambridge-primary', 'british-cambridge-lower-secondary', 'british-pearson-igcse'}
    assert all(item['curriculum'] == 'cbse' for item in collections if 'ncert.nic.in' in item['source_url'])


def test_reading_metadata_has_unique_safe_official_links_without_stored_file_claims():
    data = textbook_sources()
    records = data['collections'] + data['reference_books']
    assert len({item['id'] for item in records}) == len(records)
    allowed_hosts = {'minhaji.moe.gov.ae', 'www.cambridgeinternational.org', 'qualifications.pearson.com',
                     'openstax.org', 'ibo.org', 'ncert.nic.in', 'www.siyavula.com'}
    for item in records:
        url = urlsplit(item['source_url'])
        assert url.scheme == 'https' and url.hostname in allowed_hosts
        assert item['reviewed_on'] == '2026-10-12'
        assert not any(key in item for key in ['pdf_url', 'download', 'file_id', 'catalogue_id', 'storage_key'])


def test_openstax_requires_permission_and_other_curriculum_books_remain_supplementary():
    books = textbook_sources()['reference_books']
    for book in books:
        assert book['license'] and book['license_url'] and book['rights_note'] and book['curriculum_note']
        if book['id'].startswith('openstax-'):
            assert book['curriculum'] == 'american'
            assert 'AI use requires written permission' in book['license']
            assert 'Written publisher permission' in book['rights_note']
            assert book['grades'] == []
            assert 'alignment have not been verified' in book['curriculum_note']
        elif book['id'].startswith('siyavula-'):
            assert book['curriculum'] == 'other'
            assert book['license'] == 'Online textbook text: CC BY 3.0'
            assert 'CC BY-ND 3.0' in book['rights_note']
            assert 'South African CAPS' in book['curriculum_note']
            assert len(book['grades']) == 1
        elif book['id'].startswith('cambridge-'):
            assert book['curriculum'] == 'british' and book['access'] == 'publisher'
            assert 'access licence required' in book['license']


def test_source_metadata_returns_fresh_records_without_polluting_future_requests():
    first = textbook_sources()
    first['reference_books'][0]['subjects'].append('Not a real subject')
    first['collections'][0]['title'] = 'Changed by client'
    second = textbook_sources()
    assert 'Not a real subject' not in second['reference_books'][0]['subjects']
    assert second['collections'][0]['title'] == 'UAE MoE textbooks — Minhaji'


async def test_catalogue_browsing_serves_sources_without_ai_or_downloads(monkeypatch):
    db = database()
    db.execute.return_value = rows([])
    ai = AsyncMock()
    monkeypatch.setattr('app.ai.service.get_ai', ai)
    storage = AsyncMock()
    monkeypatch.setattr(book_catalog, 'get_storage', storage)
    result = await book_catalog.catalog(db)
    assert result['items'] == []
    assert len(result['reference_books']) == 31 and len(result['collections']) == 10
    ai.assert_not_called()
    storage.assert_not_called()
    db.execute.assert_awaited_once()

from __future__ import annotations

import io
import uuid
from types import SimpleNamespace

import pymupdf as fitz
from PIL import Image
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import UploadedFile
from app.services.courses import chapter_teaching_context
from app.services.sources import chunk, retrieve
from tests.conftest import make_user


async def upload_notes(client, headers, text='Chapter notes: sine uses opposite divided by hypotenuse.'):
    result = await client.post('/api/v1/uploads', headers=headers, data={'kind': 'source'},
                               files={'file': ('chapter-notes.txt', text.encode(), 'text/plain')})
    assert result.status_code == 200, result.text
    assert result.json()['file']['status'] == 'ready'
    return result.json()['file']['id']


async def create(client, headers, **extra):
    payload = {'topic': 'Trigonometry', 'grade': '8', 'subject': 'Mathematics', 'num_lectures': 2,
               'slides_per_lecture': 4, 'auto_generate': False, **extra}
    return await client.post('/api/v1/courses', headers=headers, json=payload)


async def test_sources_are_attached_and_retrieval_is_chapter_scoped(client, teacher):
    headers = teacher['headers']
    selected = await upload_notes(client, headers)
    other = await upload_notes(client, headers, 'Other book: unrelated water cycle material.')
    result = await create(client, headers, source_file_ids=[selected], chapter_mode='parts', auto_generate=True,
                          previous_taught='Triangle sides', revision_needed='Opposite and adjacent')
    assert result.status_code == 200, result.text
    course = result.json()['course']
    assert course['options']['source_file_ids'] == [selected]
    assert course['options']['revision_needed'] == 'Opposite and adjacent'
    project = (await client.get('/api/v1/projects/' + course['project_id'], headers=headers)).json()
    assert all(lesson['status'] == 'planned' for lesson in project['lessons'])
    async with get_sessionmaker()() as db:
        sources = await retrieve(db, uuid.UUID(teacher['id']), 'chapter', file_ids=[selected])
        assert sources and {source['file_id'] for source in sources} == {selected}
        assert await retrieve(db, uuid.UUID(teacher['id']), 'chapter', file_ids=[]) == []
        assert other not in {source['file_id'] for source in sources}


async def test_cannot_use_another_teachers_book(client, teacher):
    other = await make_user(client)
    source = await upload_notes(client, other['headers'])
    result = await create(client, teacher['headers'], source_file_ids=[source])
    assert result.status_code == 404


async def test_pending_source_cannot_silently_be_ignored(client, teacher):
    source = await upload_notes(client, teacher['headers'])
    async with get_sessionmaker()() as db:
        file = await db.get(UploadedFile, uuid.UUID(source))
        file.status = 'processing'
        await db.commit()
    result = await create(client, teacher['headers'], source_file_ids=[source])
    assert result.status_code == 409


async def test_daily_builds_one_lesson_and_accepts_revision_for_next(client, teacher):
    h = teacher['headers']
    result = await create(client, h, chapter_mode='daily', auto_generate=True, previous_taught='Triangle sides')
    assert result.status_code == 200, result.text
    course = result.json()['course']
    project = (await client.get('/api/v1/projects/' + course['project_id'], headers=h)).json()
    assert [lesson['has_pptx'] for lesson in project['lessons']] == [True, False]
    assert project['course']['status'] == 'planned'  # no endless generation indicator
    first = project['lessons'][0]
    reflected = await client.post(f"/api/v1/lessons/{first['id']}/reflection", headers=h,
                                   json={'outcome': 'struggled', 'note': 'Revise adjacent versus opposite', 'covered_until_slide': 2})
    assert reflected.status_code == 200
    generated = await client.post(f"/api/v1/courses/{course['id']}/generate", headers=h,
                                   json={'lessons': [2], 'previous_taught': 'Sine examples', 'revision_needed': 'Adjacent versus opposite',
                                         'instructions': 'Begin with two quick questions'})
    assert generated.status_code == 200, generated.text
    project = (await client.get('/api/v1/projects/' + course['project_id'], headers=h)).json()
    assert all(lesson['has_pptx'] for lesson in project['lessons'])
    from app.models import GenerationJob
    async with get_sessionmaker()() as db:
        jobs = (await db.execute(select(GenerationJob).where(GenerationJob.id.in_(
            [uuid.UUID(value) for value in generated.json()['job_ids']])))).scalars().all()
        assert jobs[0].payload['revision_needed'] == 'Adjacent versus opposite'


async def test_manual_image_and_table_edits_survive_rebuild(client, teacher):
    h = teacher['headers']
    result = await create(client, h, num_lectures=1, auto_generate=True)
    course = result.json()['course']
    project = (await client.get('/api/v1/projects/' + course['project_id'], headers=h)).json()
    lesson = project['lessons'][0]['id']
    buffer = io.BytesIO()
    Image.new('RGB', (80, 60), 'blue').save(buffer, 'PNG')
    image = await client.post('/api/v1/slide-images', headers=h, files={'file': ('my-image.png', buffer.getvalue(), 'image/png')})
    assert image.status_code == 200, image.text
    edited = await client.patch(f'/api/v1/lessons/{lesson}/slides/2', headers=h,
                                 json={'spec': {'title': 'Teacher edited image', 'layout': 'image_text',
                                   'asset_id': image.json()['asset_id'], 'visual': {'kind': 'image', 'alt_text': 'My image'}}})
    assert edited.status_code == 200, edited.text
    edited = await client.patch(f'/api/v1/lessons/{lesson}/slides/3', headers=h,
                                 json={'spec': {'title': 'Our results', 'layout': 'table',
                                   'table': {'headers': ['Name', 'Score'], 'rows': [['A', '4'], ['B', '5']]}}})
    assert edited.status_code == 200, edited.text
    detail = (await client.get('/api/v1/lessons/' + lesson, headers=h)).json()
    assert detail['slides'][1]['spec']['asset_id'] == image.json()['asset_id']
    assert detail['slides'][2]['spec']['table']['rows'][1] == ['B', '5']
    assert detail['downloads']['pptx']
    other = await make_user(client)
    forbidden = await client.patch(f'/api/v1/lessons/{lesson}/slides/2', headers=other['headers'], json={'spec': {'title': 'Hijack'}})
    assert forbidden.status_code == 404
    other_image = await client.post('/api/v1/slide-images', headers=other['headers'], files={'file': ('private.png', buffer.getvalue(), 'image/png')})
    forbidden = await client.patch(f'/api/v1/lessons/{lesson}/slides/2', headers=h,
                                    json={'spec': {'asset_id': other_image.json()['asset_id']}})
    assert forbidden.status_code == 404


async def test_scanned_book_reports_missing_text(client, teacher):
    doc = fitz.open()
    doc.new_page()
    result = await client.post('/api/v1/uploads', headers=teacher['headers'], data={'kind': 'source'},
                               files={'file': ('scanned.pdf', doc.tobytes(), 'application/pdf')})
    assert result.status_code == 200
    assert result.json()['file']['status'] == 'failed'
    assert 'No readable text' in result.json()['file']['error']


def test_long_notes_are_split_into_bounded_chunks():
    pieces = chunk([(1, 'a' * 10_000)])
    assert len(pieces) > 10 and all(len(text) <= 900 for _, text in pieces)


def test_context_distinguishes_previous_teaching_from_revision():
    course = SimpleNamespace(options={'chapter_mode': 'daily', 'previous_taught': 'Sine', 'revision_needed': 'Ratios'})
    context = chapter_teaching_context(course, {'previous_taught': 'Cosine', 'revision_needed': 'Triangle sides'})
    assert 'Cosine' in context and 'Triangle sides' in context and 'not proof' in context
    assert 'already taught: Sine' not in context

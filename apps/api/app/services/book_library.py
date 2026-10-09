"""Persistent private textbook library: original PDFs and one-time source indexing."""
from __future__ import annotations

import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, HttpUrl, ValidationError
from sqlalchemy import select

from app.core.errors import AppError, NotFound
from app.core.remote_images import download_public_image
from app.core.storage import get_storage
from app.jobs.queue import enqueue
from app.models import AppSetting, UploadedFile
from app.services.uploads import store_upload


def book_out(book):
    return {'id': str(book.id), 'filename': book.filename, 'status': book.status,
            'stage': book.stage, 'error': book.error, 'page_count': book.page_count,
            'metadata': (book.meta or {}).get('book', {}), 'catalogue': (book.meta or {}).get('catalogue', {}), 'chapters': (book.meta or {}).get('chapters', []),
            'download': get_storage().signed_url(book.storage_key, book.filename)}


async def import_pdf(db, user, *, url, title, metadata, rights_confirmed, max_bytes):
    if not rights_confirmed:
        raise AppError('rights_required', 'Confirm that you may use this PDF for teaching.', 400)
    validate_book_identity(title, url, metadata.get("curriculum", ""))
    existing = (await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id,
        UploadedFile.kind == 'source', UploadedFile.meta['book']['source_url'].astext == url))).scalars().first()
    if existing and existing.status != 'failed':
        return existing, None
    data = await download_public_image(url, max_bytes)
    if not data.startswith(b'%PDF-'):
        raise AppError('not_pdf', 'Use a direct, publicly accessible PDF link. Login pages cannot be imported.', 400)
    from app.services import usage
    duplicate = (await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id,
        UploadedFile.kind == "source", UploadedFile.sha256 == hashlib.sha256(data).hexdigest()))).scalars().first()
    await usage.check_storage(db, user, 0 if duplicate else len(data))
    book, new = await store_upload(db, owner_id=user.id, filename=title+'.pdf', data=data,
                                  kind='source', rights_confirmed=True)
    book.meta = {**(book.meta or {}), 'book': {**metadata, 'title': title, 'source_url': url}}
    job = None
    if new or book.status == 'failed':
        job = await enqueue(db, 'source_indexing', {'file_id': str(book.id)}, owner_id=user.id, dedupe=True)
        book.status, book.stage, book.error = 'queued', 'Reading saved book', None
    await db.commit()
    return book, job


async def owned_book(db, user, file_id):
    book = await db.get(UploadedFile, file_id)
    if not book or book.owner_id != user.id or book.kind != 'source':
        raise NotFound('Book')
    return book


def cache_key(owner_id, category, payload):
    import json
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]
    return f'{category}:{owner_id}:{digest}'


def validate_book_identity(title, source_url, curriculum):
    host = (urlsplit(source_url).hostname or '').casefold() if source_url else ''
    if ('ncert' in title.casefold() or host == 'ncert.nic.in' or host.endswith('.ncert.nic.in')) and curriculum != 'cbse':
        raise AppError('wrong_book_curriculum', 'NCERT books belong under Indian — CBSE, not UAE MoE or another curriculum.', 400)


class DiscoveredBook(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    curriculum: Literal['moe', 'british', 'american', 'ib', 'cbse', 'icse', 'other']
    publisher: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=100)
    grade: str = Field(max_length=30)
    language: str = Field(max_length=30)
    edition: str = Field(max_length=100)
    source_url: str = Field(max_length=2000)
    pdf_url: str | None = Field(default=None, max_length=2000)
    access: Literal['public_pdf', 'school_login', 'publisher_access']


class DiscoveryResult(BaseModel):
    books: list[DiscoveredBook] = Field(default_factory=list, max_length=10)
    unavailable_reason: str = Field(default='', max_length=1000)


def valid_https_url(value):
    try:
        parsed = HttpUrl(value)
        return parsed.scheme == 'https' and not parsed.username and not parsed.password
    except (ValueError, TypeError):
        return False


def matching_discovery(result, curriculum, subject='', grade='', language=''):
    accepted = []
    for book in result.books:
        if book.curriculum != curriculum:
            continue
        if subject and book.subject.casefold() != subject.casefold():
            continue
        if grade and book.grade.casefold() != grade.casefold():
            continue
        if language and book.language.casefold() not in {language.casefold(), {'en':'english','ar':'arabic'}.get(language, language)}:
            continue
        urls = [url for url in [book.source_url, book.pdf_url] if url]
        if any(not valid_https_url(url) for url in urls):
            continue
        ncert = 'ncert' in (book.publisher+' '+book.title).casefold() or any(
            (urlsplit(url).hostname or '').endswith('.ncert.nic.in') or urlsplit(url).hostname == 'ncert.nic.in' for url in urls)
        if ncert and curriculum != 'cbse':
            continue
        if book.access != 'public_pdf':
            book.pdf_url = None
        accepted.append(book.model_dump())
    return accepted


async def discover(db, user, query, *, curriculum='moe', subject='', grade='', language=''):
    from app.ai.base import ChatMessage
    from app.ai.schema_utils import extract_json
    from app.ai.service import get_ai
    from app.services.book_catalog import CURRICULA

    if curriculum not in CURRICULA:
        raise AppError('invalid_curriculum', 'Select a supported curriculum.', 400)
    scope = {'version': 3, 'query': ' '.join(query.split()).casefold(), 'curriculum': curriculum,
             'subject': subject, 'grade': grade, 'language': language}
    key = cache_key(user.id, 'book_find', scope)
    cached = await db.get(AppSetting, key)
    if cached:
        return {**cached.value, 'cached': True}
    text = await get_ai().text(task='textbook_discovery', tier='search', owner_id=user.id,
        system='Find only official or publisher-authorised textbooks matching the explicit curriculum, '
               'subject, grade and language. UAE location is not a curriculum. NCERT is permitted ONLY '
               'when curriculum=cbse; never substitute it for UAE MoE, British, American, IB or ICSE. '
               'The curriculum field is authoritative even if the query requests a different curriculum. '
               'For UAE MoE, prefer the Ministry textbook library Minhaji (minhaji.moe.gov.ae). '
               'Do not use pirated mirrors, invent book titles or links, or substitute supplements. '
               'Return no books and explain missing access if the matching textbook cannot be verified. '
               'School-login and publisher-login books are not public PDFs. Return only JSON matching '
               'this schema: '+json.dumps(DiscoveryResult.model_json_schema()),
        messages=[ChatMessage('user', json.dumps(scope))], max_tokens=3000)
    try:
        result = DiscoveryResult.model_validate(extract_json(text.split('\n\nSources:\n', 1)[0]))
        books = matching_discovery(result, curriculum, subject, grade, language)
        reason = result.unavailable_reason if books else 'No verified matching textbook was found. Use the official source directory or save your school-authorised copy.'
    except (ValueError, ValidationError, TypeError):
        books, reason = [], 'The search response could not be verified. Use the official source directory or try a more specific book title.'
    value = {'books': books, 'unavailable_reason': reason, 'curriculum': curriculum,
             'results': '\n\n'.join(book['title']+' — '+book['publisher']+'\n'+book['source_url']+
                                       ('\n'+book['pdf_url'] if book['pdf_url'] else '') for book in books) or reason}
    from sqlalchemy.dialects.postgresql import insert
    await db.execute(insert(AppSetting).values(key=key, value=value).on_conflict_do_nothing(index_elements=['key']))
    await db.commit()
    return {**value, 'cached': False}

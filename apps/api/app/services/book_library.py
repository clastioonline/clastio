"""Persistent private textbook library: original PDFs and one-time source indexing."""
from __future__ import annotations

import hashlib

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
            'metadata': (book.meta or {}).get('book', {}), 'chapters': (book.meta or {}).get('chapters', []),
            'download': get_storage().signed_url(book.storage_key, book.filename)}


async def import_pdf(db, user, *, url, title, metadata, rights_confirmed, max_bytes):
    if not rights_confirmed:
        raise AppError('rights_required', 'Confirm that you may use this PDF for teaching.', 400)
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


async def discover(db, user, query):
    from app.ai.base import ChatMessage
    from app.ai.service import get_ai
    key = cache_key(user.id, 'book_find', ' '.join(query.split()).casefold())
    cached = await db.get(AppSetting, key)
    if cached:
        return {**cached.value, 'cached': True}
    text = await get_ai().text(task='textbook_discovery', tier='search', owner_id=user.id,
        system='Find official or publisher-authorised educational books for the requested grade, curriculum, '
               'subject and edition. Give the book title, publisher, edition, language and source URL. '
               'Only give a PDF URL if it is actually available. Do not use pirated mirrors or invent links. '
               'Distinguish UAE curriculum textbooks from supplementary resources. State when no accessible '
               'matching book is found. Do not claim school-login resources are public.',
        messages=[ChatMessage('user', query)], max_tokens=1800)
    value = {'results': text}
    from sqlalchemy.dialects.postgresql import insert
    await db.execute(insert(AppSetting).values(key=key, value=value).on_conflict_do_nothing(index_elements=['key']))
    await db.commit()
    return {**value, 'cached': False}

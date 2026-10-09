"""Curriculum-scoped directory and explicitly published, reusable school PDFs.

Directory entries are source destinations, never assertions that a textbook file is stored.
"""
from __future__ import annotations

from sqlalchemy import delete, func, literal, select

from app.core.errors import AppError, NotFound
from app.core.storage import get_storage
from app.models import SourceChunk, UploadedFile, User
from app.services.book_library import book_out

CURRICULA = {
    'moe': 'UAE Ministry of Education', 'british': 'British / Cambridge / Pearson',
    'american': 'American', 'ib': 'International Baccalaureate', 'cbse': 'Indian — CBSE',
    'icse': 'Indian — ICSE', 'other': 'Other school curriculum',
}
SUBJECTS = ['Mathematics', 'Science', 'Biology', 'Chemistry', 'Physics', 'English', 'Arabic',
            'Islamic Education', 'Social Studies & Moral Education', 'Geography', 'History',
            'Computing', 'Artificial Intelligence', 'Business', 'Economics', 'Art', 'Music',
            'Physical Education']
UAE_SUBJECTS = {'Arabic', 'Islamic Education', 'Social Studies & Moral Education'}
MOE_SOURCE = {'label': 'MoE electronic book library (Minhaji)', 'url': 'https://minhaji.moe.gov.ae/',
              'access': 'school_login', 'note': 'Open with your school account, then save an authorised PDF copy.'}
PUBLISHERS = {
    'british': [{'label': 'Cambridge textbooks and resources', 'url': 'https://www.cambridgeinternational.org/resource-centre/',
                 'access': 'publisher', 'note': 'Use the edition and exam board prescribed by your school.'},
                {'label': 'Pearson International Schools', 'url': 'https://www.pearson.com/international-schools.html',
                 'access': 'publisher', 'note': 'School or publisher access may be required.'}],
    'american': [{'label': 'McGraw Hill PreK–12', 'url': 'https://www.mheducation.com/prek-12',
                  'access': 'publisher', 'note': 'Match your school textbook series and state standards.'}],
    'ib': [{'label': 'IB programmes', 'url': 'https://www.ibo.org/programmes/', 'access': 'programme_directory',
            'note': 'A programme directory, not a free textbook library. Use the school-prescribed book.'}],
    'cbse': [{'label': 'NCERT textbook library — CBSE only', 'url': 'https://ncert.nic.in/textbook.php',
              'access': 'official_library', 'note': 'Indian CBSE resources, not UAE MoE textbooks.'}],
    'icse': [{'label': 'CISCE', 'url': 'https://cisce.org/', 'access': 'programme_directory',
              'note': 'Use your school-prescribed ICSE/ISC books; NCERT is not an automatic substitute.'}],
    'other': [],
}


def source_directory(curriculum):
    if curriculum not in CURRICULA:
        raise AppError('invalid_curriculum', 'Select a supported curriculum.', 400)
    return [{'subject': subject, 'sources': [dict(MOE_SOURCE)] if curriculum == 'moe' or subject in UAE_SUBJECTS
             else [dict(source) for source in PUBLISHERS.get(curriculum, [])]} for subject in SUBJECTS]


def published_query():
    # Publication can only be set by staff; still verify the current owner's status and role.
    return select(UploadedFile).join(User, User.id == UploadedFile.owner_id).where(
        UploadedFile.kind == 'source', UploadedFile.mime == 'application/pdf', UploadedFile.status == 'ready',
        User.role == 'admin', User.status == 'active',
        UploadedFile.meta['catalogue']['published'].astext == 'true',
        UploadedFile.meta['catalogue']['sharing_rights_confirmed'].astext == 'true')


async def catalog(db):
    books = (await db.execute(published_query().order_by(UploadedFile.created_at.desc()))).scalars().all()
    return {'curricula': [{'code': code, 'label': label} for code, label in CURRICULA.items()],
            'subjects': SUBJECTS, 'directories': {code: source_directory(code) for code in CURRICULA},
            'items': [{**book_out(book), 'catalogue_id': str(book.id),
                       'license': book.meta['catalogue'].get('license'),
                       'license_url': book.meta['catalogue'].get('license_url')} for book in books]}


async def copy_to_library(db, user, file_id, max_bytes):
    """Copy a published file and its existing index; never re-search or re-embed it."""
    from app.services import usage
    from app.services.uploads import store_upload

    source = (await db.execute(published_query().where(UploadedFile.id == file_id))).scalars().first()
    if not source:
        raise NotFound('Published book')
    await usage.lock_user(db, user.id)
    existing = (await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id,
        UploadedFile.kind == 'source', UploadedFile.sha256 == source.sha256))).scalars().first()
    if existing and existing.status == 'ready':
        return existing
    if source.size_bytes > max_bytes:
        raise AppError('book_too_large', 'This PDF exceeds your upload size allowance.', 400)
    await usage.check_storage(db, user, 0 if existing else source.size_bytes)
    data = await get_storage().get(source.storage_key)
    book, new = await store_upload(db, owner_id=user.id, filename=source.filename, data=data,
                                  kind='source', rights_confirmed=True)
    if not new and book.status != 'failed':
        # Do not overwrite a source being indexed by another job.
        return book
    if not new:
        await db.execute(delete(SourceChunk).where(SourceChunk.file_id == book.id))
    book.meta = {'book': {**(source.meta or {}).get('book', {}), 'catalogue_source_id': str(source.id)},
                 'chapters': (source.meta or {}).get('chapters', []),
                 'attribution': {'license': source.meta['catalogue']['license'],
                                 'license_url': source.meta['catalogue']['license_url']}}
    await db.execute(SourceChunk.__table__.insert().from_select(
        ['id', 'file_id', 'owner_id', 'page', 'text', 'embedding'],
        select(func.gen_random_uuid(), literal(book.id), literal(user.id), SourceChunk.page,
               SourceChunk.text, SourceChunk.embedding).where(SourceChunk.file_id == source.id)))
    book.error = None
    book.page_count, book.status, book.stage = source.page_count, 'ready', 'Ready — reused catalogue index'
    await db.commit()
    return book

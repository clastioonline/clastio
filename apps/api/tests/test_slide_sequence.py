"""Slide sequence integration tests against isolated PostgreSQL (no AI/render calls)."""
import uuid

import pytest
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError, NotFound
from app.generation.specs import SlideSpec
from app.models import Base, Course, GenerationJob, Lesson, Project, Slide, SlideVersion, User
from app.services.courses import arrange_slides


@pytest.fixture
async def editor_database(monkeypatch):
    settings = get_settings()
    assert settings.database_url.endswith('/teacher_assistant_test')
    monkeypatch.setattr(settings, 'run_jobs_inline', False)
    names = {'slides', 'lessons', 'generation_jobs', 'slide_versions', 'subscriptions', 'plans', 'app_settings', 'credit_ledger'}
    while True:
        refs = {fk.column.table.name for name in names for fk in Base.metadata.tables[name].foreign_keys}
        if refs <= names:
            break
        names |= refs
    engine = create_engine(settings.sync_database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in names])
    engine.dispose()
    async with get_sessionmaker()() as db:
        owner = User(email=f'editor-{uuid.uuid4()}@example.com', name='Teacher')
        other = User(email=f'editor-{uuid.uuid4()}@example.com', name='Other')
        db.add_all([owner, other])
        await db.flush()
        project = Project(owner_id=owner.id, title='Editor')
        db.add(project)
        await db.flush()
        course = Course(owner_id=owner.id, project_id=project.id, topic='Fractions', subject='Math', grade='4',
                        curriculum='british', num_lectures=1, slides_per_lecture=3)
        db.add(course)
        await db.flush()
        lesson = Lesson(owner_id=owner.id, course_id=course.id, number=1, title='Fractions', plan={'title': 'Fractions'})
        db.add(lesson)
        await db.flush()
        slides = [Slide(lesson_id=lesson.id, number=n, spec=SlideSpec(number=n, layout='concept',
                    purpose='Practice', title=f'Slide {n}').model_dump()) for n in range(1, 4)]
        db.add_all(slides)
        await db.commit()
        return owner.id, other.id, lesson.id, [slide.id for slide in slides]


async def test_sequence_preserves_identity_and_rejects_conflicts(editor_database):
    owner_id, other_id, lesson_id, original = editor_database
    async with get_sessionmaker()() as db:
        owner = await db.get(User, owner_id)
        other = await db.get(User, other_id)
        with pytest.raises(NotFound):
            await arrange_slides(db, other, lesson_id, action='move', number=1, target=2)
        job_id, current = await arrange_slides(db, owner, lesson_id, action='move', number=1, target=3)
        assert current == 3
        rows = list((await db.execute(select(Slide).where(Slide.lesson_id == lesson_id).order_by(Slide.number))).scalars())
        assert [row.id for row in rows] == [original[1], original[2], original[0]]
        assert [row.spec['number'] for row in rows] == [1, 2, 3]
        with pytest.raises(AppError, match='current lesson update'):
            await arrange_slides(db, owner, lesson_id, action='duplicate', number=1)
        job = await db.get(GenerationJob, job_id)
        job.status = 'succeeded'
        await db.commit()
        job_id, current = await arrange_slides(db, owner, lesson_id, action='duplicate', number=1)
        assert current == 2
        rows = list((await db.execute(select(Slide).where(Slide.lesson_id == lesson_id).order_by(Slide.number))).scalars())
        assert len(rows) == 4 and rows[1].id not in original
        assert rows[0].spec['title'] == rows[1].spec['title']
        (await db.get(GenerationJob, job_id)).status = 'succeeded'
        await db.commit()
        job_id, _ = await arrange_slides(db, owner, lesson_id, action='insert', number=2, layout='section')
        rows = list((await db.execute(select(Slide).where(Slide.lesson_id == lesson_id).order_by(Slide.number))).scalars())
        assert len(rows) == 5 and rows[2].spec['layout'] == 'section'
        removed = rows[2].id
        db.add(SlideVersion(slide_id=removed, version=1, spec=rows[2].spec, reason='test'))
        (await db.get(GenerationJob, job_id)).status = 'succeeded'
        await db.commit()
        job_id, _ = await arrange_slides(db, owner, lesson_id, action='delete', number=3)
        rows = list((await db.execute(select(Slide).where(Slide.lesson_id == lesson_id).order_by(Slide.number))).scalars())
        assert len(rows) == 4 and [row.number for row in rows] == [1, 2, 3, 4]
        assert await db.get(Slide, removed) is None
        assert not list((await db.execute(select(SlideVersion).where(SlideVersion.slide_id == removed))).scalars())

        (await db.get(GenerationJob, job_id)).status = 'succeeded'
        await db.commit()
        with pytest.raises(AppError, match='existing slide position'):
            await arrange_slides(db, owner, lesson_id, action='move', number=1, target=99)
        for _ in range(3):
            job_id, _ = await arrange_slides(db, owner, lesson_id, action='delete', number=1)
            (await db.get(GenerationJob, job_id)).status = 'succeeded'
            await db.commit()
        with pytest.raises(AppError, match='at least one slide'):
            await arrange_slides(db, owner, lesson_id, action='delete', number=1)

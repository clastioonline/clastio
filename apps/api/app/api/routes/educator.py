"""Async, owner-scoped UAE educator planners, demos and reusable resource guides."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select

from app.core.deps import DB, CurrentUser
from app.core.ratelimit import rate_limit
from app.generation.educator_specs import EducationStage, StrictContent, UAEPlanContent
from app.models import DemoClass, DigitalResource, LessonPlan
from app.services import educator

router = APIRouter(tags=['educator'])


@router.post('/lesson-plans', status_code=202, dependencies=[Depends(rate_limit('educator_plans', 30, 3600))])
async def create_plan(data: educator.PlanRequest, user: CurrentUser, db: DB):
    row, job_id = await educator.create_plan(db, user, data)
    return {'lesson_plan_id': str(row.id), 'job_id': str(job_id), 'lesson_plan': educator.summary(row)}


@router.get('/lesson-plans')
async def list_plans(user: CurrentUser, db: DB, subject: str | None = None,
                     education_stage: EducationStage | None = None, limit: int = Query(100, ge=1, le=200)):
    query = select(LessonPlan).where(LessonPlan.owner_id == user.id)
    if subject:
        query = query.where(LessonPlan.subject == subject)
    if education_stage:
        query = query.where(LessonPlan.education_stage == education_stage)
    rows = (await db.execute(query.order_by(LessonPlan.updated_at.desc()).limit(limit))).scalars().all()
    return {'items': [educator.summary(row) for row in rows]}


@router.get('/lesson-plans/{identifier}')
async def get_plan(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return await educator.detail(db, await educator.owned(db, LessonPlan, identifier, user.id))


class PlanUpdate(StrictContent):
    version: int = Field(ge=1)
    content: UAEPlanContent


@router.put('/lesson-plans/{identifier}')
async def update_plan(identifier: uuid.UUID, data: PlanUpdate, user: CurrentUser, db: DB):
    row = await educator.update_plan(db, user, identifier, data.content, data.version)
    return await educator.detail(db, row)


class PlanReview(StrictContent):
    version: int = Field(ge=1)
    notes: str = Field(default='', max_length=2000)


@router.post('/lesson-plans/{identifier}/review')
async def review_plan(identifier: uuid.UUID, data: PlanReview, user: CurrentUser, db: DB):
    row = await educator.review_plan(db, user, identifier, data.version, data.notes)
    return await educator.detail(db, row)


@router.post('/lesson-plans/{identifier}/export', status_code=202,
             dependencies=[Depends(rate_limit('educator_exports', 60, 3600))])
async def export_plan(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return {'job_id': str(await educator.start_export(db, user, 'plan', identifier))}


@router.delete('/lesson-plans/{identifier}')
async def delete_plan(identifier: uuid.UUID, user: CurrentUser, db: DB):
    row = await educator.owned(db, LessonPlan, identifier, user.id)
    await educator.delete_record(db, row)
    return {'ok': True}


@router.post('/demo-classes', status_code=202, dependencies=[Depends(rate_limit('educator_demos', 20, 3600))])
async def create_demo(data: educator.DemoRequest, user: CurrentUser, db: DB):
    row, job_id = await educator.create_demo(db, user, data)
    return {'demo_class_id': str(row.id), 'job_id': str(job_id), 'demo_class': educator.summary(row)}


@router.get('/demo-classes')
async def list_demos(user: CurrentUser, db: DB, subject: str | None = None,
                     limit: int = Query(100, ge=1, le=200)):
    query = select(DemoClass).where(DemoClass.owner_id == user.id)
    if subject:
        query = query.where(DemoClass.subject == subject)
    rows = (await db.execute(query.order_by(DemoClass.updated_at.desc()).limit(limit))).scalars().all()
    return {'items': [educator.summary(row) for row in rows]}


@router.get('/demo-classes/{identifier}')
async def get_demo(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return await educator.detail(db, await educator.owned(db, DemoClass, identifier, user.id))


@router.post('/demo-classes/{identifier}/export', status_code=202,
             dependencies=[Depends(rate_limit('educator_exports', 60, 3600))])
async def export_demo(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return {'job_id': str(await educator.start_export(db, user, 'demo', identifier))}


@router.delete('/demo-classes/{identifier}')
async def delete_demo(identifier: uuid.UUID, user: CurrentUser, db: DB):
    row = await educator.owned(db, DemoClass, identifier, user.id)
    await educator.delete_record(db, row)
    return {'ok': True}


@router.get('/digital-resources')
async def list_resources(user: CurrentUser, db: DB, subject: str | None = None,
                         education_stage: EducationStage | None = None,
                         curriculum: str | None = None, grade: str | None = None, language: str | None = None,
                         limit: int = Query(100, ge=1, le=200)):
    query = select(DigitalResource).where(DigitalResource.owner_id == user.id)
    for field, value in [('subject', subject), ('education_stage', education_stage),
                         ('curriculum', curriculum), ('grade', grade), ('language', language)]:
        if value:
            query = query.where(getattr(DigitalResource, field) == value)
    rows = (await db.execute(query.order_by(DigitalResource.updated_at.desc()).limit(limit))).scalars().all()
    return {'items': [educator.summary(row) for row in rows]}


@router.post('/digital-resources/generate', status_code=202,
             dependencies=[Depends(rate_limit('educator_resources', 20, 3600))])
async def generate_resource(data: educator.ResourceRequest, user: CurrentUser, db: DB):
    row, job_id, cached = await educator.create_resource(db, user, data)
    return {'resource_id': str(row.id), 'job_id': str(job_id) if job_id else None,
            'resource': educator.summary(row), 'cached': cached}


@router.get('/digital-resources/{identifier}')
async def get_resource(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return await educator.detail(db, await educator.owned(db, DigitalResource, identifier, user.id))


@router.post('/digital-resources/{identifier}/export', status_code=202,
             dependencies=[Depends(rate_limit('educator_exports', 60, 3600))])
async def export_resource(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return {'job_id': str(await educator.start_export(db, user, 'resource', identifier))}


@router.post('/digital-resources/{identifier}/regenerate', status_code=202,
             dependencies=[Depends(rate_limit('educator_resources', 20, 3600))])
async def retry_resource(identifier: uuid.UUID, user: CurrentUser, db: DB):
    return {'job_id': str(await educator.retry_resource(db, user, identifier))}


@router.delete('/digital-resources/{identifier}')
async def delete_resource(identifier: uuid.UUID, user: CurrentUser, db: DB):
    row = await educator.owned(db, DigitalResource, identifier, user.id)
    await educator.delete_record(db, row)
    return {'ok': True}

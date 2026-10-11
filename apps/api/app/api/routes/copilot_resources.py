"""Printable resources produced by the dedicated teacher copilot."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field, model_validator
from sqlalchemy import select

from app.core.deps import DB, CurrentUser
from app.core.ratelimit import rate_limit
from app.generation.educator_specs import (
    CurriculumText,
    EducationStage,
    Framework,
    GradeText,
    SubjectText,
    TitleText,
)
from app.models import DigitalResource
from app.services import copilot_resources
from app.services.educator import SourceRequest

router=APIRouter(tags=['teacher-copilot'])


class CopilotRequest(SourceRequest):
    request:str=Field(min_length=5,max_length=2000)
    topic:TitleText|None=None
    subject:SubjectText
    grade:GradeText|None=None
    education_stage:EducationStage='secondary'
    curriculum:CurriculumText='british'
    language:Literal['en','ar']='en'
    framework:Framework='not_specified'
    conversation_id:uuid.UUID|None=None

    @model_validator(mode='after')
    def school_grade(self):
        self.request = self.request.strip()
        if len(self.request) < 5:
            raise ValueError('Write a classroom task request of at least five characters.')
        if self.education_stage!='university' and not (self.grade or '').strip():
            raise ValueError('Choose a grade or year for a school task.')
        if self.education_stage == 'university' and self.framework in {'khda', 'adek', 'moe'}:
            raise ValueError('Choose Other or Not specified for university teaching.')
        return self


@router.post('/copilot/resources',dependencies=[Depends(rate_limit('copilot_resource',20,3600))])
async def create_printable(body:CopilotRequest,user:CurrentUser,db:DB):
    from app.services.educator import resource_out
    conversation, history = await copilot_resources.prepare_conversation(db, user, body)
    payload = {**body.model_dump(mode='json'), 'conversation_id': str(conversation.id),
               '_conversation_context': history}
    row,job_id,cached=await copilot_resources.create_task(db,user,payload)
    await copilot_resources.record_queued_response(db, conversation, row, cached)
    await db.refresh(row)
    return {'resource':await resource_out(db,row),'job_id':str(job_id) if job_id else None,'cached':cached,
            'conversation_id': str(conversation.id)}


@router.get('/copilot/resources')
async def printable_history(user:CurrentUser,db:DB):
    from app.services.educator import resource_out
    rows=(await db.execute(select(DigitalResource).where(DigitalResource.owner_id==user.id,
        DigitalResource.content['resource_type'].astext=='copilot_task')
        .order_by(DigitalResource.created_at.desc()).limit(50))).scalars().all()
    return {'items':[await resource_out(db,row) for row in rows]}


@router.get('/copilot/conversations')
async def conversation_history(user:CurrentUser,db:DB):
    return await copilot_resources.conversation_history(db, user)


@router.get('/copilot/conversations/{conversation_id}')
async def conversation_detail(conversation_id:uuid.UUID,user:CurrentUser,db:DB):
    return await copilot_resources.conversation_detail(db, user, conversation_id)

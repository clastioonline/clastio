"""Admin-composed push campaigns using the existing consent-aware delivery outbox."""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.db import get_sessionmaker, utcnow
from app.core.permissions import permissions_for
from app.jobs.queue import PermanentJobError
from app.models import TeacherPreference, User, UserSession
from app.models.push import PushDelivery, PushSubscription
from app.services.notifications import PREF_KEY
from app.services.push import push_configured


class CampaignIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=500)
    link: str = Field(default='/notifications', max_length=500)
    audience: Literal['teachers', 'staff', 'everyone', 'selected'] = 'teachers'
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    template: Literal['custom', 'update', 'maintenance', 'reminder', 'welcome'] = 'custom'

    @field_validator('title', 'body', mode='before')
    @classmethod
    def nonblank(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Enter a message')
        return value.strip()

    @field_validator('link')
    @classmethod
    def internal_link(cls, value):
        if not value.startswith('/') or value.startswith('//') or '\\' in value or any(ord(c) < 32 for c in value):
            raise ValueError('Use an internal app path such as /notifications')
        return value


def audience_query(data):
    query = select(User.id).where(User.status == 'active')
    if data.audience == 'teachers':
        query = query.where(User.role == 'teacher')
    elif data.audience == 'staff':
        query = query.where(User.role == 'admin')
    elif data.audience == 'selected':
        query = query.where(User.id.in_(data.user_ids))
    return query


def devices_query(data):
    return select(PushSubscription).join(UserSession, UserSession.id == PushSubscription.session_id).join(
        TeacherPreference, (TeacherPreference.user_id == PushSubscription.user_id) &
        (TeacherPreference.key == PREF_KEY)).where(
        PushSubscription.user_id.in_(audience_query(data)), PushSubscription.marketing_enabled.is_(True),
        UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow(), UserSession.user_id == PushSubscription.user_id,
        TeacherPreference.value['announcement']['push'].as_boolean().is_(True))


async def preview(db, data):
    devices = devices_query(data).subquery()
    users, count = (await db.execute(select(func.count(func.distinct(devices.c.user_id)), func.count())
                                    .select_from(devices))).one()
    total = await db.scalar(select(func.count()).select_from(audience_query(data).subquery()))
    return {'title': data.title, 'body': data.body, 'link': data.link, 'users': users,
            'devices': count, 'audience_users': total, 'configured': push_configured()}


async def handle_campaign(ctx):
    data = CampaignIn.model_validate(ctx.payload)
    key = f'admin-push:{ctx.job_id}'
    async with get_sessionmaker()() as db:
        admin = await db.get(User, ctx.owner_id)
        if (not admin or admin.status != 'active' or
                'announcements.manage' not in permissions_for(admin.role, admin.admin_role)):
            raise PermanentJobError('The sender no longer has permission to send notifications.')
        # Capture device IDs, then commit in bounded batches. Retries cannot duplicate device deliveries.
        ids = list((await db.execute(devices_query(data).with_only_columns(PushSubscription.id))).scalars())
        for start in range(0, len(ids), 500):
            devices = list((await db.execute(devices_query(data).where(
                PushSubscription.id.in_(ids[start:start + 500])))).scalars())
            if devices:
                await db.execute(insert(PushDelivery).values([{
                    'id': uuid.uuid4(), 'subscription_id': device.id, 'user_id': device.user_id,
                    'category': 'announcement', 'title': data.title, 'body': data.body, 'link': data.link,
                    'dedupe_key': key, 'status': 'queued', 'attempts': 0,
                    'created_at': utcnow(), 'send_after': utcnow(),
                } for device in devices]).on_conflict_do_nothing(index_elements=['subscription_id', 'dedupe_key']))
                await db.commit()
            await ctx.progress(min(95, int((start + len(devices)) / max(1, len(ids)) * 95)), 'Queueing push notifications')
        count = await db.scalar(select(func.count()).select_from(PushDelivery).where(PushDelivery.dedupe_key == key))
    return {'queued_devices': count or 0}

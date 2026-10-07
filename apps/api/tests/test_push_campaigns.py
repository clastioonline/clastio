"""Consent-aware admin campaigns, real PostgreSQL outbox, no push service calls."""
import uuid
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.jobs.queue import JobContext, PermanentJobError
from app.models import Base, TeacherPreference, User, UserSession
from app.models.push import PushDelivery, PushSubscription
from app.services.notifications import PREF_KEY
from app.services.push_campaigns import CampaignIn, handle_campaign, preview
from tests.test_slide_sequence import editor_database  # noqa: F401


@pytest.mark.parametrize('link', ['https://example.com', '//example.com', '/\\evil', '/path\n'])
def test_campaign_rejects_external_or_malformed_destinations(link):
    with pytest.raises(ValidationError):
        CampaignIn(title='Update', body='Message', link=link)


async def test_campaign_consent_session_and_retry_deduplication(editor_database):  # noqa: F811
    owner_id, other_id, _, _ = editor_database
    engine = create_engine(get_settings().sync_database_url)
    names = {'push_deliveries', 'push_subscriptions', 'user_sessions', 'teacher_preferences'}
    while True:
        refs = {fk.column.table.name for name in names for fk in Base.metadata.tables[name].foreign_keys}
        if refs <= names:
            break
        names |= refs
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in names])
    engine.dispose()
    async with get_sessionmaker()() as db:
        sender = User(email=f'campaign-{uuid.uuid4()}@example.com', role='admin', admin_role='admin', name='Sender')
        db.add(sender)
        await db.flush()
        db.add(TeacherPreference(user_id=owner_id, key=PREF_KEY, value={'announcement': {'push': True}}))
        for uid, marketing, expired in [(owner_id, True, False), (owner_id, True, False),
                                       (owner_id, False, False), (owner_id, True, True), (other_id, True, False)]:
            session = UserSession(user_id=uid, expires_at=utcnow() + timedelta(days=-1 if expired else 1))
            db.add(session)
            await db.flush()
            device = PushSubscription(user_id=uid, session_id=session.id, endpoint_hash=uuid.uuid4().hex,
                endpoint='https://fcm.googleapis.com/fcm/send/test', p256dh='not-used', auth='not-used', marketing_enabled=marketing)
            db.add(device)
        await db.commit()
        data = CampaignIn(title='New feature', body='Try the updated editor', audience='selected', user_ids=[owner_id, other_id])
        result = await preview(db, data)
        assert result['users'] == 1 and result['devices'] == 2 and result['audience_users'] == 2
        sender_id = sender.id
    ctx = JobContext(job_id=uuid.uuid4(), owner_id=sender_id, payload=data.model_dump(mode='json'))
    assert (await handle_campaign(ctx))['queued_devices'] == 2
    assert (await handle_campaign(ctx))['queued_devices'] == 2
    async with get_sessionmaker()() as db:
        rows = list((await db.execute(select(PushDelivery).where(PushDelivery.dedupe_key == f'admin-push:{ctx.job_id}'))).scalars())
        assert len(rows) == 2 and all(row.user_id == owner_id for row in rows)
        sender = await db.get(User, sender_id)
        sender.admin_role = 'support'
        await db.commit()
    with pytest.raises(PermanentJobError, match='permission'):
        await handle_campaign(ctx)


@pytest.mark.parametrize('title,body', [('  a  ', 'Message'), ('Update', '   ')])
def test_campaign_requires_meaningful_message(title, body):
    with pytest.raises(ValidationError):
        CampaignIn(title=title, body=body)

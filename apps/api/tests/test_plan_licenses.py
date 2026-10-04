"""License issuance and concurrent redemption against the isolated test database."""
import asyncio
import uuid

from app.core.security import create_access_token
from tests.conftest import make_staff, make_user


async def verified_teacher(client):
    teacher = await make_user(client, plan='free')
    token = create_access_token(uuid.UUID(teacher['id']), extra={'typ': 'verify', 'em': teacher['email']})
    result = await client.post('/api/v1/auth/verify-email', json={'token': token})
    assert result.status_code == 200, result.text
    return teacher


async def issue(client, admin):
    result = await client.post('/api/v1/admin/licenses', headers=admin['headers'],
                               json={'plan': 'pro', 'months': 12, 'valid_days': 30})
    assert result.status_code == 200, result.text
    return result.json()


async def test_teachers_cannot_issue_licenses_and_only_hashes_are_persisted(client):
    from sqlalchemy import select

    from app.core.db import get_sessionmaker
    from app.models import PlanLicense

    teacher = await verified_teacher(client)
    refused = await client.post('/api/v1/admin/licenses', headers=teacher['headers'], json={'plan': 'pro'})
    assert refused.status_code == 403
    admin = await make_staff(client)
    license = await issue(client, admin)
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(PlanLicense).where(PlanLicense.id == uuid.UUID(license['id'])))).scalar_one()
        assert license['key'] not in row.key_hash
        assert row.key_suffix == license['key'][-8:]
    listed = await client.get('/api/v1/admin/licenses', headers=admin['headers'])
    assert listed.status_code == 200
    assert license['key'] not in listed.text


async def test_one_license_can_be_redeemed_by_only_one_teacher_concurrently(client):
    admin = await make_staff(client)
    license = await issue(client, admin)
    teachers = [await verified_teacher(client), await verified_teacher(client)]
    results = await asyncio.gather(*(client.post('/api/v1/billing/licenses/redeem', headers=t['headers'],
                                                 json={'key': license['key']}) for t in teachers))
    assert sorted(r.status_code for r in results) == [200, 422]
    winner = teachers[next(i for i, result in enumerate(results) if result.status_code == 200)]
    usage = (await client.get('/api/v1/me/usage', headers=winner['headers'])).json()
    assert usage['plan']['code'] == 'pro'
    assert usage['subscription']['provider'] == 'manual'


async def test_one_teacher_cannot_consume_two_plan_licenses_concurrently(client):
    from sqlalchemy import select

    from app.core.db import get_sessionmaker
    from app.models import PlanLicense

    admin = await make_staff(client)
    licenses = [await issue(client, admin), await issue(client, admin)]
    teacher = await verified_teacher(client)
    results = await asyncio.gather(*(client.post('/api/v1/billing/licenses/redeem', headers=teacher['headers'],
                                                 json={'key': license['key']}) for license in licenses))
    assert sorted(r.status_code for r in results) == [200, 409]
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(PlanLicense).where(PlanLicense.id.in_(
            [uuid.UUID(license['id']) for license in licenses])))).scalars().all()
        assert sum(row.redeemed_at is not None for row in rows) == 1

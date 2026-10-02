import asyncio
import os
import uuid

import pytest
from redis.asyncio import Redis

from app.ai.base import AIError
from app.ai.capacity import provider_capacity
from app.core import security


@pytest.mark.asyncio
async def test_password_work_does_not_block_event_loop(monkeypatch):
    import time
    monkeypatch.setattr(security, 'verify_password', lambda *_: (time.sleep(.1), True)[1])
    work = asyncio.create_task(security.verify_password_async('password', 'hash'))
    await asyncio.sleep(.02)
    assert not work.done()
    assert await work


@pytest.mark.asyncio
async def test_capacity_fails_closed():
    class BrokenRedis:
        async def eval(self, *_):
            raise ConnectionError('offline')
    entered = False
    with pytest.raises(AIError, match='no provider call'):
        async with provider_capacity(BrokenRedis(), limit=2, wait_s=1):
            entered = True
    assert not entered


@pytest.mark.asyncio
async def test_shared_redis_capacity_and_release():
    url = os.getenv('CAPACITY_REDIS_TEST_URL')
    if not url:
        pytest.skip('Dedicated capacity Redis not configured')
    client = Redis.from_url(url)
    key = f'test:capacity:{uuid.uuid4().hex}'
    active = peak = 0
    async def call():
        nonlocal active, peak
        async with provider_capacity(client, limit=2, wait_s=10, lease_s=.3, key=key):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.4)
            active -= 1
    try:
        await asyncio.gather(*(call() for _ in range(10)))
        assert peak == 2
        assert await client.zcard(key) == 0
        async def cancelable():
            async with provider_capacity(client, limit=2, wait_s=1, key=key):
                await asyncio.sleep(20)
        task = asyncio.create_task(cancelable())
        while await client.zcard(key) == 0:
            await asyncio.sleep(.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert await client.zcard(key) == 0
    finally:
        await client.delete(key)
        await client.aclose()


@pytest.mark.asyncio
async def test_competing_claims_respect_owner_limit(client, teacher):
    from app.core.db import get_sessionmaker
    from app.jobs.queue import claim
    from app.models import GenerationJob
    queue = f'cap-{uuid.uuid4().hex[:12]}'
    async with get_sessionmaker()() as db:
        for _ in range(2):
            db.add(GenerationJob(owner_id=uuid.UUID(teacher['id']), type='capacity_test', queue=queue,
                                 status='queued', payload={}, max_concurrent=1))
        await db.commit()
    claims = await asyncio.gather(claim([queue]), claim([queue]))
    assert sum(job is not None for job in claims) == 1


@pytest.mark.asyncio
async def test_running_job_renews_heartbeat(client, monkeypatch):
    from app.core.config import get_settings
    from app.core.db import get_sessionmaker
    from app.jobs.queue import HANDLERS, run_job
    from app.models import GenerationJob
    entered, release = asyncio.Event(), asyncio.Event()
    async def slow(_):
        entered.set()
        await release.wait()
        return {}
    monkeypatch.setitem(HANDLERS, 'heartbeat_test', slow)
    monkeypatch.setattr(get_settings(), 'job_heartbeat_s', .03)
    async with get_sessionmaker()() as db:
        job = GenerationJob(type='heartbeat_test', status='queued', payload={})
        db.add(job)
        await db.commit()
        job_id = job.id
    task = asyncio.create_task(run_job(job_id))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        async with get_sessionmaker()() as db:
            before = (await db.get(GenerationJob, job_id)).locked_at
        for _ in range(50):
            await asyncio.sleep(.03)
            async with get_sessionmaker()() as db:
                after = (await db.get(GenerationJob, job_id)).locked_at
            if after > before:
                break
        assert after > before
    finally:
        release.set()
        await task

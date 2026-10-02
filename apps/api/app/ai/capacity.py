"""Shared capacity for paid provider calls across API and worker processes."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from app.ai.base import AIError

logger = logging.getLogger('ai.capacity')

ACQUIRE = """
local now = redis.call('TIME'); now = tonumber(now[1]) + tonumber(now[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[2]) * 2))
return 1
"""
RENEW = """
if not redis.call('ZSCORE', KEYS[1], ARGV[2]) then return 0 end
local now = redis.call('TIME'); now = tonumber(now[1]) + tonumber(now[2]) / 1000000
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[1]), ARGV[2])
redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[1]) * 2))
return 1
"""


@asynccontextmanager
async def provider_capacity(client, *, limit: int, wait_s: float, lease_s: float = 240,
                            key: str = 'ai:capacity:v1'):
    if client is None:
        yield
        return
    token = uuid.uuid4().hex
    deadline = time.monotonic() + wait_s
    try:
        while not await client.eval(ACQUIRE, 1, key, limit, lease_s, token):
            if time.monotonic() >= deadline:
                raise AIError('AI capacity is busy; try again shortly', retryable=False)
            await asyncio.sleep(.2)
    except AIError:
        raise
    except Exception as exc:
        raise AIError('Shared AI capacity is unavailable; no provider call was started', retryable=False) from exc
    stopped = asyncio.Event()
    owner = asyncio.current_task()

    async def renew():
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), timeout=lease_s / 3)
            except TimeoutError:
                try:
                    if not await client.eval(RENEW, 1, key, lease_s, token):
                        raise RuntimeError('capacity lease expired')
                except Exception:
                    logger.error('AI capacity lease lost; canceling provider request')
                    if owner:
                        owner.cancel('AI capacity lease lost')
                    return

    task = asyncio.create_task(renew())
    try:
        yield
    finally:
        stopped.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            await client.zrem(key, token)
        except Exception:
            logger.warning('AI lease release unavailable; lease will expire')

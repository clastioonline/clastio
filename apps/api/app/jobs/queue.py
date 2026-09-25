"""Postgres-backed job queue (SELECT ... FOR UPDATE SKIP LOCKED).

Long-running work never runs inside HTTP requests: routes enqueue a job and return its id; the worker
claims jobs, runs registered handlers and records progress, cost, errors and retries. Clients follow
progress via GET /jobs/{id} or the SSE stream.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
import traceback
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.logging import job_id_var, log
from app.models import GenerationJob

logger = logging.getLogger("jobs")
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


@dataclass
class JobContext:
    job_id: uuid.UUID
    owner_id: uuid.UUID | None
    payload: dict[str, Any]

    async def progress(self, pct: int, stage: str | None = None) -> None:
        async with get_sessionmaker()() as s:
            values: dict[str, Any] = {"progress": max(0, min(100, int(pct)))}
            if stage is not None:
                values["stage"] = stage[:120]
            await s.execute(update(GenerationJob).where(GenerationJob.id == self.job_id).values(**values))
            await s.commit()


Handler = Callable[[JobContext], Awaitable[dict[str, Any] | None]]
HANDLERS: dict[str, Handler] = {}
QUEUES: dict[str, str] = {}


def handler(job_type: str, queue: str = "default"):
    def deco(fn: Handler) -> Handler:
        HANDLERS[job_type] = fn
        QUEUES[job_type] = queue
        return fn

    return deco


def payload_hash(job_type: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps([job_type, payload], sort_keys=True, default=str).encode()).hexdigest()


async def enqueue(db: AsyncSession, job_type: str, payload: dict[str, Any], *, owner_id: uuid.UUID | None,
                  parent_id: uuid.UUID | None = None, max_attempts: int = 3, delay_s: float = 0,
                  dedupe: bool = False) -> GenerationJob:
    """Create a job in the caller's transaction. With dedupe, reuse an identical queued/running job."""
    h = payload_hash(job_type, payload)
    if dedupe:
        existing = (await db.execute(select(GenerationJob).where(
            GenerationJob.input_hash == h, GenerationJob.type == job_type, GenerationJob.owner_id == owner_id,
            GenerationJob.status.in_(["queued", "running"])))).scalars().first()
        if existing:
            return existing
    job = GenerationJob(type=job_type, queue=QUEUES.get(job_type, "default"), payload=payload, owner_id=owner_id,
                        parent_id=parent_id, max_attempts=max_attempts, input_hash=h,
                        run_after=utcnow() + timedelta(seconds=delay_s), stage="Queued")
    db.add(job)
    await db.flush()
    return job


async def run_inline_if_configured(job_ids: list[uuid.UUID]) -> None:
    """Tests / single-process dev: execute jobs right away instead of waiting for a worker."""
    if not get_settings().run_jobs_inline:
        return
    for jid in job_ids:
        await run_job(jid)


async def claim(queues: list[str] | None = None) -> uuid.UUID | None:
    async with get_sessionmaker()() as s:
        q = """
            UPDATE generation_jobs SET status='running', locked_by=:w, locked_at=now(), started_at=now(),
                   attempts=attempts+1, stage=COALESCE(NULLIF(stage,'Queued'),'Starting')
            WHERE id = (
                SELECT id FROM generation_jobs
                WHERE status='queued' AND run_after <= now() {queue_filter}
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1)
            RETURNING id
        """.format(queue_filter="AND queue = ANY(:queues)" if queues else "")
        params: dict[str, Any] = {"w": WORKER_ID}
        if queues:
            params["queues"] = queues
        row = (await s.execute(text(q), params)).first()
        await s.commit()
        return row[0] if row else None


async def run_job(job_id: uuid.UUID) -> None:
    async with get_sessionmaker()() as s:
        job = await s.get(GenerationJob, job_id)
        if job is None:
            return
        if job.status == "queued":  # inline execution path
            job.status, job.started_at, job.attempts = "running", utcnow(), job.attempts + 1
            await s.commit()
        ctx = JobContext(job_id=job.id, owner_id=job.owner_id, payload=dict(job.payload))
        job_type, attempts, max_attempts = job.type, job.attempts, job.max_attempts
    token = job_id_var.set(str(job_id))
    fn = HANDLERS.get(job_type)
    try:
        if fn is None:
            raise RuntimeError(f"No handler registered for job type {job_type}")
        result = await fn(ctx)
        async with get_sessionmaker()() as s:
            await s.execute(update(GenerationJob).where(GenerationJob.id == job_id).values(
                status="succeeded", progress=100, stage="Done", result=result or {}, completed_at=utcnow(),
                error=None, locked_by=None))
            await s.commit()
        log(logger, logging.INFO, "job_succeeded", type=job_type)
    except Exception as e:  # noqa: BLE001 - job boundary
        retryable = not isinstance(e, (PermanentJobError,)) and attempts < max_attempts
        tb = traceback.format_exc(limit=8)
        log(logger, logging.ERROR, "job_failed", type=job_type, error=str(e), retry=retryable, trace=tb)
        async with get_sessionmaker()() as s:
            values: dict[str, Any] = {"error": str(e)[:4000], "locked_by": None}
            if retryable:
                values.update(status="queued", stage="Retrying", run_after=utcnow() + timedelta(seconds=10 * attempts))
            else:
                values.update(status="failed", stage="Failed", completed_at=utcnow())
            await s.execute(update(GenerationJob).where(GenerationJob.id == job_id).values(**values))
            await s.commit()
        if not retryable:
            failure_hook = FAILURE_HOOKS.get(job_type)
            if failure_hook:
                try:
                    await failure_hook(ctx, str(e))
                except Exception:  # noqa: BLE001
                    pass
    finally:
        job_id_var.reset(token)


class PermanentJobError(Exception):
    """Raise from a handler to fail without retrying (bad input, limits exceeded...)."""


FAILURE_HOOKS: dict[str, Callable[[JobContext, str], Awaitable[None]]] = {}


def on_failure(job_type: str):
    def deco(fn):
        FAILURE_HOOKS[job_type] = fn
        return fn

    return deco


async def recover_stale(max_age_minutes: int = 30) -> int:
    """Requeue jobs whose worker died mid-run."""
    async with get_sessionmaker()() as s:
        res = await s.execute(text(
            "UPDATE generation_jobs SET status='queued', stage='Recovered', locked_by=NULL "
            "WHERE status='running' AND locked_at < now() - make_interval(mins => :m)"), {"m": max_age_minutes})
        await s.commit()
        return res.rowcount or 0


async def worker_loop(concurrency: int = 4, queues: list[str] | None = None,
                      stop: asyncio.Event | None = None) -> None:
    import app.jobs.handlers  # noqa: F401  (register handlers)

    stop = stop or asyncio.Event()
    sem = asyncio.Semaphore(concurrency)
    running: set[asyncio.Task] = set()
    poll = get_settings().worker_poll_interval_s
    log(logger, logging.INFO, "worker_started", worker=WORKER_ID, concurrency=concurrency)
    await recover_stale()
    while not stop.is_set():
        await sem.acquire()
        job_id = await claim(queues)
        if job_id is None:
            sem.release()
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll)
            except TimeoutError:
                pass
            continue

        async def _run(jid=job_id):
            try:
                await run_job(jid)
            finally:
                sem.release()

        t = asyncio.create_task(_run())
        running.add(t)
        t.add_done_callback(running.discard)
    if running:
        await asyncio.gather(*running, return_exceptions=True)

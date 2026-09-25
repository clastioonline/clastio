"""Background worker: runs queued jobs and the minute-level scheduler (WhatsApp daily plans / check-ins).

    python -m app.worker --concurrency 4
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging, log
from app.jobs.queue import recover_stale, worker_loop

logger = logging.getLogger("worker")


HOUSEKEEPING_EVERY = 60  # scheduler ticks (minutes)


async def _step(name: str, fn) -> None:
    """Run one scheduler step; a failure is logged and never stops the others."""
    try:
        result = await fn()
        if result and (not isinstance(result, dict) or any(result.values())):
            log(logger, logging.INFO, name, result=result)
    except Exception as e:  # noqa: BLE001
        log(logger, logging.ERROR, "scheduler_error", step=name, error=str(e)[:500])


async def scheduler(stop: asyncio.Event) -> None:
    from app.services.lifecycle import purge_due_accounts, retention_cleanup
    from app.services.notify import send_pending_emails
    from app.services.whatsapp import scheduler_tick

    tick = 0
    while not stop.is_set():
        await _step("whatsapp_tick", scheduler_tick)
        await _step("recover_stale", recover_stale)
        await _step("emails_sent", send_pending_emails)
        if tick % HOUSEKEEPING_EVERY == 0:
            await _step("retention_cleanup", retention_cleanup)
            await _step("accounts_purged", purge_due_accounts)
        tick += 1
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except TimeoutError:
            pass


async def main(concurrency: int, queues: list[str] | None, with_scheduler: bool) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover
            pass
    tasks = [asyncio.create_task(worker_loop(concurrency, queues, stop))]
    if with_scheduler:
        tasks.append(asyncio.create_task(scheduler(stop)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--queues", default="", help="comma-separated queues (default: all)")
    ap.add_argument("--no-scheduler", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.concurrency, [q for q in a.queues.split(",") if q] or None, not a.no_scheduler))

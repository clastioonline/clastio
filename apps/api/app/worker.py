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


async def scheduler(stop: asyncio.Event) -> None:
    from app.services.whatsapp import scheduler_tick

    while not stop.is_set():
        try:
            sent = await scheduler_tick()
            if any(sent.values()):
                log(logger, logging.INFO, "scheduler_tick", **sent)
            await recover_stale()
        except Exception as e:  # noqa: BLE001
            log(logger, logging.ERROR, "scheduler_error", error=str(e))
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

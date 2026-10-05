from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.jobs import queue


async def test_recovery_uses_missed_heartbeats(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=1)
    manager = AsyncMock()
    manager.__aenter__.return_value = session
    monkeypatch.setattr(queue, "get_sessionmaker", lambda: lambda: manager)
    monkeypatch.setattr(queue, "get_settings", lambda: SimpleNamespace(
        job_stale_after_s=300, job_heartbeat_s=30))
    assert await queue.recover_stale() == 1
    assert session.execute.call_args.args[1] == {"seconds": 300}
    session.commit.assert_awaited_once()


async def test_recovery_allows_three_heartbeat_intervals(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=0)
    manager = AsyncMock()
    manager.__aenter__.return_value = session
    monkeypatch.setattr(queue, "get_sessionmaker", lambda: lambda: manager)
    monkeypatch.setattr(queue, "get_settings", lambda: SimpleNamespace(
        job_stale_after_s=300, job_heartbeat_s=300))
    assert await queue.recover_stale() == 0
    assert session.execute.call_args.args[1] == {"seconds": 900}

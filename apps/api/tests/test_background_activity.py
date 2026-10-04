"""Work survives navigation and responses are isolated to their owners."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.jobs.queue import run_job
from app.models import ConversationMessage, GenerationJob, User
from tests.conftest import make_user


async def test_assistant_queues_returns_and_persists_after_request_ends(client, teacher, monkeypatch):
    monkeypatch.setattr(get_settings(), "run_jobs_inline", False)
    headers = {**teacher["headers"], "idempotency-key": "background-request-001"}
    r = await client.post("/api/v1/assistant/tasks", headers=headers,
                          json={"text": "What did I teach last week?"})
    assert r.status_code == 202, r.text
    ids = r.json()
    replay = await client.post("/api/v1/assistant/tasks", headers=headers,
                               json={"text": "What did I teach last week?"})
    assert replay.json() == ids
    path = f"/api/v1/assistant/conversations/{ids['conversation_id']}"
    before = (await client.get(path, headers=teacher["headers"])).json()
    assert before["job"]["status"] == "queued"
    assert [m["role"] for m in before["messages"]] == ["user"]
    # Execution happens independently, after the submit request has already returned.
    await run_job(uuid.UUID(ids["job_id"]))
    after = (await client.get(path, headers=teacher["headers"])).json()
    assert after["job"]["status"] == "succeeded"
    assert [m["role"] for m in after["messages"]] == ["user", "assistant"]
    assert after["messages"][-1]["content"]
    feed = (await client.get("/api/v1/activity", headers=teacher["headers"])).json()
    item = next(j for j in feed["items"] if j["id"] == ids["job_id"])
    assert item["href"] == f"/assistant?conversation={ids['conversation_id']}"
    notices = (await client.get("/api/v1/me/notifications", headers=teacher["headers"])).json()
    assert any(n["link"] == item["href"] for n in notices["items"])


async def test_pending_conversation_cannot_get_overlapping_replies(client, teacher, monkeypatch):
    monkeypatch.setattr(get_settings(), "run_jobs_inline", False)
    ids = (await client.post("/api/v1/assistant/tasks", headers=teacher["headers"], json={"text": "Hello"})).json()
    r = await client.post("/api/v1/assistant/tasks", headers=teacher["headers"],
                          json={"text": "Second message", "conversation_id": ids["conversation_id"]})
    assert r.status_code == 409
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(ConversationMessage).where(
            ConversationMessage.conversation_id == uuid.UUID(ids["conversation_id"])))).scalars().all()
        assert len(rows) == 1


async def test_activity_and_assistant_are_owner_scoped(client, teacher, monkeypatch):
    monkeypatch.setattr(get_settings(), "run_jobs_inline", False)
    ids = (await client.post("/api/v1/assistant/tasks", headers=teacher["headers"], json={"text": "Private question"})).json()
    other = await make_user(client)
    assert (await client.get(f"/api/v1/assistant/conversations/{ids['conversation_id']}", headers=other["headers"])).status_code == 404
    assert (await client.post("/api/v1/assistant/tasks", headers=other["headers"],
                             json={"text": "Reply", "conversation_id": ids["conversation_id"]})).status_code == 404
    feed = (await client.get("/api/v1/activity", headers=other["headers"])).json()
    assert ids["job_id"] not in [j["id"] for j in feed["items"]]


async def test_active_work_stays_visible_ahead_of_newer_history(client, teacher):
    uid = uuid.UUID(teacher["id"])
    async with get_sessionmaker()() as db:
        active = GenerationJob(owner_id=uid, type="source_indexing", status="running", payload={})
        db.add(active)
        await db.flush()
        active_id = str(active.id)
        for _ in range(105):
            db.add(GenerationJob(owner_id=uid, type="source_indexing", status="succeeded", payload={}))
        db.add(GenerationJob(owner_id=uid, type="source_indexing", status="failed", payload={}, error="secret-provider-internals"))
        await db.commit()
    r = await client.get("/api/v1/activity", headers=teacher["headers"])
    assert r.status_code == 200, r.text
    feed = r.json()
    assert feed["active_count"] == 1
    assert feed["items"][0]["id"] == active_id
    assert len(feed["items"]) == 100
    assert "secret-provider-internals" not in r.text
    assert "payload" not in feed["items"][0]


async def test_promotion_hides_teacher_activity_without_deleting_history(client, teacher):
    uid = uuid.UUID(teacher["id"])
    async with get_sessionmaker()() as db:
        active = GenerationJob(owner_id=uid, type="source_indexing", status="running", payload={})
        completed = GenerationJob(owner_id=uid, type="source_indexing", status="succeeded", payload={})
        db.add_all([active, completed])
        await db.commit()
        job_ids = {str(active.id), str(completed.id)}

    before = await client.get("/api/v1/activity", headers=teacher["headers"])
    assert before.status_code == 200, before.text
    assert before.json()["active_count"] == 1
    assert job_ids <= {j["id"] for j in before.json()["items"]}

    async with get_sessionmaker()() as db:
        user = await db.get(User, uid)
        user.role, user.admin_role = "admin", "support"
        await db.commit()

    promoted = await client.get("/api/v1/activity", headers=teacher["headers"])
    assert promoted.status_code == 200, promoted.text
    assert promoted.json() == {"items": [], "active_count": 0}

    async with get_sessionmaker()() as db:
        retained = (await db.execute(select(GenerationJob).where(GenerationJob.owner_id == uid))).scalars().all()
        assert job_ids <= {str(j.id) for j in retained}
        assert {j.status for j in retained if str(j.id) in job_ids} == {"running", "succeeded"}
        user = await db.get(User, uid)
        user.role, user.admin_role = "teacher", None
        await db.commit()

    restored = await client.get("/api/v1/activity", headers=teacher["headers"])
    assert restored.status_code == 200, restored.text
    assert restored.json()["active_count"] == 1
    assert job_ids <= {j["id"] for j in restored.json()["items"]}


async def test_failed_assistant_task_remains_discoverable(client, teacher, monkeypatch):
    from app.services import assistant

    monkeypatch.setattr(get_settings(), "run_jobs_inline", False)
    ids = (await client.post("/api/v1/assistant/tasks", headers=teacher["headers"], json={"text": "Hello"})).json()

    async def broken(*args, **kwargs):
        raise RuntimeError("private provider failure")
        yield  # marks this as an async generator

    monkeypatch.setattr(assistant, "converse", broken)
    await run_job(uuid.UUID(ids["job_id"]))
    feed = (await client.get("/api/v1/activity", headers=teacher["headers"])).json()
    item = next(j for j in feed["items"] if j["id"] == ids["job_id"])
    assert item["status"] == "failed"
    assert item["error"] and "private provider failure" not in item["error"]
    r = await client.get(f"/api/v1/assistant/conversations/{ids['conversation_id']}", headers=teacher["headers"])
    assert r.json()["messages"][0]["content"] == "Hello"

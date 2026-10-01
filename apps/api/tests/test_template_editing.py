from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.jobs.queue import run_job
from app.models import Template


@pytest.fixture
async def owned_template(teacher, seeded):
    async with get_sessionmaker()() as db:
        base = (await db.execute(select(Template).where(Template.owner_id.is_(None)))).scalars().first()
        template = Template(owner_id=uuid.UUID(teacher["id"]), name="Editable design",
                            mode=base.mode, base_storage_key=base.base_storage_key,
                            spec=base.spec, preview_keys=base.preview_keys)
        db.add(template)
        await db.commit()
        return str(template.id)


async def test_template_save_queues_preview_and_recovers(client, teacher, owned_template, monkeypatch):
    monkeypatch.setattr(get_settings(), "run_jobs_inline", False)
    path = f"/api/v1/templates/{owned_template}"
    r = await client.patch(path, headers=teacher["headers"], json={"name": "Updated design"})
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    detail = (await client.get(path, headers=teacher["headers"])).json()
    assert detail["name"] == "Updated design"
    assert detail["job"]["status"] == "queued"
    assert detail["can_edit"]
    overlap = await client.patch(path, headers=teacher["headers"], json={"name": "Overlap"})
    assert overlap.status_code == 409
    await run_job(uuid.UUID(job_id))
    result = (await client.get(path, headers=teacher["headers"])).json()
    assert result["job"]["status"] == "succeeded"
    assert result["previews"]
    assert result["previews"] != detail["previews"]
    feed = (await client.get("/api/v1/activity", headers=teacher["headers"])).json()
    task = next(j for j in feed["items"] if j["id"] == job_id)
    assert task["href"] == f"/templates/{owned_template}"


@pytest.mark.parametrize("patch", [{"name": "   "}, {"typography": {"title_pt": "bad"}},
                                  {"typography": {"body_pt": 100}}, {"colors": {"primary": "#ZZZZZZ"}}])
async def test_template_invalid_edits_are_rejected(client, teacher, owned_template, patch):
    r = await client.patch(f"/api/v1/templates/{owned_template}", headers=teacher["headers"], json=patch)
    assert r.status_code == 422, r.text

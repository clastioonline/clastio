import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.datastructures import UploadFile

from app.api.routes import content


@pytest.mark.parametrize("status,saved_template,should_enqueue", [
    ("ready", None, True),
    ("ready", uuid.uuid4(), False),
    ("processing", None, False),
    ("queued", None, False),
    ("failed", None, True),
])
async def test_repeat_upload_recovers_missing_design_without_duplicate_pending_jobs(
        monkeypatch, status, saved_template, should_enqueue):
    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    row = SimpleNamespace(id=uuid.uuid4(), filename="School.pptx", kind="style", size_bytes=10,
                          status=status, stage="Ready", error=None, page_count=16,
                          created_at=datetime.now(UTC))
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = saved_template
    db.execute.return_value = result
    monkeypatch.setattr(content.usage, "check_count_limit", AsyncMock())
    monkeypatch.setattr(content.usage, "check_storage", AsyncMock())
    monkeypatch.setattr(content, "upload_limit_mb", AsyncMock(return_value=100))
    monkeypatch.setattr(content, "store_upload", AsyncMock(return_value=(row, False)))
    enqueue = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(content, "enqueue", enqueue)
    monkeypatch.setattr(content, "run_inline_if_configured", AsyncMock())
    output = await content.upload(owner, db, UploadFile(io.BytesIO(b"slide data"), filename="School.pptx"),
                                  kind="style", name="School", rights_confirmed=True)
    assert output["duplicate"] is True
    assert bool(output["job_id"]) == should_enqueue
    assert enqueue.await_count == int(should_enqueue)
    if should_enqueue:
        assert row.status == "queued"
        assert enqueue.call_args.args[1] == "style_analysis"
        assert enqueue.call_args.kwargs["owner_id"] == owner.id
    db.commit.assert_awaited_once()

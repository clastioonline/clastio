import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import NotFound
from app.services import courses, styles


@pytest.mark.parametrize("refresh", [False, True])
async def test_template_upgrade_can_be_deferred_to_worker(monkeypatch, refresh):
    owner = uuid.uuid4()
    template = SimpleNamespace(id=uuid.uuid4(), owner_id=owner)
    db = AsyncMock()
    db.get.return_value = template
    upgrade = AsyncMock()
    monkeypatch.setattr(styles, "refresh_native_template", upgrade)

    result = await courses.resolve_template(db, owner, template.id, refresh=refresh)

    assert result is template
    if refresh:
        upgrade.assert_awaited_once_with(db, template)
    else:
        upgrade.assert_not_awaited()


async def test_deferred_upgrade_still_rejects_private_template(monkeypatch):
    template = SimpleNamespace(id=uuid.uuid4(), owner_id=uuid.uuid4(), is_shared=False)
    db = AsyncMock()
    db.get.return_value = template
    upgrade = AsyncMock()
    monkeypatch.setattr(styles, "refresh_native_template", upgrade)

    with pytest.raises(NotFound):
        await courses.resolve_template(db, uuid.uuid4(), template.id, refresh=False)
    upgrade.assert_not_awaited()

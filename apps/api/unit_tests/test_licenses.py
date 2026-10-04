import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routes.platform import LicenseRedeemIn, redeem_license
from app.core.errors import AppError
from app.services.licenses import generate_key, key_digest


def test_license_keys_are_random_and_digest_is_normalized():
    key = generate_key()
    assert key != generate_key()
    assert key_digest(key) == key_digest('  '+key.lower()+'  ')
    assert key not in key_digest(key)

async def test_active_plan_prevents_consuming_license(monkeypatch):
    monkeypatch.setattr('app.core.ratelimit.enforce', AsyncMock())
    monkeypatch.setattr('app.services.usage.active_subscription', AsyncMock(return_value=object()))
    db=AsyncMock()
    user=SimpleNamespace(id=uuid.uuid4(),role='teacher',email_verified=True)
    with pytest.raises(AppError) as exc:
        await redeem_license(LicenseRedeemIn(key=generate_key()),user,db)
    assert exc.value.code == 'license_active_plan'
    assert db.execute.await_count == 1
    db.commit.assert_not_called()

async def test_invalid_or_used_license_grants_nothing(monkeypatch):
    monkeypatch.setattr('app.core.ratelimit.enforce', AsyncMock())
    monkeypatch.setattr('app.services.usage.active_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr('app.services.billing.manageable_online_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr('app.services.billing.pending_checkout', AsyncMock(return_value=None))
    db=AsyncMock()
    db.execute.return_value=SimpleNamespace(mappings=lambda:SimpleNamespace(first=lambda:None))
    user=SimpleNamespace(id=uuid.uuid4(),role='teacher',email_verified=True)
    with pytest.raises(AppError) as exc:
        await redeem_license(LicenseRedeemIn(key=generate_key()),user,db)
    assert exc.value.code == 'invalid_license'
    db.add.assert_not_called()
    db.commit.assert_not_called()

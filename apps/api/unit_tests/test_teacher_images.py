import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.api.routes.content import CourseIn
from app.core.errors import NotFound
from app.services.courses import teacher_image_catalog
from app.services import assets
from test_stock_presentations import environment, slide


async def test_catalog_rejects_other_users_and_generated_assets():
    owner = uuid.uuid4()
    db = AsyncMock()
    for asset in [None, SimpleNamespace(owner_id=uuid.uuid4(), source='upload', kind='image'), SimpleNamespace(owner_id=owner, source='ai', kind='image')]:
        db.get.return_value = asset
        with pytest.raises(NotFound):
            await teacher_image_catalog(db, owner, [{'asset_id': str(uuid.uuid4()), 'description': 'Leaf'}])


async def test_catalog_retains_caption_and_asset():
    owner, aid = uuid.uuid4(), uuid.uuid4()
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(id=aid, owner_id=owner, source='upload', kind='image', storage_key='photo.png')
    catalog = await teacher_image_catalog(db, owner, [{'asset_id': str(aid), 'description': 'Leaf cross section'}])
    assert catalog['teacher_image_1']['description'] == 'Leaf cross section'
    assert catalog['teacher_image_1']['teacher_supplied'] is True


@pytest.mark.parametrize('mode', ['hybrid', 'stock', 'ai'])
async def test_supplied_image_precedes_search_and_generation(environment, monkeypatch, mode):
    owner, ai, storage, db, added = environment
    aid = uuid.uuid4()
    db.get.return_value = SimpleNamespace(id=aid, owner_id=owner, source='upload', storage_key='photo.png', attribution=None)
    search = AsyncMock(side_effect=AssertionError('A supplied picture must be used first'))
    monkeypatch.setattr(assets, 'search_openverse', search)
    item = slide()
    item.visual.source_image_key = 'teacher_image_1'
    images, counts = await assets.resolve_images(db, owner_id=owner, slides=[item], colors={}, image_mode=mode, allow_ai_images=4, source_images={'teacher_image_1': {'asset_id': str(aid), 'teacher_supplied': True}})
    assert item.asset_id == str(aid) and images[str(aid)] == b'cached-photo'
    assert counts['reused'] == 1 and counts['ai'] == 0
    ai.image.assert_not_awaited()
    search.assert_not_awaited()

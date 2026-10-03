import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.routes.content import CourseIn
from app.generation.prompts import presentation_style
from app.generation.specs import SlideSpec
from app.services import assets


def slide(**extra):
    return SlideSpec(number=1, layout='image_text', purpose='Explain', title='Leaves',
                     visual={'kind': 'image', 'image_query': 'green leaf'}, **extra)


@pytest.fixture
def environment(monkeypatch):
    owner = uuid.uuid4()
    ai = SimpleNamespace(image=AsyncMock())
    storage = SimpleNamespace(get=AsyncMock(return_value=b'cached-photo'), put=AsyncMock())
    monkeypatch.setattr(assets, 'get_ai', lambda: ai)
    monkeypatch.setattr(assets, 'get_storage', lambda: storage)
    monkeypatch.setattr(assets, 'get_settings', lambda: SimpleNamespace(openverse_enabled=True))
    monkeypatch.setattr('app.services.settings.get_setting', AsyncMock(return_value={'ai_images': True, 'openverse': True}))
    monkeypatch.setattr(assets, '_normalise_image', lambda data: (data, 1000, 600))
    placeholder = Mock(side_effect=AssertionError('Stock mode must not generate a placeholder'))
    monkeypatch.setattr(assets, 'placeholder_illustration', placeholder)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))
    added = []
    db.add = added.append
    async def flush():
        for asset in added:
            if asset.id is None:
                asset.id = uuid.uuid4()
    db.flush.side_effect = flush
    return owner, ai, storage, db, added


async def test_stock_mode_has_no_paid_or_placeholder_fallback(environment, monkeypatch):
    owner, ai, storage, db, added = environment
    monkeypatch.setattr(assets, 'search_openverse', AsyncMock(return_value=None))
    item = slide()
    images, counts = await assets.resolve_images(db, owner_id=owner, slides=[item], colors={}, image_mode='stock', allow_ai_images=4)
    assert images == {} and counts['ai'] == 0 and counts['placeholder'] == 0
    assert item.visual.kind == 'none' and item.layout == 'concept'
    assert 'No matching licensed stock photo' in item.speaker_notes
    ai.image.assert_not_awaited()
    storage.put.assert_not_awaited()


async def test_stock_mode_stores_photo_and_attribution(environment, monkeypatch):
    owner, ai, storage, db, added = environment
    monkeypatch.setattr(assets, 'search_openverse', AsyncMock(return_value={
        'data': b'photo', 'license': 'CC BY 4.0', 'attribution': 'Leaf by Photographer', 'source_url': 'https://example.com/photo'}))
    item = slide()
    images, counts = await assets.resolve_images(db, owner_id=owner, slides=[item], colors={}, image_mode='stock', allow_ai_images=4)
    assert counts['openverse'] == 1 and counts['ai'] == 0
    assert images[item.asset_id] == b'photo'
    assert added[0].source == 'openverse'
    assert any(s.get('attribution') == 'Leaf by Photographer' for s in item.sources)
    assert any(s.get('url') == 'https://example.com/photo' for s in item.sources)
    ai.image.assert_not_awaited()


async def test_stock_mode_rejects_preassigned_ai_asset(environment, monkeypatch):
    owner, ai, storage, db, added = environment
    db.get.return_value = SimpleNamespace(owner_id=owner, source='ai')
    monkeypatch.setattr(assets, 'search_openverse', AsyncMock(return_value=None))
    item = slide(asset_id=str(uuid.uuid4()))
    await assets.resolve_images(db, owner_id=owner, slides=[item], colors={}, image_mode='stock')
    assert item.asset_id is None
    storage.get.assert_not_awaited()
    params = db.execute.call_args.args[0].compile().params
    assert 'openverse' in params.values()


def test_natural_stock_options_validate_and_reach_prompt():
    request = CourseIn(topic='Plants', grade='6', subject='Science', num_lectures=1, slides_per_lecture=10,
                       writing_style='natural', image_mode='stock')
    text = presentation_style(request.model_dump())
    assert 'NATURAL CLASSROOM STYLE' in text and 'STOCK PHOTOS ONLY' in text
    assert 'Do not invent personal experiences' in text
    assert presentation_style({'writing_style': 'standard', 'image_mode': 'auto'}) == ''


async def test_invalid_stock_file_never_generates_placeholder(environment, monkeypatch):
    owner, ai, storage, db, added = environment
    monkeypatch.setattr(assets, 'search_openverse', AsyncMock(return_value={
        'data': b'invalid-photo', 'license': 'CC BY 4.0', 'attribution': 'Photographer'}))
    def invalid(data):
        raise ValueError('Invalid image')
    monkeypatch.setattr(assets, '_normalise_image', invalid)
    item = slide()
    images, counts = await assets.resolve_images(db, owner_id=owner, slides=[item], colors={}, image_mode='stock')
    assert images == {} and counts['placeholder'] == 0 and item.asset_id is None
    ai.image.assert_not_awaited()


async def test_search_rejects_noncommercial_license():
    client = AsyncMock()
    client.get.return_value = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'results': [
        {'width': 1000, 'url': 'https://example.com/photo', 'license': 'by-nc'}]})
    assert await assets.search_openverse('leaf', client) is None
    assert client.get.await_count == 1


@pytest.mark.parametrize('found', [True, False])
async def test_hybrid_searches_before_generating(environment, monkeypatch, found):
    owner, ai, storage, db, added = environment
    calls = []
    async def search(*args):
        calls.append('search')
        return {'data': b'photo', 'license': 'by', 'attribution': 'Author', 'source_url': 'https://example.org/photo'} if found else None
    async def generate(*args, **kwargs):
        calls.append('generate')
        return SimpleNamespace(data=b'illustration')
    monkeypatch.setattr(assets, 'search_openverse', search)
    ai.image.side_effect = generate
    _, counts = await assets.resolve_images(db, owner_id=owner, slides=[slide()], colors={}, image_mode='hybrid', allow_ai_images=1)
    assert calls == (['search'] if found else ['search', 'generate'])
    assert counts['ai'] == (0 if found else 1)

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_stock_presentations import environment as environment
from test_stock_presentations import slide

from app.core.errors import AppError, NotFound
from app.services import assets, context, memory
from app.services import image_assistant as service
from app.services.teacher_signals import explicit_preferences, image_change_signal


def brief():
    return service.ImageBrief(
        change="Show four leaves instead of six",
        preserve="Keep the same plant and a plain background",
        description="A green plant showing exactly four leaves on a plain white background",
        image_query="green plant four leaves",
        source="ai",
        style="illustration",
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Remember that I prefer diagrams for future lessons", {"preferred_image_style": "diagram"}),
        ("Remember I like photographs", {"preferred_image_style": "photograph"}),
        ("Remember I prefer hybrid images", {"preferred_image_source": "hybrid"}),
        ("Remember I prefer stock-only pictures", {"preferred_image_source": "stock"}),
        ("Use cartoons for this slide", {}),
        ("Do not remember that I prefer diagrams", {}),
        ("Remember I prefer photographs or diagrams", {}),
        ("Remember the student name is Alice", {}),
    ],
)
def test_regex_stores_only_explicit_unambiguous_supported_preferences(text, expected):
    assert explicit_preferences(text) == expected


def test_regex_routes_image_change_without_guessing_target():
    assert image_change_signal("Please fix the image on slide 4") == {"image_change": True, "slide_number": 4}
    assert image_change_signal("Make the lesson better")["image_change"] is False


async def test_memory_fallback_is_relevant_and_bounded(monkeypatch):
    rows = [
        SimpleNamespace(content="Plants: students confused roots and leaves"),
        SimpleNamespace(content="Fractions need another worked example"),
    ]
    monkeypatch.setattr(memory, "recent_memory", AsyncMock(return_value=rows))
    found = await memory.lexical_memory(AsyncMock(), uuid.uuid4(), "plant leaves roots", kinds=["reflection"])
    assert found == [rows[0]]
    assert memory.recent_memory.call_args.kwargs["limit"] == 60


async def test_context_applies_only_confirmed_preferences(monkeypatch):
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))
    monkeypatch.setattr(
        memory,
        "list_preferences",
        AsyncMock(
            return_value=[
                SimpleNamespace(key="tone", value="Friendly", confirmed=True),
                SimpleNamespace(key="words_per_bullet", value=4, confirmed=False),
            ]
        ),
    )
    text, meta = await context.build_context(db, SimpleNamespace(id=uuid.uuid4()))
    assert meta["preferences"] == {"tone": "Friendly"}
    assert "ask before applying" in text


@pytest.mark.parametrize("turns,ready", [(1, False), (2, True)])
async def test_image_chat_clarifies_before_offering_confirmation(monkeypatch, turns, ready):
    owner, cid, lid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conv, user = SimpleNamespace(id=cid), SimpleNamespace(id=owner)
    row = SimpleNamespace(spec={"layout": "image_text", "title": "Plant"}, version=2, number=4)
    monkeypatch.setattr(
        service,
        "target_for",
        AsyncMock(return_value=(SimpleNamespace(id=lid, course_id=uuid.uuid4()), row, {})),
    )
    monkeypatch.setattr(
        service, "build_context", AsyncMock(return_value=("Confirmed style: illustration", {}))
    )
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(
        topic="Plants", class_section_id=None, subject="Science", options={}
    )
    msgs = [
        SimpleNamespace(role="user", content="Keep the plant, change to four leaves, use AI")
        for _ in range(turns)
    ]
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: msgs))
    saved = []
    db.add = saved.append

    async def flush():
        for item in saved:
            item.id = uuid.uuid4()

    db.flush.side_effect = flush
    ai = SimpleNamespace(
        structured=AsyncMock(
            return_value=service.ImageReply(reply="Review your image requirements.", brief=brief())
        ),
        image=AsyncMock(),
    )
    monkeypatch.setattr(service, "get_ai", lambda: ai)
    events = [event async for event in service.reply(db, user, conv)]
    ai.image.assert_not_awaited()
    actions = saved[-1].actions
    assert bool(actions) is ready
    if ready:
        assert actions[0]["message_id"] == str(saved[-1].id)
        assert actions[0]["slide_version"] == 2
    else:
        assert "must stay" in saved[-1].content
    assert events[-1]["event"] == "done"


async def test_confirmation_rejects_stale_brief_before_spending(monkeypatch):
    uid, cid = uuid.uuid4(), uuid.uuid4()
    conv = SimpleNamespace(id=cid, owner_id=uid, channel="image_edit")
    msg = SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=cid,
        role="assistant",
        actions=[{"type": "image_brief", "brief": brief().model_dump(), "slide_version": 1}],
    )
    db = AsyncMock()
    db.get.side_effect = [conv, msg]
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: msg))
    monkeypatch.setattr(service.usage, "lock_user", AsyncMock())
    monkeypatch.setattr(service.usage, "check", AsyncMock())
    monkeypatch.setattr(
        service,
        "target_for",
        AsyncMock(return_value=(SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(version=2), {})),
    )
    with pytest.raises(AppError) as exc:
        await service.confirm(db, SimpleNamespace(id=uid), cid, msg.id)
    assert exc.value.code == "stale_slide"
    service.usage.check.assert_not_awaited()


async def test_confirmation_replay_reuses_job(monkeypatch):
    uid, cid, jid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conv = SimpleNamespace(id=cid, owner_id=uid, channel="image_edit")
    msg = SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=cid,
        role="assistant",
        actions=[{"type": "image_brief", "job_id": str(jid)}],
    )
    db = AsyncMock()
    db.get.side_effect = [conv, msg]
    monkeypatch.setattr(service.usage, "lock_user", AsyncMock())
    monkeypatch.setattr(service.usage, "check", AsyncMock())
    monkeypatch.setattr(
        service,
        "target_for",
        AsyncMock(return_value=(SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(version=2), {})),
    )
    assert await service.confirm(db, SimpleNamespace(id=uid), cid, msg.id) == jid
    service.usage.check.assert_not_awaited()


async def test_confirmation_rejects_foreign_conversation(monkeypatch):
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(owner_id=uuid.uuid4())
    monkeypatch.setattr(service.usage, "lock_user", AsyncMock())
    with pytest.raises(NotFound):
        await service.confirm(db, SimpleNamespace(id=uuid.uuid4()), uuid.uuid4(), uuid.uuid4())


async def test_required_real_replacement_never_inserts_placeholder(environment, monkeypatch):
    owner, ai, storage, db, added = environment
    monkeypatch.setattr(assets, "search_openverse", AsyncMock(return_value=None))
    item = slide()
    result, counts = await assets.resolve_images(
        db,
        owner_id=owner,
        slides=[item],
        colors={},
        image_mode="hybrid",
        require_real_image=True,
        reuse_cached=False,
        allow_ai_images=0,
    )
    assert not item.asset_id and result == {} and counts["placeholder"] == 0
    db.execute.assert_not_awaited()
    ai.image.assert_not_awaited()


async def test_explicit_confirmed_ai_image_survives_stock_rerender(environment):
    owner, ai, storage, db, added = environment
    aid = uuid.uuid4()
    db.get.return_value = SimpleNamespace(
        id=aid, owner_id=owner, source="ai", storage_key="confirmed.png", attribution=None
    )
    item = slide(asset_id=str(aid), sources=[{"type": "image", "source": "ai", "teacher_confirmed": True}])
    result, counts = await assets.resolve_images(
        db, owner_id=owner, slides=[item], colors={}, image_mode="stock"
    )
    assert result[str(aid)] == b"cached-photo"
    ai.image.assert_not_awaited()


@pytest.mark.parametrize("available,identical", [(True, False), (False, False), (True, True)])
async def test_replacement_worker_changes_only_target_and_saves_memory_after_success(
    monkeypatch, available, identical
):
    uid, lid = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uid, status="active")
    lesson = SimpleNamespace(id=lid, owner_id=uid, course_id=uuid.uuid4())
    course = SimpleNamespace(grade="6", subject="Science", topic="Plants")
    original = slide(asset_id=str(uuid.uuid4()))
    original.visual.description = "Original plant"
    other = slide()
    other.number = 2
    other.title = "Unchanged slide"
    deck = SimpleNamespace(slides=[original, other])
    row = SimpleNamespace(number=1, version=3)
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.side_effect = [
        user,
        lesson,
        course,
        SimpleNamespace(sha256="old"),
        SimpleNamespace(sha256="old" if identical else "new"),
    ]
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: row))
    monkeypatch.setattr("app.core.db.get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(service.usage, "lock_user", AsyncMock())
    monkeypatch.setattr(service.usage, "check", AsyncMock())
    consume = AsyncMock()
    monkeypatch.setattr(service.usage, "consume", consume)
    monkeypatch.setattr(service.courses, "load_deck", AsyncMock(return_value=deck))
    render = AsyncMock(return_value={"version": 2})
    monkeypatch.setattr(service.courses, "rerender_lesson", render)
    remember = AsyncMock()
    monkeypatch.setattr(service.memory, "set_preference", remember)

    async def resolve(db, **kwargs):
        assert len(kwargs["slides"]) == 1
        assert kwargs["require_real_image"] is True and kwargs["reuse_cached"] is False
        candidate = kwargs["slides"][0]
        if available:
            candidate.asset_id = str(uuid.uuid4())
            candidate.sources.append({"type": "image", "source": "ai"})
        return {}, {"ai": 1 if available else 0}

    monkeypatch.setattr(service.assets, "resolve_images", resolve)
    ctx = SimpleNamespace(
        owner_id=uid,
        job_id=uuid.uuid4(),
        progress=AsyncMock(),
        payload={
            "lesson_id": str(lid),
            "slide_number": 1,
            "slide_version": 3,
            "brief": brief().model_dump(),
            "credit_cost": 1,
            "remember_style": True,
        },
    )
    result = await service.replace(ctx)
    changed = available and not identical
    assert result["changed"] is changed
    assert result["credits_used"] == (1 if changed else 0)
    assert deck.slides[1] is other
    if changed:
        assert deck.slides[0].title == original.title
        assert deck.slides[0].asset_id != original.asset_id
        assert deck.slides[0].sources[-1]["teacher_confirmed"] is True
        assert remember.await_count == 2
        assert consume.await_count == 2
    else:
        assert deck.slides[0] is original
        render.assert_not_awaited()
        if identical:
            assert consume.await_count == 1
        else:
            consume.assert_not_awaited()
        remember.assert_not_awaited()

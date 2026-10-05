import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
from test_content_quality import budgets, deck

from app.generation import page_review


def preview():
    output = io.BytesIO()
    Image.new('RGB', (1280, 720), 'white').save(output, format='PNG')
    return output.getvalue()


async def test_review_preserves_images_and_teacher_edits_and_ignores_invalid_numbers(monkeypatch):
    lesson = deck()
    lesson.slides[1].asset_id = 'existing-photo'
    lesson.slides[1].visual.kind = 'image'
    lesson.slides[2].manual_objects = {'1': {'x': 0.1}}
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=page_review.PageReview(findings=[
        page_review.PageFinding(number=2, instruction='Add an example', image_mismatch=False),
        page_review.PageFinding(number=3, instruction='Move text', image_mismatch=False),
        page_review.PageFinding(number=999, instruction='Invalid', image_mismatch=False)])))
    replacement = lesson.slides[1].model_copy(deep=True)
    replacement.visual.kind = 'none'
    repair = AsyncMock(return_value=replacement)
    monkeypatch.setattr(page_review.pipeline, 'repair_slide', repair)
    result = await page_review.review_pages(ai, lesson, [preview()] * len(lesson.slides),
                                          budgets=budgets(), context_text='', grade='2')
    assert [r['slide'] for r in result] == [2]
    assert lesson.slides[1].visual.kind == 'image'
    assert lesson.slides[1].asset_id == 'existing-photo'
    assert len(ai.structured.call_args.kwargs['images']) == len(lesson.slides)
    assert repair.await_count == 1


async def test_mismatched_photo_replaced_with_editable_content(monkeypatch):
    lesson = deck()
    old = lesson.slides[1]
    old.asset_id = 'wrong-photo'
    old.sources = [{'type': 'image', 'url': 'photo'}, {'type': 'textbook', 'page': 2}]
    ai = SimpleNamespace(mode='live', structured=AsyncMock(return_value=page_review.PageReview(findings=[
        page_review.PageFinding(number=2, instruction='Picture is unrelated', image_mismatch=True)])))
    replacement = old.model_copy(deep=True)
    replacement.layout = 'image_text'
    monkeypatch.setattr(page_review.pipeline, 'repair_slide', AsyncMock(return_value=replacement))
    result = await page_review.review_pages(ai, lesson, [preview()] * len(lesson.slides),
                                          budgets=budgets(), context_text='', grade='2')
    assert result[0]['image_replaced_with_editable_content']
    assert lesson.slides[1].asset_id is None
    assert lesson.slides[1].layout == 'concept'
    assert lesson.slides[1].sources == [{'type': 'textbook', 'page': 2}]


async def test_incomplete_previews_skip_ai_review():
    ai = SimpleNamespace(mode='live', structured=AsyncMock())
    assert await page_review.review_pages(ai, deck(), [preview()], budgets=budgets(),
                                         context_text='', grade='2') == []
    ai.structured.assert_not_awaited()

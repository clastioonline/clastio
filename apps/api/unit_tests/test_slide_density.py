import io

from pptx import Presentation

from app.engine.render.renderer import DeckRenderer
from app.engine.template.builder import BUILTIN_STYLES, build_builtin
from app.generation import pipeline
from app.generation.budgets import compute_budgets
from app.generation.specs import Bullet, LessonDeck, SlideSpec


def test_sparse_explanation_is_flagged_without_blocking_purposeful_whitespace():
    base, template = build_builtin(next(iter(BUILTIN_STYLES)))
    slide = SlideSpec(number=1, layout='concept', title='Fractions', purpose='Explain',
                      bullets=[Bullet(text='A fraction is part of a whole.')])
    deck = LessonDeck.model_construct(slides=[slide])
    assert any(issue.code == 'sparse_explanation' for issue in pipeline.content_qc(deck, compute_budgets(template)))
    for layout in ['cover', 'section', 'quiz', 'activity']:
        changed = slide.model_copy(update={'layout': layout})
        deck = LessonDeck.model_construct(slides=[changed])
        assert not any(issue.code == 'sparse_explanation' for issue in pipeline.content_qc(deck, compute_budgets(template)))


def test_explanation_cards_use_body_area_and_remain_editable():
    base, template = build_builtin(next(iter(BUILTIN_STYLES)))
    renderer = DeckRenderer(base, template)
    points = ['A fraction describes equal parts of a whole.', 'The denominator counts all equal parts.',
              'The numerator counts the parts selected.']
    slide = SlideSpec(number=1, layout='concept', title='Fractions', purpose='Explain',
                      bullets=[Bullet(text=text) for text in points])
    data = renderer.render([slide])
    shapes = Presentation(io.BytesIO(data)).slides[0].shapes
    cards = [shape for shape in shapes if shape.has_text_frame and shape.text in points]
    assert len(cards) == 3
    body = renderer.zone('body')
    assert min(shape.top for shape in cards) == body.y
    assert abs(max(shape.top + shape.height for shape in cards) - body.bottom) < 5
    assert not any(report.overflow for report in renderer.reports)

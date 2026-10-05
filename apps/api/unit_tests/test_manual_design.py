import io

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from app.engine.render.manual import apply_manual, editable_objects
from app.generation.specs import ManualObjectEdit


def test_manual_text_and_geometry_survive_powerpoint_roundtrip():
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    run = box.text_frame.paragraphs[0].add_run()
    run.text, run.font.name, run.font.size = "Original", "Carlito", Pt(24)
    key = str(box.shape_id)
    apply_manual(slide, {key: ManualObjectEdit(text="Worked example: 2 + 3 = 5", color="#1255AA",
        font_size=32, x=.2, y=.3, width=.5, height=.2, bold=True)}, deck.slide_width, deck.slide_height)
    buffer = io.BytesIO()
    deck.save(buffer)
    objects = editable_objects(buffer.getvalue())[0]
    assert objects[0]["text"] == "Worked example: 2 + 3 = 5"
    assert objects[0]["color"] == "#1255AA"
    assert objects[0]["font_size"] == 32
    assert objects[0]["font_family"] == "Carlito"
    assert objects[0]["x"] == pytest.approx(.2)
    assert objects[0]["width"] == pytest.approx(.5)
    restored = Presentation(io.BytesIO(buffer.getvalue()))
    assert restored.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.bold is True


def test_unspecified_formatting_is_preserved_and_missing_objects_ignored():
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    run = shape.text_frame.paragraphs[0].add_run()
    run.text, run.font.name, run.font.size = "Keep this", "Carlito", Pt(28)
    apply_manual(slide, {str(shape.shape_id): ManualObjectEdit(x=.1),
                         "9999": ManualObjectEdit(text="Missing")}, deck.slide_width, deck.slide_height)
    assert run.text == "Keep this"
    assert run.font.size.pt == 28
    assert run.font.name == "Carlito"


@pytest.mark.parametrize("edit", [{"color": "red"}, {"font_size": 0}, {"width": 0}, {"x": -1}])
def test_invalid_manual_formatting_is_rejected(edit):
    with pytest.raises(ValueError):
        ManualObjectEdit(**edit)

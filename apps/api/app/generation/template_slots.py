"""Resolve the same preserved-template page mapping used by the PPTX injector."""

from app.engine.render.vendor.presenton import repeated_child_source_index
from app.generation.quality import ContentQualityError


def prepare_template_images(slides, spec, *, subject, topic=''):
    if not spec.get('preserve_slots'):
        return
    pages = spec.get('template_slots') or []
    bodies = [page for page in pages if any(slot.get('role') == 'body' for slot in page.get('slots', []))]
    if not pages or not bodies:
        raise ContentQualityError('The preserved template needs a title and body content page.')
    for index, slide in enumerate(slides):
        page = pages[0] if index == 0 else bodies[repeated_child_source_index(index-1,
            template_count=len(bodies), content_count=len(slides)-1, center_when_reduced=False)]
        slide.template_image_slot = any(slot.get('role') == 'image' for slot in page['slots'])
        if slide.template_image_slot:
            # A real PICTURE slot requires bitmap data, including on a cover.
            # Native counting diagrams cannot fill that slot by themselves.
            slide.visual.kind = 'image'
            slide.visual.counting_groups = []
            if not slide.visual.image_query:
                slide.visual.image_query = ' '.join(part for part in (topic, slide.title, subject) if part)

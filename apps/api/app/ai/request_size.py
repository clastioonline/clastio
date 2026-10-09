"""Fit PPT reference previews into approved request limits without changing originals."""
from __future__ import annotations

import io
from dataclasses import replace

from PIL import Image, ImageOps

from app.ai.base import AIRequest, ImageInput
from app.ai.budget import BudgetError, BudgetPolicy

PPT_TASKS = {'course_plan', 'lesson_outline', 'lesson_deck', 'slide_rewrite', 'lesson_page_review', 'lesson_teaching', 'lesson_deck_batch', 'chapter_knowledge'}


def fit_ppt_request(req: AIRequest, policy: BudgetPolicy, text_bytes: int) -> AIRequest:
    if text_bytes > policy.max_input_bytes:
        raise BudgetError(f"PPT teaching text needs {text_bytes:,} bytes; the configured input limit is "
                          f"{policy.max_input_bytes:,}. Reduce the teaching brief or source sections.")
    images = [image for message in req.messages for image in message.images]
    available = policy.max_input_bytes - text_bytes
    converted = []
    if sum(len(image.data) for image in images) > available:
        per_image = available // max(1, len(images))
        for image in images:
            with Image.open(io.BytesIO(image.data)) as source:
                page = ImageOps.exif_transpose(source).convert('RGB')
                page.thumbnail((1280, 960))
                while True:
                    output = io.BytesIO()
                    page.save(output, format='JPEG', quality=70, optimize=True)
                    if output.tell() <= per_image:
                        converted.append(ImageInput(output.getvalue(), 'image/jpeg'))
                        break
                    if min(page.size) <= 240:
                        raise BudgetError("PPT reference images cannot fit legibly within the configured "
                                          "input limit. Use fewer reference images or a shorter teaching brief.")
                    page = page.resize((max(1, int(page.width * .8)), max(1, int(page.height * .8))),
                                       Image.Resampling.LANCZOS)
    else:
        converted = images
    iterator = iter(converted)
    return replace(req, max_tokens=min(req.max_tokens, policy.max_output_tokens),
                   messages=[replace(message, images=[next(iterator) for _ in message.images])
                             for message in req.messages])

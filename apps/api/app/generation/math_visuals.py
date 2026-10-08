"""Grounded editable algebra visuals; quantities come from the slide text."""
import re

from app.generation.specs import SlideSpec


def algebra_visual(slide: SlideSpec) -> dict | None:
    text = ' '.join([slide.title, *[bullet.text for bullet in slide.bullets]])
    match = re.search(r'(?<![\w.\-−/])(\d{1,4})\s*([a-zA-Z])\s*\+\s*(\d{1,4})(?![\w^]|\.\d)', text)
    if not match:
        return None
    coefficient, variable, constant = match.groups()
    value = re.search(rf'\b{re.escape(variable)}\s*=\s*(\d{{1,4}})(?!\w|\.\d)', text)
    return {'expression': f'{coefficient}{variable} + {constant}', 'coefficient': coefficient,
            'variable': variable, 'constant': constant, 'value': value.group(1) if value else None,
            'answer': int(coefficient) * int(value.group(1)) + int(constant) if value else None}

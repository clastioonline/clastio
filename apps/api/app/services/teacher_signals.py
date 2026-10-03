"""Bounded regex signals route requests and extract only explicit, supported preferences.

These patterns detect intent; they do not infer scientific facts or replace clarification.
"""
import re

IMAGE_CHANGE = re.compile(r"\b(?:change|replace|edit|fix|adjust|regenerate|improve)\b.{0,100}\b(?:image|picture|photo|illustration|diagram)\b|\b(?:image|picture|photo|illustration|diagram)\b.{0,100}\b(?:change|replace|edit|fix|adjust|regenerate|improve)\b", re.I)
SLIDE_NUMBER = re.compile(r"\bslide\s*(?:number\s*|#\s*)?(\d{1,2})\b", re.I)
REMEMBER = re.compile(r"\b(?:remember(?:\s+that)?|for\s+(?:all|future)\s+(?:my\s+)?(?:lessons|ppts|presentations))\b", re.I)
PREFER = re.compile(r"\b(?:i\s+(?:prefer|like|want)|use|choose)\b", re.I)
NEGATION = re.compile(r"\b(?:not|never|don't|do\s+not|avoid)\b", re.I)
STYLE_PATTERNS = {
    "photograph": re.compile(r"\b(?:photos?|photographs?|photography)\b", re.I),
    "diagram": re.compile(r"\bdiagrams?\b", re.I),
    "illustration": re.compile(r"\billustrations?\b", re.I),
    "cartoon": re.compile(r"\bcartoons?\b", re.I),
}


def explicit_preferences(text: str) -> dict[str, str]:
    text = text[:4000]
    if not REMEMBER.search(text) or not PREFER.search(text) or NEGATION.search(text):
        return {}
    matches = [style for style, pattern in STYLE_PATTERNS.items() if pattern.search(text)]
    preferences = {"preferred_image_style": matches[0]} if len(matches) == 1 else {}
    sources = {
        "hybrid": r"\bhybrid\b",
        "stock": r"\b(?:licensed\s+stock|stock[- ]only)\b",
        "ai": r"\bai[- ](?:generated\s+)?(?:images?|pictures?|illustrations?)\b",
    }
    selected = [source for source, pattern in sources.items() if re.search(pattern, text, re.I)]
    if len(selected) == 1:
        preferences["preferred_image_source"] = selected[0]
    return preferences


def image_change_signal(text: str) -> dict:
    text = text[:4000]
    slide = SLIDE_NUMBER.search(text)
    return {"image_change": bool(IMAGE_CHANGE.search(text)), "slide_number": int(slide[1]) if slide else None}


def memory_terms(text: str) -> set[str]:
    return set(re.findall(r"\b[^\W\d_]{3,}\b", text[:4000].lower(), re.UNICODE))

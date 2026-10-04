"""Explainable design suggestions from stated teaching context, never school-name guesses."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SUBJECT_GROUPS = {
    "science": {"science", "biology", "chemistry", "physics", "general science"},
    "maths": {"mathematics", "maths", "math", "mathematics and statistics"},
    "language": {"english", "language arts", "english language", "french", "hindi", "urdu"},
    "arabic": {"arabic", "arabic language"},
    "islamic": {"islamic education", "islamic studies"},
    "humanities": {"social studies & moral education", "social studies", "moral education", "history", "geography"},
    "computing": {"computing", "computer science", "artificial intelligence", "ai", "ict"},
}
CURRICULUM_LABELS = {"british": "British", "cbse": "CBSE", "icse": "ICSE", "american": "American",
                     "ib": "IB", "moe": "UAE MOE", "uae_ai": "UAE AI"}


def grade_number(value: str | None) -> int | None:
    value = (value or "").strip().lower()
    if re.fullmatch(r"(?:kg|fs|eyfs|nursery|reception)(?:[ -]?[12])?", value):
        return 0
    match = re.fullmatch(r"(?:grade|year)?\s*(\d{1,2})", value)
    number = int(match[1]) if match else None
    return number if number is not None and 0 <= number <= 13 else None


def suggest_templates(templates: Iterable[Any], *, owner_id: Any, org_id: Any = None,
                      default_id: Any = None, subjects: list[str] | None = None, grades: list[str] | None = None,
                      curriculum: str | None = None, language: str | None = None, country: str | None = None,
                      limit: int = 3) -> list[dict[str, Any]]:
    subjects = [subject.strip() for subject in subjects or [] if subject and subject.strip()]
    groups = {group for group, names in SUBJECT_GROUPS.items()
              if any(subject.casefold() in names for subject in subjects)}
    grade_numbers = [number for grade in grades or [] if (number := grade_number(grade)) is not None]
    curriculum = (curriculum or "").lower()
    ranked = []
    for template in templates:
        if template.status != "ready":
            continue
        owned = template.owner_id == owner_id
        shared = bool(org_id and template.org_id == org_id and template.is_shared)
        if template.owner_id is not None and not (owned or shared):
            continue  # Defence in depth for pure callers; never suggest another teacher's upload.
        score, reasons = 0, []
        if template.id == default_id:
            score += 100
            reasons.append("Your saved default design")
        if owned:
            score += 60
            reasons.append("Your uploaded design; reuse it for your school's own style")
        elif shared:
            score += 55
            reasons.append("A design shared by your organisation")
        catalog = (template.spec or {}).get("catalog", {}) if template.owner_id is None else {}
        matched = groups.intersection(catalog.get("subjects", []))
        if matched:
            score += 45 + 10 / max(1, len(catalog.get("subjects", [])))
            relevant = [subject for subject in subjects
                        if any(subject.casefold() in SUBJECT_GROUPS[group] for group in matched)]
            reasons.append(f"Designed for {', '.join(relevant[:2])}")
        if curriculum and curriculum in catalog.get("curricula", []):
            score += 20
            reasons.append(f"Fits your selected {CURRICULUM_LABELS.get(curriculum, curriculum.upper())} curriculum")
        minimum, maximum = catalog.get("grade_min", 0), catalog.get("grade_max", 12)
        if grade_numbers and any(minimum <= number <= maximum for number in grade_numbers):
            score += 30 if minimum == 0 and maximum <= 2 else 8
            reasons.append("Large, playful type for early years" if maximum <= 2
                           else f"Suitable for grade {', '.join((grades or [])[:2])}")
        elif grade_numbers and catalog:
            score -= 50  # Avoid nursery designs for secondary classes and vice versa.
        if language and language in catalog.get("languages", []):
            score += 25
            reasons.append("Arabic typography for your selected teaching language")
        if country == "AE" and catalog.get("region") == "AE":
            score += 3
        if score > 0 and reasons:
            ranked.append({"template_id": str(template.id), "score": score, "reasons": reasons[:3],
                           "reason": " · ".join(reasons[:2]), "name": template.name})
    return sorted(ranked, key=lambda item: (-item["score"], item["name"].casefold()))[:limit]

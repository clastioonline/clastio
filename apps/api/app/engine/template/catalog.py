"""Curated editable classroom designs, independent of any school brand or endorsement."""

from __future__ import annotations

from typing import Any

BUILTIN_CATALOG_REVISION = 1

# Fonts are installed in our export image. Each design has native, editable PowerPoint chrome.
UAE_STYLES: dict[str, dict[str, Any]] = {
    "uae-heritage": {
        "name": "UAE Heritage", "primary": "#155E46", "secondary": "#BE6C3B", "background": "#FFF9EF",
        "text": "#29382F", "heading": "Caladea", "body": "Lato", "layout": "heritage", "band": False,
        "description": "Warm sand, heritage geometry and generous space for UAE history and moral education.",
        "subjects": ["humanities", "islamic"], "curricula": ["moe"], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "Heritage", "Humanities"],
    },
    "uae-sustainability": {
        "name": "Green Emirates", "primary": "#166534", "secondary": "#147D92", "background": "#F6FBF5",
        "text": "#193A30", "heading": "Montserrat", "body": "Open Sans", "layout": "botanical", "band": False,
        "description": "Leaf-inspired circles and emerald accents for ecosystems, climate and sustainability.",
        "subjects": ["science", "humanities"], "curricula": [], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "Sustainability", "Science"],
    },
    "uae-maths-grid": {
        "name": "Maths Studio", "primary": "#173E75", "secondary": "#B45309", "background": "#F8FAFF",
        "text": "#202C42", "heading": "Roboto", "body": "Carlito", "layout": "grid", "band": False,
        "description": "Graph-paper corner details, square cards and a wide working area for mathematical examples.",
        "subjects": ["maths"], "curricula": [], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "Mathematics", "Worked examples"], "corner_radius": "square",
    },
    "uae-science-lab": {
        "name": "Discovery Lab", "primary": "#075985", "secondary": "#A45D04", "background": "#F4FBFC",
        "text": "#203642", "heading": "Montserrat", "body": "Open Sans", "layout": "lab", "band": True,
        "description": "A deep teal title band and molecule motifs for evidence, experiments and scientific models.",
        "subjects": ["science"], "curricula": [], "grade_min": 4, "grade_max": 12,
        "tags": ["UAE", "Science", "Experiments"],
    },
    "uae-language-stories": {
        "name": "Language & Stories", "primary": "#6D336F", "secondary": "#B45E25", "background": "#FFF9F6",
        "text": "#392D40", "heading": "Caladea", "body": "Lato", "layout": "book", "band": False,
        "description": "Book-spine borders and an editorial typeface for reading, vocabulary and classroom discussion.",
        "subjects": ["language"], "curricula": [], "grade_min": 2, "grade_max": 12,
        "tags": ["UAE", "Languages", "Reading"],
    },
    "uae-arabic-classroom": {
        "name": "Arabic Classroom", "primary": "#115E59", "secondary": "#9C6818", "background": "#FFFDF4",
        "text": "#253D39", "heading": "Lato", "body": "Open Sans", "layout": "arabesque", "band": False,
        "description": "Restrained geometric borders and Noto Sans Arabic for Arabic or bilingual classroom content.",
        "subjects": ["arabic", "islamic"], "curricula": ["moe"], "languages": ["ar"],
        "grade_min": 1, "grade_max": 12, "tags": ["UAE", "Arabic", "Bilingual"],
    },
    "uae-early-years": {
        "name": "Little Explorers", "primary": "#A3442B", "secondary": "#137D87", "background": "#FFFBF3",
        "text": "#3B332B", "heading": "Comic Neue", "body": "Lato", "layout": "playful", "band": False,
        "description": "Playful shapes, bigger type and fewer words for KG and early primary lessons.",
        "subjects": [], "curricula": [], "grade_min": 0, "grade_max": 2,
        "tags": ["UAE", "KG", "Early years"], "title_pt": 38, "body_pt": 26,
    },
    "uae-british-seminar": {
        "name": "British Classroom", "primary": "#243A66", "secondary": "#945315", "background": "#FCFAF5",
        "text": "#252F3F", "heading": "Caladea", "body": "Carlito", "layout": "seminar", "band": True,
        "description": "Structured navy headers and quiet gold details for retrieval, explanation and exam practice.",
        "subjects": [], "curricula": ["british"], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "British", "Secondary"], "corner_radius": "square",
    },
    "uae-cbse-concepts": {
        "name": "CBSE Concept Builder", "primary": "#9A3F18", "secondary": "#205F75", "background": "#FFFBF5",
        "text": "#343434", "heading": "Roboto", "body": "Lato", "layout": "steps", "band": False,
        "description": "Numbered-margin blocks and clear typography for definitions, worked examples and guided practice.",
        "subjects": ["maths", "science"], "curricula": ["cbse", "icse"], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "CBSE / ICSE", "Guided practice"], "corner_radius": "square",
    },
    "uae-ib-inquiry": {
        "name": "IB Inquiry Atelier", "primary": "#5D3C85", "secondary": "#087F80", "background": "#FAF8FE",
        "text": "#352E42", "heading": "Montserrat", "body": "Open Sans", "layout": "inquiry", "band": False,
        "description": "Open question frames and paired accents for inquiry, perspectives and reflective discussion.",
        "subjects": [], "curricula": ["ib"], "grade_min": 1, "grade_max": 12,
        "tags": ["UAE", "IB", "Inquiry"],
    },
    "uae-moe-learning": {
        "name": "Emirates Learning", "primary": "#116145", "secondary": "#A33B38", "background": "#FFFFFF",
        "text": "#273B34", "heading": "Lato", "body": "Open Sans", "layout": "emirates", "band": True,
        "description": "Green headers, red edge accents and a clean bilingual canvas for UAE curriculum lessons.",
        "subjects": [], "curricula": ["moe"], "grade_min": 1, "grade_max": 12,
        "tags": ["UAE", "MOE", "Bilingual"],
    },
    "uae-future-makers": {
        "name": "Future Makers", "primary": "#244B7D", "secondary": "#0C7D76", "background": "#F5F9FE",
        "text": "#26384D", "heading": "Roboto", "body": "Open Sans", "layout": "circuit", "band": False,
        "description": "Circuit-like edge details and crisp panels for computing, AI literacy and design projects.",
        "subjects": ["computing"], "curricula": ["uae_ai", "american"], "grade_min": 3, "grade_max": 12,
        "tags": ["UAE", "Computing", "AI literacy"], "corner_radius": "square",
    },
}


def catalog_metadata(key: str, style: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "revision": BUILTIN_CATALOG_REVISION,
            "description": style.get("description", "A clear, editable classroom presentation design."),
            "tags": style.get("tags", ["Classroom"]), "subjects": style.get("subjects", []),
            "curricula": style.get("curricula", []), "languages": style.get("languages", []),
            "grade_min": style.get("grade_min", 0), "grade_max": style.get("grade_max", 12),
            "region": "AE" if key.startswith("uae-") else None}

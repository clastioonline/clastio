"""Shared helpers for style analysis (colours, typography stats, content style, layout labels)."""

from __future__ import annotations

import colorsys
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- colour utils


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(c))) for c in rgb])


def luminance(h: str) -> float:
    def ch(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def saturation(h: str) -> float:
    r, g, b = (c / 255 for c in hex_to_rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[2]


def is_neutral(h: str) -> bool:
    r, g, b = hex_to_rgb(h)
    return max(r, g, b) - min(r, g, b) < 24


def mix(a: str, b: str, t: float) -> str:
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(tuple(ra[i] * (1 - t) + rb[i] * t for i in range(3)))


def readable_text_on(bg: str, dark: str = "#111827", light: str = "#FFFFFF") -> str:
    return dark if contrast_ratio(bg, dark) >= contrast_ratio(bg, light) else light


def color_distance(a: str, b: str) -> float:
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return sum((ra[i] - rb[i]) ** 2 for i in range(3)) ** 0.5


class ColorTally:
    def __init__(self) -> None:
        self.c: Counter[str] = Counter()

    def add(self, hexval: str | None, weight: float) -> None:
        if hexval and weight > 0:
            self.c[hexval.upper()] += weight

    def ranked(self, merge_distance: float = 18) -> list[tuple[str, float]]:
        merged: list[list[Any]] = []
        for col, w in self.c.most_common():
            for m in merged:
                if color_distance(m[0], col) < merge_distance:
                    m[1] += w
                    break
            else:
                merged.append([col, w])
        total = sum(m[1] for m in merged) or 1
        return [(m[0], round(m[1] / total, 4)) for m in sorted(merged, key=lambda m: -m[1])]


# --------------------------------------------------------------------------- font names


def clean_font_name(name: str | None) -> str | None:
    if not name:
        return None
    name = re.sub(r"^[A-Z]{6}\+", "", name)  # PDF subset prefix
    name = re.sub(r"[-,](Bold|Italic|Regular|Semibold|SemiBold|Light|Medium|Black|BoldItalic|Oblique|MT|PS)+$", "",
                  name)
    name = re.sub(r"(MT|PSMT)$", "", name)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name) if " " not in name else name
    return name.strip() or None


FALLBACK_FONTS = {
    "serif": "Georgia", "sans": "Arial", "rounded": "Verdana", "arabic": "Noto Sans Arabic",
}


def fallback_for(family: str | None) -> str:
    if not family:
        return "Arial"
    f = family.lower()
    if any(k in f for k in ("georgia", "times", "serif", "garamond", "cambria", "roboto slab", "merriweather")):
        return "Georgia"
    if any(k in f for k in ("comic", "rounded", "verdana", "nunito", "quicksand")):
        return "Verdana"
    return "Arial"


# --------------------------------------------------------------------------- content style

_SYL = re.compile(r"[aeiouy]+")


def syllables(word: str) -> int:
    w = word.lower().strip(".,;:!?()\"'")
    if not w:
        return 0
    n = len(_SYL.findall(w))
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def flesch_kincaid_grade(text: str) -> float | None:
    sentences = max(1, len(re.findall(r"[.!?\n]+", text)))
    words = re.findall(r"[A-Za-z']+", text)
    if len(words) < 20:
        return None
    syl = sum(syllables(w) for w in words)
    return round(0.39 * (len(words) / sentences) + 11.8 * (syl / len(words)) - 15.59, 1)


@dataclass
class ContentStats:
    bullets_per_slide: list[int] = field(default_factory=list)
    words_per_bullet: list[int] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    body_text: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        text = "\n".join(self.body_text)
        titles_q = sum(1 for t in self.titles if t.strip().endswith("?"))
        bps = [b for b in self.bullets_per_slide if b > 0]
        wpb = self.words_per_bullet
        return {
            "bullets_per_slide": [min(bps) if bps else 3, max(bps) if bps else 5],
            "avg_bullets_per_slide": round(statistics.mean(bps), 1) if bps else 4.0,
            "avg_words_per_bullet": round(statistics.mean(wpb), 1) if wpb else 9.0,
            "max_words_per_bullet": max(wpb) if wpb else 14,
            "question_titles_ratio": round(titles_q / len(self.titles), 2) if self.titles else 0.0,
            "reading_grade": flesch_kincaid_grade(text),
            "uses_full_sentences": (sum(1 for b in self.body_text if b.strip().endswith(".")) /
                                    max(1, len(self.body_text))) > 0.5,
            "sample_titles": self.titles[:8],
        }


# --------------------------------------------------------------------------- layout labels


def classify_slide(*, index: int, title: str, texts: list[str], n_text_blocks: int, n_pictures: int,
                   n_tables: int, n_charts: int, has_two_columns: bool, is_first: bool) -> str:
    t = title.lower()
    body = " ".join(texts).lower()
    if is_first:
        return "cover"
    if n_tables:
        return "table"
    if n_charts:
        return "chart"
    if any(k in t for k in ("objective", "learning intention", "we will", "goals", "aims")):
        return "objectives"
    if any(k in t for k in ("quiz", "check your", "test yourself", "question")) or re.search(r"\b[a-d]\)", body):
        return "quiz"
    if any(k in t for k in ("summary", "recap", "key points", "review", "plenary")):
        return "summary"
    if any(k in t for k in ("activity", "task", "group work", "try this", "practice", "let's think", "discuss")):
        return "activity"
    if any(k in t for k in ("compare", " vs", "versus", "difference")) or has_two_columns:
        return "comparison" if ("compare" in t or " vs" in t or "differ" in t) else "two_column"
    if any(k in t for k in ("homework",)):
        return "homework"
    if n_text_blocks <= 1 and not body.strip():
        return "section"
    if n_pictures:
        return "image_text"
    return "concept"

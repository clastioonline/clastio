"""Deterministic text measurement with real font metrics.

We size every text box *before* writing the PPTX so text never overflows. Fonts are resolved with
fontconfig (fc-match), so a missing teacher font measures with its closest installed substitute; a
safety margin covers renderer differences between PowerPoint, Keynote and LibreOffice.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont

SCALE = 10  # measure at 10x point size for sub-point precision
WIDTH_SAFETY = 0.93
_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")


@lru_cache(maxsize=256)
def font_path(family: str, bold: bool = False) -> str | None:
    pattern = f"{family}:bold" if bold else f"{family}:regular"
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=512)
def _font(family: str, size_pt: float, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = font_path(family, bold)
    size = max(1, int(round(size_pt * SCALE)))
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    for fallback in ("DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(fallback, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_width_pt(text: str, family: str, size_pt: float, bold: bool = False) -> float:
    f = _font(family, size_pt, bold)
    try:
        return f.getlength(text) / SCALE
    except AttributeError:  # pragma: no cover - bitmap fallback font
        return len(text) * size_pt * 0.55


def line_height_pt(family: str, size_pt: float, spacing: float = 1.0, bold: bool = False) -> float:
    f = _font(family, size_pt, bold)
    try:
        ascent, descent = f.getmetrics()
        natural = (ascent + descent) / SCALE
    except AttributeError:  # pragma: no cover
        natural = size_pt * 1.2
    return max(natural, size_pt * 1.15) * spacing


def wrap(text: str, family: str, size_pt: float, width_pt: float, bold: bool = False) -> list[str]:
    width_pt = max(1.0, width_pt * WIDTH_SAFETY)
    lines: list[str] = []
    for hard in text.split("\n"):
        words = hard.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for w in words:
            cand = f"{cur} {w}".strip()
            if text_width_pt(cand, family, size_pt, bold) <= width_pt:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            # break very long words
            while text_width_pt(w, family, size_pt, bold) > width_pt and len(w) > 1:
                cut = len(w)
                while cut > 1 and text_width_pt(w[:cut], family, size_pt, bold) > width_pt:
                    cut -= 1
                lines.append(w[:cut])
                w = w[cut:]
            cur = w
        lines.append(cur)
    return lines


@dataclass
class Para:
    text: str
    bold: bool = False
    size_scale: float = 1.0  # relative to the fitted base size (e.g. headings 1.1)
    indent_pt: float = 0.0  # left indent (bullets / levels)
    space_after_em: float = 0.0  # paragraph spacing as a multiple of the font size
    family: str | None = None


@dataclass
class FitResult:
    size_pt: float
    fits: bool
    height_pt: float
    lines: int


def measure(paras: list[Para], family: str, size_pt: float, width_pt: float, spacing: float = 1.0) -> tuple[float, int]:
    total, n_lines = 0.0, 0
    for p in paras:
        fam = p.family or family
        size = size_pt * p.size_scale
        lines = wrap(p.text, fam, size, width_pt - p.indent_pt, p.bold)
        n_lines += len(lines)
        total += len(lines) * line_height_pt(fam, size, spacing, p.bold) + p.space_after_em * size
    return total, n_lines


def fit(paras: list[Para], family: str, width_pt: float, height_pt: float, max_pt: float, min_pt: float,
        spacing: float = 1.0, step: float = 1.0) -> FitResult:
    """Largest size in [min_pt, max_pt] where all paragraphs fit the box."""
    size = max_pt
    while size >= min_pt - 1e-6:
        h, n = measure(paras, family, size, width_pt, spacing)
        if h <= height_pt:
            return FitResult(round(size, 1), True, h, n)
        size -= step
    h, n = measure(paras, family, min_pt, width_pt, spacing)
    return FitResult(round(min_pt, 1), h <= height_pt, h, n)


def is_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))

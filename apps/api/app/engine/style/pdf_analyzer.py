"""Approximate style extraction from PDF slides (no OOXML available).

PyMuPDF gives us text spans (font, size, colour, bbox), vector drawings (fills) and images.
Recurring drawings/images across pages become decorations for the reconstructed template.
Scanned PDFs (no text layer) fall back to OCR when the optional OCR extra is installed.
"""

from __future__ import annotations

import hashlib
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf as fitz

from app.engine.style.common import (
    ColorTally,
    ContentStats,
    classify_slide,
    clean_font_name,
    fallback_for,
    is_neutral,
    luminance,
    rgb_to_hex,
)


def _overlap(a, b) -> float:
    """Intersection over the smaller rectangle's area."""
    inter = fitz.Rect(a) & fitz.Rect(b)
    if inter.is_empty:
        return 0.0
    small = min(fitz.Rect(a).get_area(), fitz.Rect(b).get_area()) or 1
    return inter.get_area() / small


def _int_color(c: int) -> str:
    return f"#{(c >> 16) & 255:02X}{(c >> 8) & 255:02X}{c & 255:02X}"


def _tuple_color(c) -> str | None:
    if not c:
        return None
    return rgb_to_hex(tuple(int(v * 255) for v in c[:3]))


class PdfAnalyzer:
    def __init__(self, path: Path, max_pages: int = 60):
        self.path = Path(path)
        self.doc = fitz.open(str(path))
        self.pages = [self.doc[i] for i in range(min(len(self.doc), max_pages))]
        first = self.pages[0].rect
        self.W, self.H = first.width, first.height

    def _norm(self, r) -> tuple[float, float, float, float]:
        return (r.x0 / self.W, r.y0 / self.H, (r.x1 - r.x0) / self.W, (r.y1 - r.y0) / self.H)

    def has_text_layer(self) -> bool:
        return sum(len(p.get_text("text").strip()) for p in self.pages[:5]) > 40

    def page_images(self, dpi: int = 60) -> list[bytes]:
        return [p.get_pixmap(dpi=dpi).tobytes("png") for p in self.pages]

    def _page_data(self, page) -> dict[str, Any]:
        blocks = []
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            spans = [s for line in b.get("lines", []) for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            lines = [" ".join(s["text"].strip() for s in line.get("spans", []) if s.get("text", "").strip())
                     for line in b.get("lines", [])]
            blocks.append({
                "bbox": fitz.Rect(b["bbox"]),
                "text": "\n".join(x for x in lines if x),
                "lines": [x for x in lines if x],
                "max_size": max(s["size"] for s in spans),
                "spans": spans,
            })
        drawings = []
        for dr in page.get_drawings():
            fill = _tuple_color(dr.get("fill"))
            if not fill:
                continue
            r = dr["rect"]
            if r.width * r.height < 4:
                continue
            drawings.append({"bbox": r, "fill": fill, "kind": "rect" if len(dr.get("items", [])) <= 5 else "shape"})
        images = []
        for info in page.get_image_info(hashes=True, xrefs=True):
            images.append({"bbox": fitz.Rect(info["bbox"]), "digest": (info.get("digest") or b"").hex()
                           if isinstance(info.get("digest"), bytes) else str(info.get("digest")),
                           "xref": info.get("xref", 0)})
        return {"blocks": blocks, "drawings": drawings, "images": images}

    @staticmethod
    def _sig(kind: str, bbox, extra: str | None) -> tuple:
        return (kind, tuple(round(v * 50) / 50 for v in bbox), extra)

    def analyze(self) -> dict[str, Any]:
        pages = [self._page_data(p) for p in self.pages]
        n = len(pages)
        content = pages[1:] if n > 1 else pages

        # recurring drawings / images / short texts (text compared per span: footers and page
        # numbers are often merged into one block by PDF producers)
        def span_sig(sp):
            t = sp["text"].strip()
            box = self._norm(fitz.Rect(sp["bbox"]))
            if t.isdigit():
                return ("slide_number", tuple(round(v * 50) / 50 for v in (box[0], box[1], 0, box[3])), None)
            if 0 < len(t) <= 60:
                return self._sig("text", box, t)
            return None

        counts: Counter = Counter()
        for pd in content:
            sigs = set()
            for dr in pd["drawings"]:
                sigs.add(self._sig("autoshape", self._norm(dr["bbox"]), dr["fill"]))
            for im in pd["images"]:
                sigs.add(self._sig("picture", self._norm(im["bbox"]), im["digest"]))
            for b in pd["blocks"]:
                for sp in b["spans"]:
                    sig = span_sig(sp)
                    if sig:
                        sigs.add(sig)
            counts.update(sigs)
        threshold = max(2, int(0.5 * len(content) + 0.5))
        deco = {s for s, c in counts.items() if c >= threshold}

        def block_sig(b):
            # A block is decoration only if every span in it is a recurring decoration span.
            if all((span_sig(sp) in deco) for sp in b["spans"]):
                return ("deco",)
            return ("content", id(b))

        stats = ContentStats()
        fills, text_cols, fonts_title, fonts_body = ColorTally(), ColorTally(), Counter(), Counter()
        title_sizes, body_sizes, title_boxes, body_boxes, image_boxes, labels = [], [], [], [], [], []
        title_colors, body_colors = ColorTally(), ColorTally()
        bg_colors = ColorTally()

        for i, pd in enumerate(pages):
            blocks = [b for b in pd["blocks"] if block_sig(b) != ("deco",)]
            full = [dr for dr in pd["drawings"] if dr["bbox"].width * dr["bbox"].height >= 0.85 * self.W * self.H]
            bg_colors.add(full[-1]["fill"] if full else "#FFFFFF", 1)
            for dr in pd["drawings"]:
                if dr not in full:
                    fills.add(dr["fill"], (dr["bbox"].width * dr["bbox"].height) / (self.W * self.H))
            title = max(blocks, key=lambda b: (b["max_size"], -b["bbox"].y0), default=None) if blocks else None
            body = [b for b in blocks if b is not title]
            for b in blocks:
                for s in b["spans"]:
                    n_ch = len(s["text"].strip())
                    fam = clean_font_name(s.get("font"))
                    col = _int_color(s.get("color", 0))
                    text_cols.add(col, n_ch)
                    if b is title:
                        fonts_title[fam] += n_ch
                        title_sizes.append(round(s["size"], 1))
                        title_colors.add(col, n_ch)
                    else:
                        fonts_body[fam] += n_ch
                        body_sizes.extend([round(s["size"], 1)] * min(n_ch, 40))
                        body_colors.add(col, n_ch)
            pics = [im for im in pd["images"] if self._sig("picture", self._norm(im["bbox"]), im["digest"]) not in deco]
            label = classify_slide(index=i, title=title["text"] if title else "",
                                   texts=[ln for b in body for ln in b["lines"]], n_text_blocks=len(body),
                                   n_pictures=len(pics), n_tables=0, n_charts=0,
                                   has_two_columns=any(b["bbox"].x1 < self.W * 0.55 for b in body)
                                   and any(b["bbox"].x0 > self.W * 0.45 for b in body),
                                   is_first=i == 0 and n > 1)
            labels.append(label)
            if i > 0:
                if title:
                    title_boxes.append(self._norm(title["bbox"]))
                    stats.titles.append(title["text"].replace("\n", " "))
                lines = [ln.lstrip("•-–· ").strip() for b in body for ln in b["lines"]]
                lines = [ln for ln in lines if ln]
                stats.bullets_per_slide.append(len(lines))
                stats.words_per_bullet.extend(len(ln.split()) for ln in lines)
                stats.body_text.extend(lines)
                others = [b["bbox"] for b in body] + [im["bbox"] for im in pics]
                if others:
                    x0 = min(r.x0 for r in others)
                    y0 = min(r.y0 for r in others)
                    x1 = max(r.x1 for r in others)
                    y1 = max(r.y1 for r in others)
                    body_boxes.append(self._norm(fitz.Rect(x0, y0, x1, y1)))
                image_boxes.extend(self._norm(im["bbox"]) for im in pics)

        def median_box(boxes):
            if not boxes:
                return None
            xs = statistics.median(b[0] for b in boxes)
            ys = statistics.median(b[1] for b in boxes)
            x2 = statistics.median(b[0] + b[2] for b in boxes)
            y2 = statistics.median(b[1] + b[3] for b in boxes)
            return [round(xs, 4), round(ys, 4), round(x2 - xs, 4), round(y2 - ys, 4)]

        fill_rank = fills.ranked()
        brand = [c for c, _ in fill_rank if not is_neutral(c)]
        text_rank = [c for c, _ in text_cols.ranked() if not is_neutral(c)]
        primary = brand[0] if brand else (text_rank[0] if text_rank else "#1D4ED8")
        secondary = next((c for c in brand[1:] + text_rank if c != primary), "#F59E0B")
        background = (bg_colors.ranked() or [("#FFFFFF", 1)])[0][0]
        heading = (fonts_title.most_common(1)[0][0] if fonts_title else None) or "Arial"
        body_font = (fonts_body.most_common(1)[0][0] if fonts_body else None) or "Arial"
        text_color = (body_colors.ranked() or [("#1F2937", 1)])[0][0]
        title_color = (title_colors.ranked() or [(text_color, 1)])[0][0]

        # decorations as concrete, re-creatable items (from the first content page that has most of them)
        donor_idx, best = (1 if n > 1 else 0), -1
        for i, pd in enumerate(pages[1:], start=1):
            present = sum(1 for dr in pd["drawings"] if self._sig("autoshape", self._norm(dr["bbox"]), dr["fill"])
                          in deco) + sum(1 for im in pd["images"]
                                         if self._sig("picture", self._norm(im["bbox"]), im["digest"]) in deco)
            if present > best:
                best, donor_idx = present, i
        items = []
        page_area = self.W * self.H
        if pages:
            pd = pages[donor_idx]
            shape_boxes = []
            for dr in pd["drawings"]:
                if dr["bbox"].width * dr["bbox"].height >= 0.85 * page_area:
                    continue  # full-page fills are the background, not decorations
                if self._sig("autoshape", self._norm(dr["bbox"]), dr["fill"]) in deco:
                    items.append({"kind": "autoshape", "bbox": list(self._norm(dr["bbox"])), "fill": dr["fill"]})
                    shape_boxes.append(dr["bbox"])
            for im in pd["images"]:
                if self._sig("picture", self._norm(im["bbox"]), im["digest"]) not in deco or not im["xref"]:
                    continue
                # Renderers often rasterise shape effects (shadows) into images overlapping the shape itself.
                if any(_overlap(im["bbox"], sb) > 0.6 for sb in shape_boxes):
                    continue
                items.append({"kind": "picture", "bbox": list(self._norm(im["bbox"])), "xref": im["xref"],
                              "page": donor_idx})
            for b in pd["blocks"]:
                for sp in b["spans"]:
                    sig = span_sig(sp)
                    if sig and sig in deco:
                        items.append({"kind": sig[0], "bbox": list(self._norm(fitz.Rect(sp["bbox"]))),
                                      "text": sp["text"].strip() if sig[0] == "text" else None,
                                      "size": round(sp["size"], 1), "color": _int_color(sp.get("color", 0)),
                                      "font": clean_font_name(sp.get("font"))})
        cover_items, cover_zone = [], None
        if n > 1:
            cp = pages[0]
            full = [dr for dr in cp["drawings"] if dr["bbox"].width * dr["bbox"].height >= 0.85 * self.W * self.H]
            for dr in cp["drawings"]:
                if dr not in full:
                    cover_items.append({"kind": "autoshape", "bbox": list(self._norm(dr["bbox"])), "fill": dr["fill"]})
            for im in cp["images"]:
                if im["xref"]:
                    cover_items.append({"kind": "picture", "bbox": list(self._norm(im["bbox"])), "xref": im["xref"],
                                        "page": 0})
            tb = sorted(cp["blocks"], key=lambda b: -b["max_size"])
            if tb:
                cover_zone = {
                    "title": list(self._norm(tb[0]["bbox"])), "title_pt": round(tb[0]["max_size"], 1),
                    "title_color": _int_color(tb[0]["spans"][0].get("color", 0)),
                    "subtitle": list(self._norm(tb[1]["bbox"])) if len(tb) > 1 else None,
                    "subtitle_pt": round(tb[1]["max_size"], 1) if len(tb) > 1 else None,
                    "subtitle_color": _int_color(tb[1]["spans"][0].get("color", 0)) if len(tb) > 1 else None,
                    "align": "center" if abs((tb[0]["bbox"].x0 + tb[0]["bbox"].x1) / 2 - self.W / 2) < self.W * 0.05
                    else "left",
                }
            cover_bg = {"kind": "solid", "color": full[-1]["fill"]} if full else {"kind": "solid", "color": background}
        else:
            cover_bg = {"kind": "solid", "color": background}

        image_zone = median_box(image_boxes)
        title_zone = median_box(title_boxes)
        body_zone = median_box(body_boxes)
        if title_zone and body_zone:
            # PDF text boxes hug their text; widen the title zone to the content column.
            title_zone[2] = max(title_zone[2], round(body_zone[0] + body_zone[2] - title_zone[0], 4))
        return {
            "source_kind": "pdf",
            "slide_size": {"w": int(self.W * 12700), "h": int(self.H * 12700)},
            "theme": {"colors": {}, "fonts": {"major": heading, "minor": body_font}},
            "colors": {
                "primary": primary, "secondary": secondary,
                "accents": [c for c, _ in fill_rank[:6]] or [primary, secondary],
                "background": background, "text": text_color, "title": title_color,
                "palette": fill_rank[:8], "dark_background": luminance(background) < 0.25,
            },
            "fonts": {
                "heading": {"family": heading, "fallback": fallback_for(heading)},
                "body": {"family": body_font, "fallback": fallback_for(body_font)},
                "arabic": {"family": "Noto Sans Arabic", "fallback": "Noto Sans Arabic"},
            },
            "typography": {
                "title_pt": statistics.median(title_sizes) if title_sizes else 36.0,
                "body_pt": statistics.median(body_sizes) if body_sizes else 20.0,
                "min_pt": max(14.0, min(body_sizes)) if body_sizes else 16.0,
                "title_bold": True,
            },
            "zones": {"title": title_zone, "body": body_zone, "image": image_zone,
                      "image_side": ("right" if image_zone and image_zone[0] + image_zone[2] / 2 > 0.5 else "left")
                      if image_zone else "right", "cover": cover_zone},
            "layouts": [],
            "layout_map": {},
            "decorations": {
                "content": {"donor_slide": donor_idx, "items": items, "background": {"kind": "solid",
                                                                                      "color": background}},
                "cover": {"donor_slide": 0, "items": cover_items, "background": cover_bg} if n > 1 else None,
            },
            "layouts_found": [{"key": k, "count": c} for k, c in Counter(labels).most_common()],
            "slide_labels": labels,
            "content_style": stats.summary(),
            "visual_rules": {"corner_radius": "square", "uses_images": bool(image_boxes),
                             "image_slides_ratio": round(len(image_boxes) / max(1, len(content)), 2),
                             "title_align": "left"},
            "stats": {"slides": n, "decoration_count": len(deco), "text_layer": self.has_text_layer()},
        }

    def extract_image(self, xref: int) -> tuple[bytes, str]:
        """Extract an embedded image as PNG, re-applying its soft mask (alpha) when present."""
        info = self.doc.extract_image(xref)
        smask = info.get("smask") or 0
        pix = fitz.Pixmap(self.doc, xref)
        if smask:
            try:
                pix = fitz.Pixmap(pix, fitz.Pixmap(self.doc, smask))
            except Exception:
                pass
        if pix.n - pix.alpha >= 4:  # CMYK -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return pix.tobytes("png"), "png"

    def render_region(self, page_index: int, bbox_norm: list[float], dpi: int = 150) -> bytes:
        """Crop what the page actually shows in a region (keeps colours/effects that raw images lose)."""
        page = self.pages[page_index]
        x, y, w, h = bbox_norm
        clip = fitz.Rect(max(0, x) * self.W, max(0, y) * self.H, min(1, x + w) * self.W, min(1, y + h) * self.H)
        return page.get_pixmap(dpi=dpi, clip=clip, alpha=False).tobytes("png")

    def decoration_images(self, analysis: dict[str, Any]) -> dict[str, bytes]:
        """Materialise picture decorations; items get an `image_key` and a bbox clipped to the page."""
        out: dict[str, bytes] = {}
        for role in ("content", "cover"):
            d = (analysis.get("decorations") or {}).get(role)
            for i, it in enumerate((d or {}).get("items", [])):
                if it.get("kind") != "picture":
                    continue
                key = f"{role}-{i}"
                out[key] = self.render_region(it.get("page", 0), it["bbox"])
                x, y, w, h = it["bbox"]
                x2, y2 = min(1.0, x + w), min(1.0, y + h)
                x, y = max(0.0, x), max(0.0, y)
                it["bbox"] = [x, y, x2 - x, y2 - y]
                it["image_key"] = key
        return out

    def fingerprint(self) -> str:
        return hashlib.sha1(self.path.read_bytes()).hexdigest()


def analyze_pdf(path: Path) -> dict[str, Any]:
    return PdfAnalyzer(path).analyze()

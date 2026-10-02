"""Build a reusable template from a style analysis.

native        (PPTX uploads)  the teacher's own file, reduced to 1-2 "donor" slides whose decorations
                              (logos, header bands, backgrounds, footers) are cloned onto every new
                              slide. Masters, layouts and theme are untouched, so output *is* their design.
reconstructed (PDF uploads)   a clean master rebuilt from extracted colours, fonts and decorations.
builtin                       the same reconstructed path, from a curated default style.

Output: (base_pptx_bytes, TemplateSpec dict). The renderer needs nothing else.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Pt

from app.engine.pptx_xml import delete_all_slides_except, write_theme
from app.engine.style.common import contrast_ratio, luminance, mix, readable_text_on
from app.engine.style.content import extract_content

SPEC_VERSION = 3
DEFAULT_TITLE = [0.05, 0.05, 0.9, 0.13]


def _rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h.lstrip("#").upper()[:6])


# --------------------------------------------------------------------------- zone sanitising


def _bottom_decoration_top(items: list[dict]) -> float:
    tops = [it["bbox"][1] for it in items or [] if it["bbox"][1] > 0.72 and it["bbox"][3] < 0.2]
    return min(tops) if tops else 0.95


def _top_band_bottom(items: list[dict]) -> float:
    bottoms = [it["bbox"][1] + it["bbox"][3] for it in items or []
               if it["bbox"][1] <= 0.02 and it["bbox"][2] > 0.6 and it["bbox"][3] < 0.3]
    return max(bottoms) if bottoms else 0.0


def sanitize_zones(zones: dict[str, Any], deco_items: list[dict]) -> dict[str, Any]:
    title = list(zones.get("title") or DEFAULT_TITLE)
    if title[3] < 0.06:
        title[3] = 0.1
    if title[2] < 0.4:
        title[2] = max(title[2], 0.9 - title[0])
    title[0] = max(0.02, title[0])
    title[2] = min(title[2], 0.98 - title[0])
    band_bottom = _top_band_bottom(deco_items)
    if band_bottom and title[1] + title[3] > band_bottom + 0.02 and title[1] < band_bottom:
        title[3] = band_bottom - title[1] - 0.01  # keep the title on the band
    footer_top = _bottom_decoration_top(deco_items)
    title_bottom = max(title[1] + title[3], band_bottom)

    body = list(zones.get("body") or [title[0], title_bottom + 0.04, title[2], 0.0])
    x = max(0.03, min(body[0], title[0] + 0.02))
    y = max(body[1], title_bottom + 0.035)
    right = max(body[0] + body[2], title[0] + title[2])
    right = min(right, 0.97)
    bottom = footer_top - 0.025
    body = [round(x, 4), round(y, 4), round(right - x, 4), round(bottom - y, 4)]
    if body[3] < 0.4 or body[2] < 0.5:
        body = [0.06, round(title_bottom + 0.04, 4), 0.88, round(footer_top - 0.03 - title_bottom - 0.04, 4)]
    # Content sits inside a large decorative "container" card? Pad inside it.
    for it in deco_items or []:
        bx = it.get("bbox") or [0, 0, 0, 0]
        if it.get("kind") != "autoshape" or bx[2] * bx[3] < 0.25 or bx[2] > 0.99:
            continue
        cx, cy = body[0] + body[2] / 2, body[1] + body[3] / 2
        if bx[0] <= cx <= bx[0] + bx[2] and bx[1] <= cy <= bx[1] + bx[3]:
            pad_x, pad_y = 0.025, 0.04
            body = [round(bx[0] + pad_x, 4), round(max(bx[1] + pad_y, title_bottom + 0.02), 4),
                    round(bx[2] - 2 * pad_x, 4), 0.0]
            body[3] = round(min(bx[1] + bx[3] - pad_y, footer_top - 0.02) - body[1], 4)
            break
    image = zones.get("image")
    side = zones.get("image_side") or "right"
    return {"title": [round(v, 4) for v in title], "body": body, "image": image, "image_side": side,
            "footer_top": round(footer_top, 4), "band_bottom": round(band_bottom, 4)}


def derive_colors(analysis: dict[str, Any]) -> dict[str, str]:
    c = analysis["colors"]
    primary = c.get("primary") or "#2563EB"
    secondary = c.get("secondary") or "#F59E0B"
    background = c.get("background") or "#FFFFFF"
    text = c.get("text") or readable_text_on(background)
    if contrast_ratio(text, background) < 4.5:
        text = readable_text_on(background)
    dark = luminance(background) < 0.25
    card_bg = mix(primary, background, 0.86 if not dark else 0.75)
    return {
        "primary": primary,
        "secondary": secondary,
        "background": background,
        "text": text,
        "title": c.get("title") or text,
        "muted": mix(text, background, 0.45),
        "card_bg": card_bg,
        "card_text": readable_text_on(card_bg),
        "card_border": primary,
        "on_primary": readable_text_on(primary),
        "on_secondary": readable_text_on(secondary),
        "heading_accent": primary if contrast_ratio(primary, background) >= 3 else text,
    }


# --------------------------------------------------------------------------- builders


def _base_spec(analysis: dict[str, Any], mode: str, deco_items: list[dict]) -> dict[str, Any]:
    zones = sanitize_zones(analysis.get("zones", {}), deco_items)
    typo = analysis.get("typography", {})
    fonts = analysis.get("fonts", {})
    return {
        "version": SPEC_VERSION,
        "mode": mode,
        "slide_size": analysis["slide_size"],
        "colors": derive_colors(analysis),
        "fonts": {
            "heading": fonts.get("heading", {}).get("family") or "Arial",
            "body": fonts.get("body", {}).get("family") or "Arial",
            "arabic": fonts.get("arabic", {}).get("family") or "Noto Sans Arabic",
        },
        "typography": {
            "title_pt": float(min(max(typo.get("title_pt", 36), 24), 48)),
            "body_pt": float(min(max(typo.get("body_pt", 20), 16), 32)),
            "min_pt": 16.0,  # legibility floor (admin-configurable in QC settings), not the teacher's smallest text
            "title_bold": bool(typo.get("title_bold", True)),
            "title_align": analysis.get("visual_rules", {}).get("title_align", "left"),
        },
        "zones": zones,
        "corner_radius": analysis.get("visual_rules", {}).get("corner_radius", "rounded"),
        "content_style": analysis.get("content_style", {}),
        "cover": None,
        "content": None,
        "donor_count": 0,
    }


def build_native(source: Path, analysis: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    prs = Presentation(str(source))
    deco = analysis.get("decorations") or {}
    content = deco.get("content")
    cover = deco.get("cover")
    content_items = (content or {}).get("items", [])
    spec = _base_spec(analysis, "native", content_items)
    spec["extracted_style_defaults"] = {key: dict(spec[key]) for key in ("colors", "fonts", "typography")}

    variants = analysis.get("stage_variants") or []
    spec["source_content"], _ = extract_content(prs)
    donors = sorted({d["donor_slide"] for d in (content, cover, *variants) if d})
    delete_all_slides_except(prs, donors)
    new_index = {old: i for i, old in enumerate(donors)}
    spec["donor_count"] = len(donors)

    lm = analysis.get("layout_map", {})
    layouts = analysis.get("layouts", [])

    def layout_meta(i: int | None) -> dict | None:
        return layouts[i] if i is not None and 0 <= i < len(layouts) else None

    content_layout = lm.get("content_layout_index", 6 if len(prs.slide_layouts) > 6 else 0)
    meta = layout_meta(content_layout) or {"placeholders": []}
    ph_types = {p["type"]: p for p in meta["placeholders"]}
    use_ph = "title" in ph_types and "body" in ph_types and not content_items
    if use_ph:
        spec["zones"]["title"] = [round(v, 4) for v in ph_types["title"]["bbox"]]
        spec["zones"]["body"] = [round(v, 4) for v in ph_types["body"]["bbox"]]
    spec["content"] = {
        "layout_index": content_layout,
        "donor_index": new_index.get(content["donor_slide"]) if content else None,
        "item_ids": [it["shape_id"] for it in content_items if it["kind"] != "slide_number"],
        "slide_number_ids": [it["shape_id"] for it in content_items if it["kind"] == "slide_number"],
        "copy_background": bool(content and (content.get("background") or {}).get("source") == "slide"),
        "use_placeholders": use_ph,
    }
    cz = (analysis.get("zones") or {}).get("cover")
    spec["cover"] = {
        "layout_index": lm.get("cover_layout_index", content_layout),
        "donor_index": new_index.get(cover["donor_slide"]) if cover else None,
        "item_ids": [it["shape_id"] for it in (cover or {}).get("items", [])],
        "copy_background": bool(cover and (cover.get("background") or {}).get("source") == "slide"),
        "zone": cz,
        "use_placeholders": False,
    }
    cover_meta = layout_meta(spec["cover"]["layout_index"])
    if cover_meta and cover and not cover.get("items") and any(p["type"] == "title" for p in cover_meta["placeholders"]):
        spec["cover"]["use_placeholders"] = True
    spec["section"] = {"layout_index": lm.get("section_layout_index")}
    spec["layouts"] = [{"index": m["index"], "name": m["name"],
                        "placeholder_types": [p["type"] for p in m["placeholders"]]} for m in layouts]
    spec["stage_variants"] = {}
    for variant in variants:
        ids = [variant["header_id"]] if variant.get("header_id") is not None else []
        spec["stage_variants"].setdefault(variant["stage"], {
            "layout_index": variant["layout_index"], "donor_index": new_index[variant["donor_slide"]],
            "item_ids": ids, "clear_text_ids": ids, "use_placeholders": False,
            "copy_background": variant["background"].get("source") == "slide",
            "zones": {**spec["zones"], **variant["zones"]},
            "colors": {**spec["colors"], "title": "#000000"},
            "typography": {**spec["typography"], "title_align": "left", "title_bold": True,
                           "title_pt": 28},
            "fonts": {**spec["fonts"], "heading": variant["header_font"]},
        })
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue(), spec


def _add_rect(slide, box, fill: str, kind: str = "rect"):
    shape_type = MSO_SHAPE.OVAL if kind == "oval" else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape_type, *box)
    sh.fill.solid()
    sh.fill.fore_color.rgb = _rgb(fill)
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def build_reconstructed(analysis: dict[str, Any], *, images: dict[str, bytes] | None = None,
                        mode: str = "reconstructed") -> tuple[bytes, dict[str, Any]]:
    """Create a fresh presentation that reproduces the analysed style."""
    images = images or {}
    prs = Presentation()
    prs.slide_width = Emu(analysis["slide_size"]["w"])
    prs.slide_height = Emu(analysis["slide_size"]["h"])
    W, H = prs.slide_width, prs.slide_height
    deco = analysis.get("decorations") or {}
    content = deco.get("content") or {"items": [], "background": None}
    cover = deco.get("cover")
    spec = _base_spec(analysis, mode, content.get("items", []))
    colors = spec["colors"]
    write_theme(prs, colors={
        "dk1": colors["text"], "lt1": "#FFFFFF", "dk2": colors["primary"], "lt2": colors["card_bg"],
        "accent1": colors["primary"], "accent2": colors["secondary"], "accent3": mix(colors["primary"], "#FFFFFF", 0.35),
        "accent4": mix(colors["secondary"], "#000000", 0.2), "accent5": "#64748B", "accent6": "#0EA5E9",
    }, fonts={"major": spec["fonts"]["heading"], "minor": spec["fonts"]["body"]})
    bg = prs.slide_master.background.fill
    bg.solid()
    bg.fore_color.rgb = _rgb(colors["background"])

    blank = prs.slide_layouts[6]

    def box(b):
        return (Emu(int(b[0] * W)), Emu(int(b[1] * H)), Emu(max(1, int(b[2] * W))), Emu(max(1, int(b[3] * H))))

    def make_donor(items: list[dict], background: dict | None) -> tuple[list[int], list[int], bool]:
        slide = prs.slides.add_slide(blank)
        copy_bg = False
        if background and background.get("kind") == "solid" and background.get("color") and \
                background["color"].upper() != colors["background"].upper():
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = _rgb(background["color"])
            copy_bg = True
        ids, num_ids = [], []
        for it in items:
            if it["kind"] == "autoshape" and it.get("fill"):
                sh = _add_rect(slide, box(it["bbox"]), it["fill"], it.get("shape", "rect"))
                ids.append(sh.shape_id)
            elif it["kind"] == "picture" and it.get("image_key") in images:
                sh = slide.shapes.add_picture(io.BytesIO(images[it["image_key"]]), *box(it["bbox"]))
                ids.append(sh.shape_id)
            elif it["kind"] in ("text", "slide_number"):
                b = list(it["bbox"])
                if it["kind"] == "slide_number":
                    b = [b[0] - 0.03, b[1], max(b[2], 0.04) + 0.03, b[3]]
                tb = slide.shapes.add_textbox(*box(b))
                tf = tb.text_frame
                tf.word_wrap = False
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                p = tf.paragraphs[0]
                run = p.add_run()
                run.text = it.get("text") or "#"
                run.font.size = Pt(it.get("size") or 11)
                run.font.color.rgb = _rgb(it.get("color") or colors["muted"])
                run.font.name = it.get("font") or spec["fonts"]["body"]
                if it["kind"] == "slide_number":
                    from pptx.enum.text import PP_ALIGN

                    p.alignment = PP_ALIGN.RIGHT
                    num_ids.append(tb.shape_id)
                else:
                    ids.append(tb.shape_id)
        return ids, num_ids, copy_bg

    donor_count = 0
    cover_spec = None
    if cover:
        ids, _, copy_bg = make_donor(cover.get("items", []), cover.get("background"))
        cover_spec = {"layout_index": 6, "donor_index": donor_count, "item_ids": ids, "copy_background": copy_bg,
                      "zone": (analysis.get("zones") or {}).get("cover"), "use_placeholders": False}
        donor_count += 1
    ids, num_ids, copy_bg = make_donor(content.get("items", []), content.get("background"))
    spec["content"] = {"layout_index": 6, "donor_index": donor_count, "item_ids": ids, "slide_number_ids": num_ids,
                       "copy_background": copy_bg, "use_placeholders": False}
    donor_count += 1
    spec["cover"] = cover_spec or {"layout_index": 6, "donor_index": None, "item_ids": [], "copy_background": False,
                                   "zone": None, "use_placeholders": False}
    spec["section"] = {"layout_index": None}
    spec["donor_count"] = donor_count
    spec["layouts"] = []
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue(), spec


# --------------------------------------------------------------------------- built-in styles

BUILTIN_STYLES: dict[str, dict[str, Any]] = {
    "clean-blue": {"name": "Clean Classroom", "primary": "#1D4ED8", "secondary": "#F59E0B", "background": "#FFFFFF",
                   "text": "#1F2937", "heading": "Montserrat", "body": "Open Sans", "band": False},
    "warm-sand": {"name": "Warm Sand", "primary": "#B45309", "secondary": "#0F766E", "background": "#FFFBF5",
                  "text": "#292524", "heading": "Lato", "body": "Lato", "band": True},
    "chalkboard": {"name": "Chalkboard", "primary": "#34D399", "secondary": "#FBBF24", "background": "#1F2A30",
                   "text": "#F1F5F9", "heading": "Comic Neue", "body": "Open Sans", "band": False},
}


def builtin_analysis(key: str) -> dict[str, Any]:
    st = BUILTIN_STYLES[key]
    W, H = 12192000, 6858000
    content_items: list[dict[str, Any]] = [
        {"kind": "autoshape", "bbox": [0.05, 0.195, 0.08, 0.008], "fill": st["secondary"]},
        {"kind": "autoshape", "bbox": [0.0, 0.955, 1.0, 0.045], "fill": st["primary"]},
    ]
    if st["band"]:
        content_items = [{"kind": "autoshape", "bbox": [0.0, 0.0, 1.0, 0.17], "fill": st["primary"]},
                         {"kind": "autoshape", "bbox": [0.0, 0.17, 1.0, 0.008], "fill": st["secondary"]},
                         {"kind": "autoshape", "bbox": [0.0, 0.975, 1.0, 0.025], "fill": st["primary"]}]
    title_color = "#FFFFFF" if st["band"] else st["text"]
    cover_items = [
        {"kind": "autoshape", "bbox": [0.0, 0.0, 0.035, 1.0], "fill": st["primary"]},
        {"kind": "autoshape", "bbox": [0.72, -0.25, 0.5, 0.9], "fill": mix(st["primary"], st["background"], 0.85),
         "shape": "oval"},
        {"kind": "autoshape", "bbox": [0.08, 0.62, 0.12, 0.012], "fill": st["secondary"]},
    ]
    return {
        "source_kind": "builtin",
        "slide_size": {"w": W, "h": H},
        "colors": {"primary": st["primary"], "secondary": st["secondary"], "background": st["background"],
                   "text": st["text"], "title": title_color},
        "fonts": {"heading": {"family": st["heading"]}, "body": {"family": st["body"]},
                  "arabic": {"family": "Noto Sans Arabic"}},
        "typography": {"title_pt": 34, "body_pt": 22, "min_pt": 16, "title_bold": True},
        "zones": {"title": [0.05, 0.035 if st["band"] else 0.06, 0.9, 0.11 if st["band"] else 0.12],
                  "body": [0.05, 0.25, 0.9, 0.66], "image": None, "image_side": "right",
                  "cover": {"title": [0.08, 0.3, 0.62, 0.26], "title_pt": 46, "title_color": st["text"],
                            "subtitle": [0.08, 0.66, 0.62, 0.1], "subtitle_pt": 22, "subtitle_color": st["primary"],
                            "align": "left"}},
        "decorations": {"content": {"items": content_items, "background": None},
                        "cover": {"items": cover_items, "background": None}},
        "visual_rules": {"corner_radius": "rounded", "title_align": "left"},
        "content_style": {"bullets_per_slide": [3, 5], "avg_words_per_bullet": 9},
        "layout_map": {},
        "layouts_found": [],
    }


def build_builtin(key: str) -> tuple[bytes, dict[str, Any]]:
    return build_reconstructed(builtin_analysis(key), mode="builtin")

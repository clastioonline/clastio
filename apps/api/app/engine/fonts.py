"""Detect unavailable donor fonts before rendering can silently substitute them."""
from __future__ import annotations

import io
import logging
import subprocess
import zipfile

from lxml import etree

logger = logging.getLogger("fonts")


def required_fonts(pptx: bytes) -> set[str]:
    fonts = set()
    with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
        for name in archive.namelist():
            if name.startswith("ppt/") and name.endswith(".xml"):
                root = etree.fromstring(archive.read(name), parser=etree.XMLParser(resolve_entities=False, no_network=True))
                fonts.update(value.strip() for value in root.xpath("//a:latin/@typeface | //a:ea/@typeface | //a:cs/@typeface",
                                           namespaces={"a": "http://schemas.openxmlformats.org/drawingml/2006/main"})
                             if value.strip() and not value.startswith("+"))
    return fonts


def audit_fonts(pptx: bytes) -> list[dict[str, str]]:
    try:
        result = subprocess.run(["fc-list", "--format", "%{family}\\n"], capture_output=True, text=True,
                                timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return [{"code": "font_inventory_unavailable", "message": "Server font inventory could not be checked."}]
    installed = {family.strip().casefold() for line in result.stdout.splitlines() for family in line.split(",")}
    warnings = [{"code": "missing_font", "font": font,
                 "message": f"{font} is unavailable on the worker. Install the licensed font in deploy/fonts and in the rendering service; substitution can change text wrapping."}
                for font in sorted(required_fonts(pptx)) if font.casefold() not in installed]
    for warning in warnings:
        logger.warning("missing_template_font font=%s", warning["font"])
    return warnings

"""Client IP and a coarse device description from the User-Agent (no fingerprinting)."""

from __future__ import annotations

import re

from fastapi import Request


def client_ip(request: Request | None) -> str | None:
    # uvicorn's proxy-headers middleware has already resolved X-Forwarded-For from trusted proxies.
    return request.client.host if request is not None and request.client else None


def user_agent(request: Request | None) -> str | None:
    ua = request.headers.get("user-agent") if request is not None else None
    return ua[:400] if ua else None


_BROWSERS = [("Edge", r"Edg/"), ("Opera", r"OPR/"), ("Samsung Internet", r"SamsungBrowser"), ("Chrome", r"Chrome/"),
             ("Firefox", r"Firefox/"), ("Safari", r"Safari/")]
_OS = [("iOS", r"iPhone|iPad|iPod"), ("Android", r"Android"), ("Windows", r"Windows"), ("macOS", r"Mac OS X"),
       ("ChromeOS", r"CrOS"), ("Linux", r"Linux")]


def parse_user_agent(ua: str | None) -> dict[str, str]:
    ua = ua or ""
    if re.search(r"bot|crawler|spider|curl|python-requests|httpx", ua, re.I):
        device = "bot"
    elif re.search(r"iPad|Tablet", ua):
        device = "tablet"
    elif re.search(r"Mobi|iPhone|Android", ua):
        device = "mobile"
    elif ua:
        device = "desktop"
    else:
        device = "unknown"
    browser = next((name for name, pat in _BROWSERS if re.search(pat, ua)), "Other")
    os_name = next((name for name, pat in _OS if re.search(pat, ua)), "Other")
    return {"browser": browser, "os": os_name, "device_type": device}

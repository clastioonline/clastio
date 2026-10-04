"""Bounded downloads for images returned by public stock search."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx


async def validate_public_image_url(url: str) -> str:
    target = urlsplit(url)
    if target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password:
        raise ValueError("Invalid remote image URL")
    if target.port not in (None, 80, 443):
        raise ValueError("Unexpected remote image port")
    try:
        records = await asyncio.wait_for(
            asyncio.to_thread(
                socket.getaddrinfo,
                target.hostname,
                target.port or (443 if target.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            ),
            timeout=5,
        )
    except (OSError, TimeoutError) as exc:
        raise ValueError("Remote image host could not be verified") from exc
    if not records or any(not ipaddress.ip_address(record[4][0]).is_global for record in records):
        raise ValueError("Remote image host is not public")
    return records[0][4][0]


async def download_public_image(url: str, max_bytes: int, *, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    # Connect to the validated IP, retaining the original HTTP host and TLS SNI.
    # A second DNS lookup must not turn a public host into a private destination.
    # Avoid environment proxies and connection reuse between virtual hosts.
    async with httpx.AsyncClient(
        transport=transport,
        trust_env=False,
        limits=httpx.Limits(max_keepalive_connections=0),
        headers={"User-Agent": "Clastio/1.0"},
    ) as client:
        for _ in range(5):
            address = await validate_public_image_url(url)
            original = httpx.URL(url)
            pinned = original.copy_with(host=address)
            async with client.stream(
                "GET", pinned, timeout=12, follow_redirects=False,
                headers={"Host": original.netloc.decode("ascii")},
                extensions={"sni_hostname": original.host},
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Image redirect has no destination")
                    url = urljoin(url, location)
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError("Remote image is too large")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Remote image is too large")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError("Too many image redirects")

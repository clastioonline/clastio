import socket
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.remote_images import download_public_image, validate_public_image_url


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.2", "::1", "192.168.1.5"])
async def test_remote_image_blocks_internal_addresses(monkeypatch, address):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(ValueError, match="not public"):
        await validate_public_image_url("https://image.example/photo.jpg")


async def test_redirect_is_revalidated(monkeypatch):
    async def validate(url):
        if "169.254" in url:
            raise ValueError("blocked private host")
        return "93.184.216.34"

    check = AsyncMock(side_effect=validate)
    monkeypatch.setattr("app.core.remote_images.validate_public_image_url", check)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
    )
    with pytest.raises(ValueError, match="blocked"):
        await download_public_image("https://image.example/photo.jpg", 10, transport=transport)
    assert check.await_count == 2


async def test_remote_image_download_is_bounded(monkeypatch):
    monkeypatch.setattr("app.core.remote_images.validate_public_image_url", AsyncMock(return_value="93.184.216.34"))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"large payload"))
    with pytest.raises(ValueError, match="too large"):
        await download_public_image("https://image.example/photo.jpg", 3, transport=transport)


async def test_connection_pins_validated_ip_and_preserves_tls_host(monkeypatch):
    resolver = AsyncMock(return_value="93.184.216.34")
    monkeypatch.setattr("app.core.remote_images.validate_public_image_url", resolver)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, content=b"image")

    result = await download_public_image(
        "https://image.example/photo.jpg?size=large", 10, transport=httpx.MockTransport(respond)
    )
    assert result == b"image"
    assert requests[0].url.host == "93.184.216.34"
    assert requests[0].url.path == "/photo.jpg"
    assert requests[0].url.query == b"size=large"
    assert requests[0].headers["host"] == "image.example"
    assert requests[0].extensions["sni_hostname"] == "image.example"
    resolver.assert_awaited_once_with("https://image.example/photo.jpg?size=large")

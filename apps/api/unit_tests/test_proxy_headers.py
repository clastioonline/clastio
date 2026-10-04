"""Exercise the deployed Uvicorn trust boundary without a database or network."""

import re
from pathlib import Path

import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def deployed_trusted_proxies():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text()
    return re.search(r'^ENV FORWARDED_ALLOW_IPS="([^"]+)"$', dockerfile, re.M).group(1)


async def resolved_client(peer, forwarded_headers):
    observed = {}

    async def app(scope, receive, send):
        observed.update(client=scope["client"][0], scheme=scope["scheme"])

    middleware = ProxyHeadersMiddleware(app, trusted_hosts=deployed_trusted_proxies())
    await middleware(
        {
            "type": "http",
            "client": (peer, 8000),
            "scheme": "http",
            "headers": [(b"x-forwarded-for", value.encode()) for value in forwarded_headers]
            + [(b"x-forwarded-proto", b"https")],
        },
        None,
        None,
    )
    return observed


@pytest.mark.parametrize("peer", ["100.64.0.1", "100.127.255.254", "10.0.0.2"])
async def test_deployed_edge_resolves_client_and_https(peer):
    assert await resolved_client(peer, ["203.0.113.12"]) == {
        "client": "203.0.113.12",
        "scheme": "https",
    }


async def test_client_prepended_spoof_does_not_replace_edge_appended_address():
    assert (await resolved_client("100.64.0.4", ["198.51.100.99", "203.0.113.12, 10.0.0.3"]))[
        "client"
    ] == "203.0.113.12"


@pytest.mark.parametrize("peer", ["203.0.113.4", "100.128.0.1"])
async def test_untrusted_peer_cannot_override_client_or_scheme(peer):
    assert await resolved_client(peer, ["198.51.100.99"]) == {"client": peer, "scheme": "http"}


async def test_cross_provider_public_proxy_is_not_implicitly_trusted():
    assert (await resolved_client("100.64.0.4", ["198.51.100.99, 203.0.113.12"]))[
        "client"
    ] == "203.0.113.12"

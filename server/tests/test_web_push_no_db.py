import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("endpoint", ["http://fcm.googleapis.com/send/a", "https://127.0.0.1/a", "https://fcm.googleapis.com.evil.test/a", "https://fcm.googleapis.com:444/a", "https://user@fcm.googleapis.com/a", "https://fcm.googleapis.com/a#secret", "https://example.org/push"])
def test_rejects_ssrf_and_non_provider_endpoints(endpoint):
    from tickets.web_push import validate_endpoint
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


def test_vapid_header_verifies_as_es256_and_contains_only_provider_origin(tmp_path):
    from authlib.jose import JsonWebToken
    from tickets.web_push import PushConfig, vapid_headers

    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    config = PushConfig(pem, "mailto:helpdesk@example.org")
    headers = vapid_headers(config, "https://fcm.googleapis.com/fcm/send/opaque", now=1000)
    token = headers["Authorization"].split("t=", 1)[1].split(",", 1)[0]
    claims = JsonWebToken(["ES256"]).decode(token, private.public_key())
    assert claims["aud"] == "https://fcm.googleapis.com"
    assert claims["exp"] == 1000 + 12 * 3600
    assert headers["TTL"] == "86400"
    public = base64.urlsafe_b64decode(config.public_key + "==")
    assert len(public) == 65 and public[0] == 4


@pytest.mark.asyncio
async def test_transport_sends_empty_body_without_redirects_or_private_event_data():
    from tickets.web_push import PushConfig, send_wakeup

    private = ec.generate_private_key(ec.SECP256R1())
    config = PushConfig(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), "mailto:helpdesk@example.org")
    client = SimpleNamespace(post=AsyncMock(return_value=SimpleNamespace(status_code=201)))
    assert await send_wakeup(client, config, "https://fcm.googleapis.com/fcm/send/opaque") == 201
    kwargs = client.post.await_args.kwargs
    assert kwargs["content"] == b""
    assert kwargs["follow_redirects"] is False
    assert "json" not in kwargs


def test_config_disabled_without_explicit_key_and_contact(monkeypatch):
    from tickets.web_push import load_push_config
    monkeypatch.delenv("HELPDESK_WEB_PUSH_PRIVATE_KEY_FILE", raising=False)
    monkeypatch.delenv("HELPDESK_WEB_PUSH_SUBJECT", raising=False)
    assert load_push_config() is None


def test_edge_wns_query_endpoint_and_canonical_origin():
    from tickets.web_push import validate_endpoint
    assert validate_endpoint("https://wns2-test.notify.windows.com/w/?token=synthetic")
    with pytest.raises(ValueError):
        validate_endpoint("https://wns2-test.notify.windows.com.evil.test/w/?token=synthetic")


@pytest.mark.asyncio
async def test_wns_headers_are_provider_specific_and_urls_are_redacted(caplog):
    import httpx
    from tickets.web_push import PushConfig, send_wakeup
    private = ec.generate_private_key(ec.SECP256R1())
    config = PushConfig(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), "mailto:helpdesk@example.org")
    seen = []
    def provider(request):
        seen.append(request)
        return httpx.Response(201)
    caplog.set_level("INFO", logger="httpx")
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        await send_wakeup(client, config, "https://wns2-test.notify.windows.com/w/?token=synthetic-secret")
        await send_wakeup(client, config, "https://fcm.googleapis.com/fcm/send/synthetic-secret")
    assert seen[0].headers["X-WNS-Type"] == "wns/raw"
    assert seen[0].headers["Content-Type"] == "application/octet-stream"
    assert "X-WNS-Type" not in seen[1].headers
    assert "synthetic-secret" not in caplog.text
    assert "[redacted push endpoint]" in caplog.text

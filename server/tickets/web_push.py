"""Payload-free RFC 8030 wakeups authenticated with RFC 8292 VAPID.

The browser fetches event details from Helpdesk using its authenticated session;
neither chat text nor ticket identifiers are sent to the external push service.
"""
import base64
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from authlib.jose import JsonWebToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

PROVIDER_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"})


class _RedactPushUrls(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            redacted = []
            for value in record.args:
                try:
                    validate_endpoint(str(value))
                except (TypeError, ValueError):
                    redacted.append(value)
                else:
                    redacted.append("[redacted push endpoint]")
            record.args = tuple(redacted)
        return True


def validate_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= 4096 or any(ord(c) <= 32 for c in endpoint):
        raise ValueError("Invalid push endpoint")
    parts = urlsplit(endpoint)
    known_host = parts.hostname in PROVIDER_HOSTS or bool(re.fullmatch(r"[a-z0-9-]+\.notify\.windows\.com", parts.hostname or ""))
    if (parts.scheme != "https" or not known_host or parts.port not in (None, 443)
            or parts.username or parts.password or parts.fragment or not parts.path):
        raise ValueError("Unsupported push provider")
    return endpoint


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(validate_endpoint(endpoint).encode()).hexdigest()


@dataclass(frozen=True)
class PushConfig:
    private_key: bytes
    subject: str

    @property
    def public_key(self) -> str:
        key = serialization.load_pem_private_key(self.private_key, password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError("VAPID requires a P-256 private key")
        point = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(point).rstrip(b"=").decode("ascii")


def load_push_config() -> PushConfig | None:
    key_file = os.getenv("HELPDESK_WEB_PUSH_PRIVATE_KEY_FILE", "").strip()
    subject = os.getenv("HELPDESK_WEB_PUSH_SUBJECT", "").strip()
    if not key_file and not subject:
        return None
    if not key_file or not (subject.startswith("mailto:") or subject.startswith("https://")):
        raise ValueError("Configure Web Push key file and contact subject together")
    config = PushConfig(Path(key_file).read_bytes(), subject)
    config.public_key  # Validate once before enabling the feature.
    return config


def vapid_headers(config: PushConfig, endpoint: str, *, now: int | None = None) -> dict[str, str]:
    parts = urlsplit(validate_endpoint(endpoint))
    claims = {"aud": f"https://{parts.hostname}", "exp": (int(time.time()) if now is None else now) + 12 * 3600, "sub": config.subject}
    token = JsonWebToken(["ES256"]).encode({"alg": "ES256", "typ": "JWT"}, claims, config.private_key).decode("ascii")
    return {"Authorization": f"vapid t={token}, k={config.public_key}", "TTL": "86400", "Urgency": "normal", "Topic": "helpdesk-events"}


async def send_wakeup(client, config: PushConfig, endpoint: str) -> int:
    endpoint = validate_endpoint(endpoint)
    headers = vapid_headers(config, endpoint)
    if (urlsplit(endpoint).hostname or "").endswith(".notify.windows.com"):
        headers.update({"X-WNS-Type": "wns/raw", "Content-Type": "application/octet-stream"})
    response = await client.post(endpoint, content=b"", headers=headers, follow_redirects=False)
    return response.status_code


# HTTPX's INFO request log otherwise includes the access-bearing subscription URL.
logging.getLogger("httpx").addFilter(_RedactPushUrls())

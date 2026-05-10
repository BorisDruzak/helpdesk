from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger


TLS_CA_FILE_ENV_NAMES = (
    "PC_AGENT_TLS_CA_FILE",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
)


def build_remote_assist_ssl_context(url: str) -> ssl.SSLContext | None:
    """Build an aiohttp SSL context for HTTPS/WSS remote assist endpoints."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme.lower() not in {"https", "wss"}:
        return None

    context = ssl.create_default_context()
    loaded_windows = _load_windows_certificate_stores(context)
    loaded_files = _load_env_ca_files(context)
    logger.info(
        "Remote Assist TLS context prepared: scheme={} windows_certs={} ca_files={}",
        parsed.scheme,
        loaded_windows,
        loaded_files,
    )
    return context


def tls_error_hint(exc: BaseException) -> str:
    text = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" not in text and "SSLCertVerificationError" not in text:
        return text
    return (
        f"{text}. Install the stand root CA into Trusted Root Certification Authorities "
        "for the account running Maria Agent, or set PC_AGENT_TLS_CA_FILE to the CA .cer/.pem file."
    )


def _load_env_ca_files(context: ssl.SSLContext) -> list[str]:
    loaded: list[str] = []
    for env_name in TLS_CA_FILE_ENV_NAMES:
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.exists():
            logger.warning("Remote Assist TLS CA file from {} does not exist: {}", env_name, path)
            continue
        try:
            context.load_verify_locations(cafile=str(path))
            loaded.append(str(path))
        except Exception as exc:
            logger.warning("Remote Assist TLS CA file load failed: env={} path={} error={}", env_name, path, exc)
    return loaded


def _load_windows_certificate_stores(context: ssl.SSLContext) -> int:
    if sys.platform != "win32" or not hasattr(ssl, "enum_certificates"):
        return 0

    loaded = 0
    for store_name in ("ROOT", "CA"):
        try:
            certificates = ssl.enum_certificates(store_name)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("Remote Assist TLS Windows store read failed: store={} error={}", store_name, exc)
            continue
        for cert_bytes, encoding, _trust in certificates:
            if encoding != "x509_asn":
                continue
            try:
                context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert_bytes))
                loaded += 1
            except Exception:
                continue
    return loaded

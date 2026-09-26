"""Dependency-free production transport policy shared by startup and deploy."""
from __future__ import annotations

import ipaddress
from typing import Mapping
from urllib.parse import urlsplit


def production_config_errors(values: Mapping[str, object]) -> list[str]:
    if str(values.get("APP_ENV", "")).strip().lower() != "prod":
        return []
    errors: list[str] = []
    for name in ("ENABLE_DB_PERSISTENCE", "REQUIRE_HTTPS", "REQUIRE_WSS",
                 "WEB_SESSION_COOKIE_SECURE", "TRUST_X_FORWARDED_FOR"):
        if str(values.get(name, "")).lower() != "true":
            errors.append(f"{name} must be true in prod")
    for name in ("ALLOW_INSECURE_DEV_DEFAULTS", "AUTH_ALLOW_QUERY_TOKEN", "AUTH_UI_CONFIG_FALLBACK_ENABLED"):
        if str(values.get(name, "")).lower() != "false":
            errors.append(f"{name} must be false in prod")
    for name in ("SERVER_HOST", "CONTROL_HOST"):
        try:
            if not ipaddress.ip_address(str(values.get(name, ""))).is_loopback:
                raise ValueError()
        except ValueError:
            errors.append(f"{name} must be an explicit loopback IP in prod")
    try:
        public = urlsplit(str(values.get("SERVER_PUBLIC_BASE_URL", "")))
        if public.scheme != "https" or not public.hostname or public.username or public.password or public.query or public.fragment:
            raise ValueError()
        public.port
    except ValueError:
        errors.append("SERVER_PUBLIC_BASE_URL must be an HTTPS URL without credentials")
    try:
        proxies = str(values.get("TRUSTED_PROXY_CIDRS", "")).split(",")
        if not proxies or any(ipaddress.ip_network(item.strip(), strict=True).prefixlen == 0 for item in proxies):
            raise ValueError()
    except ValueError:
        errors.append("TRUSTED_PROXY_CIDRS must contain explicit non-wildcard networks")
    return errors

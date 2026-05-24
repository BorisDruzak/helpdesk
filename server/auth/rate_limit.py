"""Small in-memory rate limiter for auth-sensitive public endpoints."""
from __future__ import annotations

import time
import ipaddress
from collections import deque
from dataclasses import dataclass

from aiohttp import web
import config


@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window_seconds: int


_BUCKETS: dict[tuple[str, str], deque[float]] = {}


def _trusted_proxy_networks() -> list[ipaddress._BaseNetwork]:
    raw = getattr(config, "TRUSTED_PROXY_CIDRS", "") or ""
    networks: list[ipaddress._BaseNetwork] = []
    for item in str(raw).split(","):
        value = item.strip()
        if not value:
            continue
        try:
            if "/" not in value:
                ip = ipaddress.ip_address(value)
                value = f"{value}/32" if ip.version == 4 else f"{value}/128"
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return networks


def _remote_is_trusted_proxy(remote: str | None) -> bool:
    if not getattr(config, "TRUST_X_FORWARDED_FOR", False):
        return False
    if not remote:
        return False
    try:
        remote_ip = ipaddress.ip_address(str(remote).strip())
    except ValueError:
        return False
    return any(remote_ip in network for network in _trusted_proxy_networks())


def client_ip(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and _remote_is_trusted_proxy(request.remote):
        return forwarded.split(",", 1)[0].strip()
    return request.remote or "unknown"


def check_rate_limit(scope: str, key: str, *, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()
    cutoff = now - max(int(window_seconds), 1)
    bucket_key = (scope, key)
    bucket = _BUCKETS.setdefault(bucket_key, deque())
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max(int(limit), 1):
        return False
    bucket.append(now)
    return True


def rate_limited_response() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "Too many requests",
            "error_code": "RATE_LIMITED",
        },
        status=429,
    )


def reset_rate_limits() -> None:
    _BUCKETS.clear()

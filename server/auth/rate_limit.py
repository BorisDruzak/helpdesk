"""Small in-memory rate limiter for auth-sensitive public endpoints."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from aiohttp import web


@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window_seconds: int


_BUCKETS: dict[tuple[str, str], deque[float]] = {}


def client_ip(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
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

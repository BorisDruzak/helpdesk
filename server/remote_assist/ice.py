from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import config


def build_remote_assist_ice_servers(*, now: int | None = None) -> list[dict[str, Any]]:
    now = int(time.time() if now is None else now)
    servers: list[dict[str, Any]] = []
    for item in config.REMOTE_ASSIST_ICE_SERVERS:
        if not isinstance(item, dict):
            continue
        server = dict(item)
        credential_mode = str(server.pop("credential_mode", "") or "").strip().lower()
        ttl_seconds = int(server.pop("ttl_seconds", config.REMOTE_ASSIST_SIGNALING_TOKEN_TTL_SECONDS) or 0)
        if credential_mode == "time_limited_hmac":
            if not config.REMOTE_ASSIST_TURN_SHARED_SECRET:
                continue
            expiry = now + max(60, ttl_seconds)
            username = f"{expiry}:remote-assist"
            digest = hmac.new(
                config.REMOTE_ASSIST_TURN_SHARED_SECRET.encode("utf-8"),
                username.encode("utf-8"),
                hashlib.sha1,
            ).digest()
            server["username"] = username
            server["credential"] = base64.b64encode(digest).decode("ascii")
        if server.get("urls"):
            servers.append(server)
    return servers

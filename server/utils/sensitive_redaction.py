from __future__ import annotations

from typing import Any


SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "session_token",
    "token",
)


def redact_sensitive_mapping_values(
    value: Any,
    *,
    depth: int = 0,
    drop_sensitive_keys: bool = False,
) -> Any:
    if depth > 4:
        return "<redacted-depth>"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEY_PARTS):
                if not drop_sensitive_keys:
                    redacted[key_text] = "<redacted>"
                continue
            redacted[key_text] = redact_sensitive_mapping_values(
                item,
                depth=depth + 1,
                drop_sensitive_keys=drop_sensitive_keys,
            )
        return redacted
    if isinstance(value, list):
        return [
            redact_sensitive_mapping_values(
                item,
                depth=depth + 1,
                drop_sensitive_keys=drop_sensitive_keys,
            )
            for item in value[:50]
        ]
    if isinstance(value, str):
        return value[:500]
    return value

from __future__ import annotations

from typing import Any


QUALITY_PROFILES: dict[str, dict[str, int | str]] = {
    "fast": {
        "quality_profile": "fast",
        "max_width": 1024,
        "max_height": 576,
        "fps": 5,
    },
    "balanced": {
        "quality_profile": "balanced",
        "max_width": 1600,
        "max_height": 900,
        "fps": 8,
    },
    "smooth": {
        "quality_profile": "smooth",
        "max_width": 1280,
        "max_height": 720,
        "fps": 15,
    },
    "sharp": {
        "quality_profile": "sharp",
        "max_width": 1920,
        "max_height": 1080,
        "fps": 12,
    },
}

DEFAULT_QUALITY_PROFILE = "balanced"
MAX_WIDTH = 1920
MAX_HEIGHT = 1080
MAX_FPS = 15


def build_remote_assist_media_options(data: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = data or {}
    requested_profile = str(raw.get("quality_profile") or DEFAULT_QUALITY_PROFILE).strip().lower()
    profile = QUALITY_PROFILES.get(requested_profile) or QUALITY_PROFILES[DEFAULT_QUALITY_PROFILE]
    options = dict(profile)
    options["monitor_id"] = str(raw.get("monitor_id") or "primary").strip() or "primary"
    for key, maximum in (("max_width", MAX_WIDTH), ("max_height", MAX_HEIGHT), ("fps", MAX_FPS)):
        value = _optional_int(raw.get(key))
        if value is not None:
            options[key] = max(1, min(value, maximum))
    return options


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

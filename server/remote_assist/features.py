from __future__ import annotations

from typing import Any

import config


def wants_clipboard_auto_sync(options: dict[str, Any] | None) -> bool:
    raw = options if isinstance(options, dict) else {}
    return bool(raw.get("clipboard_auto_sync") or raw.get("clipboard"))


def wants_file_transfer(options: dict[str, Any] | None) -> bool:
    raw = options if isinstance(options, dict) else {}
    return bool(raw.get("file_transfer") or raw.get("file_channel"))


def build_remote_assist_features(options: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = options if isinstance(options, dict) else {}
    clipboard_requested = wants_clipboard_auto_sync(raw)
    clipboard_enabled = bool(config.REMOTE_ASSIST_CLIPBOARD_ENABLED and clipboard_requested)
    file_transfer_requested = wants_file_transfer(raw)
    file_transfer_enabled = bool(config.REMOTE_ASSIST_FILE_TRANSFER_ENABLED and file_transfer_requested)
    return {
        "clipboard_auto_sync": clipboard_enabled,
        "clipboard_max_bytes": int(config.REMOTE_ASSIST_CLIPBOARD_MAX_BYTES),
        "file_transfer": file_transfer_enabled,
        "file_transfer_max_bytes": int(config.REMOTE_ASSIST_FILE_TRANSFER_MAX_BYTES),
    }

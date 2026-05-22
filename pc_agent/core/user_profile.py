from __future__ import annotations

from dataclasses import dataclass
import getpass
import json
import os
from pathlib import Path
import re
from typing import Any

from pc_agent.core.runtime_paths import resolve_data_root


PROFILE_SCHEMA_VERSION = 1
PROFILE_FIELDS = {
    "schema_version",
    "full_name",
    "display_name",
    "login",
    "email",
    "phone",
    "department",
    "building",
    "floor",
    "room",
    "relationship_type",
    "is_shared_device",
    "last_submitted_at",
    "last_claim_id",
    "registration_status",
}


def _clean(value: Any, *, max_length: int = 300) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if "<script" in text.lower() or "</" in text.lower():
        return ""
    return text[:max_length]


@dataclass
class UserProfileManager:
    data_root: Path | None = None

    @property
    def path(self) -> Path:
        root = self.data_root or resolve_data_root()
        return root / "user_profile.json"

    def load(self) -> dict[str, Any]:
        path = self.path
        if not path.exists():
            return self.get_default_profile_from_os()
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return self.get_default_profile_from_os()
        if not isinstance(payload, dict):
            return self.get_default_profile_from_os()
        return self.sanitize(payload)

    def save(self, profile: dict[str, Any]) -> dict[str, Any]:
        sanitized = self.sanitize(profile)
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(sanitized, fh, ensure_ascii=False, indent=2, sort_keys=True)
        tmp_path.replace(path)
        return sanitized

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return

    def is_complete(self, profile: dict[str, Any]) -> bool:
        sanitized = self.sanitize(profile)
        return bool(sanitized.get("full_name") or sanitized.get("display_name")) and bool(
            sanitized.get("relationship_type")
        )

    def sanitize(self, profile: dict[str, Any] | None) -> dict[str, Any]:
        profile = profile or {}
        result: dict[str, Any] = {"schema_version": PROFILE_SCHEMA_VERSION}
        for key in PROFILE_FIELDS:
            if key == "schema_version":
                continue
            if key == "is_shared_device":
                result[key] = bool(profile.get(key))
                continue
            if key not in profile:
                continue
            limit = 80 if key == "phone" else 300
            value = _clean(profile.get(key), max_length=limit)
            if value:
                result[key] = value
        relationship = result.get("relationship_type") or "primary_user"
        if relationship not in {"primary_user", "responsible", "owner", "shared_user", "temporary_user"}:
            relationship = "primary_user"
        if result.get("is_shared_device") and relationship == "primary_user":
            relationship = "shared_user"
        result["relationship_type"] = relationship
        email = result.get("email")
        if email and ("@" not in email or len(email) > 320):
            result.pop("email", None)
        return result

    def get_default_profile_from_os(self) -> dict[str, Any]:
        login = _clean(os.environ.get("USERNAME") or os.environ.get("USER") or getpass.getuser(), max_length=160)
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "login": login,
            "display_name": login,
            "relationship_type": "primary_user",
            "is_shared_device": False,
        }

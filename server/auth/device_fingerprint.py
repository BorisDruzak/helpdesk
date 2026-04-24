from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FINGERPRINT_SCHEMA = "device_fingerprint_v1"
FINGERPRINT_METADATA_KEY = "device_fingerprint"

_COMPONENT_KEYS = (
    "system_uuid",
    "baseboard",
    "cpu",
    "boot_volume",
)


@dataclass(frozen=True)
class DeviceFingerprintVerdict:
    allowed: bool
    status: str
    matched_count: int
    mismatched_count: int
    comparable_count: int
    missing_count: int
    details: dict[str, Any]


def _clean(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def normalize_device_fingerprint(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    components_raw = raw.get("components")
    if not isinstance(components_raw, dict):
        components_raw = {}

    components: dict[str, str] = {}
    for key in _COMPONENT_KEYS:
        value = _clean(components_raw.get(key) or raw.get(key))
        if value:
            components[key] = value

    mac_hashes = sorted(
        {
            item
            for item in (_clean(value) for value in (raw.get("mac_hashes") or []))
            if item
        }
    )

    if not components and not mac_hashes:
        return None

    return {
        "schema": _clean(raw.get("schema")) or FINGERPRINT_SCHEMA,
        "components": components,
        "mac_hashes": mac_hashes,
        "summary": raw.get("summary") if isinstance(raw.get("summary"), dict) else {},
    }


def compare_device_fingerprints(
    stored: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> DeviceFingerprintVerdict:
    if not stored or not incoming:
        return DeviceFingerprintVerdict(
            allowed=True,
            status="insufficient",
            matched_count=0,
            mismatched_count=0,
            comparable_count=0,
            missing_count=0,
            details={"reason": "fingerprint_missing"},
        )

    stored_components = stored.get("components") if isinstance(stored.get("components"), dict) else {}
    incoming_components = incoming.get("components") if isinstance(incoming.get("components"), dict) else {}

    matched: list[str] = []
    mismatched: list[str] = []
    missing: list[str] = []

    for key in _COMPONENT_KEYS:
        left = _clean(stored_components.get(key))
        right = _clean(incoming_components.get(key))
        if not left or not right:
            missing.append(key)
            continue
        if left == right:
            matched.append(key)
        else:
            mismatched.append(key)

    stored_macs = set(stored.get("mac_hashes") or [])
    incoming_macs = set(incoming.get("mac_hashes") or [])
    if stored_macs and incoming_macs:
        if stored_macs.intersection(incoming_macs):
            matched.append("mac_hashes")
        else:
            mismatched.append("mac_hashes")
    else:
        missing.append("mac_hashes")

    comparable_count = len(matched) + len(mismatched)
    mismatched_count = len(mismatched)
    if comparable_count >= 4:
        allowed = mismatched_count <= 1
    elif comparable_count == 3:
        allowed = len(matched) >= 2
    elif comparable_count == 2:
        allowed = mismatched_count == 0
    else:
        allowed = True

    if comparable_count < 2:
        status = "insufficient"
    elif allowed and mismatched_count:
        status = "partial_match"
    elif allowed:
        status = "match"
    else:
        status = "mismatch"

    return DeviceFingerprintVerdict(
        allowed=allowed,
        status=status,
        matched_count=len(matched),
        mismatched_count=mismatched_count,
        comparable_count=comparable_count,
        missing_count=len(missing),
        details={
            "matched": matched,
            "mismatched": mismatched,
            "missing": missing,
        },
    )

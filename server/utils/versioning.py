"""
Shared helpers for semantic version ordering across modules and agent builds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

try:
    from packaging.version import InvalidVersion, Version as PackagingVersion
except ImportError:  # pragma: no cover - fallback stays intentionally small
    InvalidVersion = ValueError
    PackagingVersion = None


VERSION_PRERELEASE_MARKERS = ("alpha", "beta", "rc", "dev", "preview", "nightly", "canary")
_SEMVER_RE = re.compile(
    r"^\s*v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-+](?P<suffix>[0-9A-Za-z.-]+))?\s*$"
)


@dataclass(frozen=True)
class VersionOrderKey:
    valid: bool
    key: tuple
    normalized: str
    is_prerelease: bool


def version_key(version: Optional[str]) -> VersionOrderKey:
    raw = str(version or "").strip()
    lowered = raw.lower()
    if PackagingVersion is not None:
        try:
            parsed = PackagingVersion(raw)
            return VersionOrderKey(
                valid=True,
                key=(parsed,),
                normalized=str(parsed),
                is_prerelease=bool(parsed.is_prerelease or parsed.is_devrelease),
            )
        except InvalidVersion:
            pass
    match = _SEMVER_RE.match(raw)
    if match:
        suffix = match.group("suffix") or ""
        is_prerelease = bool(suffix and any(marker in suffix.lower() for marker in VERSION_PRERELEASE_MARKERS))
        suffix_key = (0, suffix.lower()) if is_prerelease else (1, "")
        return VersionOrderKey(
            valid=True,
            key=(
                int(match.group("major")),
                int(match.group("minor")),
                int(match.group("patch")),
                suffix_key,
            ),
            normalized=raw,
            is_prerelease=is_prerelease,
        )
    return VersionOrderKey(
        valid=False,
        key=(raw.lower(),),
        normalized=raw,
        is_prerelease=("-" in lowered) or any(marker in lowered for marker in VERSION_PRERELEASE_MARKERS),
    )


def compare_versions(left: Optional[str], right: Optional[str]) -> int:
    left_key = version_key(left)
    right_key = version_key(right)
    if left_key.valid and right_key.valid:
        if left_key.key == right_key.key:
            return 0
        return 1 if left_key.key > right_key.key else -1
    left_norm = left_key.normalized.lower()
    right_norm = right_key.normalized.lower()
    if left_norm == right_norm:
        return 0
    return 1 if left_norm > right_norm else -1

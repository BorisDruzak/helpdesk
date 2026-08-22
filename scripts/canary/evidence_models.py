"""Secret-free evidence validation for the Helpdesk staging canary."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


class CanaryEvidenceError(ValueError):
    """Evidence contains a secret-like or unapproved field."""


_FORBIDDEN = re.compile(
    r"(?:authorization|bearer|cookie|csrf|credential|password|private[_.-]?key|secret|token)",
    re.IGNORECASE,
)


def reject_sensitive_values(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise CanaryEvidenceError("manifest/evidence keys must be strings")
            if _FORBIDDEN.search(key):
                raise CanaryEvidenceError(f"forbidden manifest/evidence field: {key}")
            reject_sensitive_values(nested)
    elif isinstance(value, list):
        for nested in value:
            reject_sensitive_values(nested)
    elif isinstance(value, str) and (
        "-----BEGIN" in value or "bearer " in value.casefold() or "://" in value and "@" in value
    ):
        raise CanaryEvidenceError("forbidden secret-like manifest/evidence value")

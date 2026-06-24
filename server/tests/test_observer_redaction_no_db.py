from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from shared.redaction import REDACTED, redact_sensitive_payload


pytestmark = pytest.mark.no_db


class _CustomMapping(Mapping[str, object]):
    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def test_observer_redaction_handles_custom_mapping_without_mutating_input() -> None:
    custom = _CustomMapping(
        {
            "Authorization": "Bearer raw-token",
            "raw_request_body": {"password": "nested-password"},
            "safe": "kept",
        }
    )
    nested = _CustomMapping({"session_token": "nested-token"})
    payload = {
        "custom": custom,
        "items": [nested],
    }

    redacted = redact_sensitive_payload(payload, extra_markers={"raw_request_body"})

    assert redacted == {
        "custom": {
            "Authorization": REDACTED,
            "raw_request_body": REDACTED,
            "safe": "kept",
        },
        "items": [{"session_token": REDACTED}],
    }
    assert custom["Authorization"] == "Bearer raw-token"
    assert custom["raw_request_body"] == {"password": "nested-password"}
    assert nested["session_token"] == "nested-token"

from __future__ import annotations

import pytest

from tickets.statuses import (
    CANONICAL_STATUSES,
    STATUS_LABELS_RU,
    assert_canonical_status,
    normalize_status_for_input,
    requester_status_for_internal,
    requester_status_label_for_internal,
)


pytestmark = pytest.mark.no_db


EXPECTED_STATUSES = (
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
    "resolved",
    "closed",
    "canceled",
)


def test_canonical_statuses_are_exact_contract() -> None:
    assert CANONICAL_STATUSES == EXPECTED_STATUSES
    assert "triaged" not in CANONICAL_STATUSES


def test_legacy_triaged_is_boundary_alias_only() -> None:
    result = normalize_status_for_input("triaged")

    assert result["canonical_value"] == "queued"
    assert result["status"] == "queued"
    assert result["raw_value"] == "triaged"
    assert result["was_legacy"] is True

    with pytest.raises(ValueError, match="not a canonical ticket status"):
        assert_canonical_status("triaged")


def test_known_legacy_aliases_normalize_but_are_not_canonical() -> None:
    assert normalize_status_for_input("open")["canonical_value"] == "in_progress"
    assert normalize_status_for_input("cancelled")["canonical_value"] == "canceled"

    with pytest.raises(ValueError):
        assert_canonical_status("cancelled")


def test_labels_and_requester_projection_cover_every_canonical_status() -> None:
    missing_labels = [status for status in CANONICAL_STATUSES if not STATUS_LABELS_RU.get(status)]
    assert missing_labels == []

    for status in CANONICAL_STATUSES:
        requester_status = requester_status_for_internal(status)
        assert requester_status
        assert requester_status_label_for_internal(status)

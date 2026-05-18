from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_db

from change.contracts import (
    CHANGE_STATUSES,
    CHANGE_TYPES,
    can_transition_change,
    normalize_change_status,
    validate_change_approval_payload,
)


def test_change_contract_declares_core_types_and_statuses() -> None:
    assert {"standard", "normal", "emergency"}.issubset(CHANGE_TYPES)
    assert {
        "draft",
        "submitted",
        "assessing",
        "awaiting_approval",
        "approved",
        "scheduled",
        "implementation_in_progress",
        "implemented",
        "pir_required",
        "closed",
        "rejected",
        "canceled",
        "failed",
        "rolled_back",
    }.issubset(CHANGE_STATUSES)


def test_change_lifecycle_transition_matrix_blocks_shortcuts() -> None:
    assert can_transition_change("draft", "submitted") is True
    assert can_transition_change("awaiting_approval", "approved") is True
    assert can_transition_change("approved", "scheduled") is True
    assert can_transition_change("scheduled", "implementation_in_progress") is True
    assert can_transition_change("implemented", "pir_required") is True
    assert can_transition_change("pir_required", "closed") is True

    assert can_transition_change("draft", "closed") is False
    assert can_transition_change("closed", "implementation_in_progress") is False


def test_change_status_normalization_rejects_unknown_status() -> None:
    assert normalize_change_status(" Submitted ") == "submitted"
    with pytest.raises(ValueError, match="status"):
        normalize_change_status("waiting_for_magic")


def test_normal_and_emergency_changes_require_rollback_before_approval() -> None:
    with pytest.raises(ValueError, match="rollback"):
        validate_change_approval_payload(
            change_type="normal",
            emergency_justification=None,
            has_risk=True,
            has_plan=True,
            has_rollback=False,
            approvals_satisfied=True,
        )

    with pytest.raises(ValueError, match="emergency"):
        validate_change_approval_payload(
            change_type="emergency",
            emergency_justification=None,
            has_risk=True,
            has_plan=True,
            has_rollback=True,
            approvals_satisfied=True,
        )


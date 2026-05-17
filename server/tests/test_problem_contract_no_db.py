from __future__ import annotations

import pytest

from problem.contracts import (
    PROBLEM_ACTION_TYPES,
    PROBLEM_CANDIDATE_STATUSES,
    PROBLEM_DETECTION_SIGNAL_TYPES,
    PROBLEM_RCA_STATUSES,
    PROBLEM_STATUSES,
    can_transition_problem,
    validate_problem_resolution_payload,
)

pytestmark = pytest.mark.no_db


def test_problem_contract_defines_p4_lifecycle_and_signals() -> None:
    assert {
        "new",
        "candidate",
        "investigating",
        "known_error",
        "workaround_available",
        "permanent_fix_planned",
        "permanent_fix_in_progress",
        "resolved",
        "closed",
        "canceled",
    }.issubset(PROBLEM_STATUSES)
    assert {"open", "accepted", "dismissed", "merged", "converted"}.issubset(PROBLEM_CANDIDATE_STATUSES)
    assert {"draft", "in_review", "approved", "rejected", "archived"}.issubset(PROBLEM_RCA_STATUSES)
    assert {"low_csat_pattern", "reopen_pattern", "sla_breach_pattern", "failed_kb_pattern", "qa_failed_pattern"}.issubset(PROBLEM_DETECTION_SIGNAL_TYPES)
    assert {"perform_rca", "implement_permanent_fix", "validate_workaround", "update_known_error"}.issubset(PROBLEM_ACTION_TYPES)


def test_problem_transition_rules_require_human_resolution_evidence() -> None:
    assert can_transition_problem("new", "investigating") is True
    assert can_transition_problem("investigating", "known_error") is True
    assert can_transition_problem("known_error", "workaround_available") is True
    assert can_transition_problem("workaround_available", "permanent_fix_planned") is True
    assert can_transition_problem("permanent_fix_in_progress", "resolved") is True
    assert can_transition_problem("closed", "investigating") is False

    with pytest.raises(ValueError, match="root cause"):
        validate_problem_resolution_payload({"permanent_fix_summary": "Patched config"})
    with pytest.raises(ValueError, match="permanent fix"):
        validate_problem_resolution_payload({"root_cause_summary": "Vendor defect"})
    validate_problem_resolution_payload(
        {
            "root_cause_summary": "Expired routing policy",
            "permanent_fix_summary": "Published corrected policy and validated queue routing.",
        }
    )

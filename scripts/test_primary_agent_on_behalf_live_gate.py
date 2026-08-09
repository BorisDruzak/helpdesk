from __future__ import annotations

from pathlib import Path

import pytest

import scripts.primary_agent_on_behalf_live_gate as gate


pytestmark = pytest.mark.no_db


def test_default_evidence_dir_uses_short_commit_and_day() -> None:
    path = gate.default_evidence_dir(commit="abcdef1234567890", day="20260616")

    assert path == Path("artifacts/browser_live_validation/primary-agent-on-behalf-abcdef12-20260616")


def test_sanitize_for_report_redacts_secret_fields() -> None:
    payload = {
        "session_token": "secret",
        "nested": {"Authorization": "Bearer secret", "safe": "value"},
        "items": [{"password": "secret"}, {"ticket_id": "T-1"}],
    }

    assert gate.sanitize_for_report(payload) == {
        "session_token": "<redacted>",
        "nested": {"Authorization": "<redacted>", "safe": "value"},
        "items": [{"password": "<redacted>"}, {"ticket_id": "T-1"}],
    }


def test_on_behalf_form_schema_locks_release_policy() -> None:
    schema = gate.on_behalf_form_schema(
        template_code="pa_release_incident",
        version="live-test",
        playbook_key="pa_release_diag",
    )

    form = schema["forms"][0]
    assert form["on_behalf_policy"] == {
        "allowed": True,
        "reason_required": True,
        "affected_person_required": True,
        "allowed_scope": "same_department_or_privileged",
        "diagnostic_target": "affected_person_primary_agent",
        "knowledge_visibility": "creator_only",
        "support_visibility": "creator_and_affected",
        "no_primary_agent_behavior": "allow_ticket_no_diagnostics",
    }
    assert form["diagnostic_policy"]["auto_run"] == {
        "enabled": True,
        "only_if_agent_online": True,
        "only_for_priorities": ["P1", "P2"],
    }
    assert form["diagnostic_policy"]["suggested_playbooks"] == ["pa_release_diag"]


def test_required_scenarios_match_release_checklist() -> None:
    assert gate.REQUIRED_SCENARIOS == (
        "normal_ticket_targets_creator_primary_agent",
        "on_behalf_ticket_targets_affected_primary_agent",
        "affected_primary_agent_offline_skips_module_enqueue",
        "gui_login_bound_user_success",
        "gui_login_wrong_user_mismatch_no_rebind",
        "admin_transfer_device_b_to_c_future_targets",
    )

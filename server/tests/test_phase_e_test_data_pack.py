from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "test_data_packs" / "web_first_phase_e.json"


REQUIRED_USERS = {
    "admin_test",
    "support_test",
    "requester_a_completed_profile_windows_agent",
    "requester_b_completed_profile_linux_agent",
    "requester_c_incomplete_profile",
    "requester_d_no_primary_agent",
    "requester_e_same_department",
    "requester_f_restricted_department",
}

REQUIRED_AGENT_KEYS = {"lab-win-primary-agent", "lab-lin-primary-agent"}
REQUIRED_KB_SCENARIOS = {
    "public_requester_article",
    "department_restricted_article",
    "support_only_article",
    "on_behalf_help_article",
    "device_linking_help_article",
    "pc_offline_power_failure_article",
}
REQUIRED_FORM_SCENARIOS = {
    "normal_incident",
    "emergency_no_profile_no_agent",
    "on_behalf_enabled",
    "on_behalf_disabled",
    "access_request_with_approval",
    "sla_policy",
    "diagnostic_policy",
}


@pytest.mark.no_db
def test_phase_e_web_first_test_data_pack_covers_required_live_gate_inputs() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))

    assert pack["schema"] == "web_first_phase_e_test_data_pack_v1"
    assert pack["purpose"] == "pre_broad_live_testing_gate"

    users = {item["key"]: item for item in pack["users"]}
    assert REQUIRED_USERS <= set(users)
    for key, user in users.items():
        assert user["role"] in {"admin", "support", "requester"}
        assert user["credential_source"] == "environment_or_secret_store"
        assert "password" not in user
        if key.startswith("requester_"):
            assert "profile_state" in user

    agents = {item["key"]: item for item in pack["vm_agents"]}
    assert REQUIRED_AGENT_KEYS == set(agents)
    for key, agent in agents.items():
        assert agent["device_id_source"] == "live_registry"
        assert agent["unique_device_id_required"] is True
        assert agent["manual_contamination_check_required"] is True
        assert agent["bound_requester"] in users
        assert agent["primary_active_binding_required"] is True
        assert agent["module_snapshot_required"] is True

    kb_scenarios = {item["scenario"] for item in pack["knowledge"]}
    assert REQUIRED_KB_SCENARIOS <= kb_scenarios
    forms = {item["scenario"]: item for item in pack["forms"]}
    assert REQUIRED_FORM_SCENARIOS <= set(forms)
    assert forms["emergency_no_profile_no_agent"]["availability_policy"]["available_without_completed_profile"] is True
    assert forms["emergency_no_profile_no_agent"]["availability_policy"]["available_without_agent_binding"] is True
    assert forms["on_behalf_enabled"]["on_behalf_policy"]["enabled"] is True
    assert forms["on_behalf_disabled"]["on_behalf_policy"]["enabled"] is False

    matrix_keys = {item["gate"] for item in pack["validation_matrix"]}
    assert {
        "ticket_context_v1",
        "customer_history",
        "observer_web_cabinet",
        "support_detail_context",
        "requester_raw_id_guard",
        "vm_agent_cleanliness",
    } <= matrix_keys

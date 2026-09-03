from __future__ import annotations

from registry.policy_service import build_registry_policy_response
import pytest


pytestmark = pytest.mark.db_cleanup("registry_access")

def test_policy_response_defaults_to_automatic_first_binding_without_warning():
    response = build_registry_policy_response(
        {"registration": {"auto_approve_first_binding": True}}
    )

    assert response["defaults"]["registration"]["require_admin_confirmation"] is False
    assert response["defaults"]["registration"]["auto_approve_first_binding"] is True
    assert response["effective"]["registration"]["require_admin_confirmation"] is False
    assert response["effective"]["registration"]["auto_approve_first_binding"] is True
    assert "warnings" not in response["effective"]
    assert response["requires_restart"] is False
    assert response["warnings"] == []


def test_policy_response_exposes_diagnostic_target_fallback_policy():
    response = build_registry_policy_response(
        {"diagnostic_target": {"allow_single_active_binding_fallback": True}}
    )

    assert response["defaults"]["diagnostic_target"]["allow_single_active_binding_fallback"] is False
    assert response["effective"]["diagnostic_target"]["allow_single_active_binding_fallback"] is True
    assert response["changed_from_defaults"] == {
        "diagnostic_target.allow_single_active_binding_fallback": {
            "default": False,
            "effective": True,
        }
    }

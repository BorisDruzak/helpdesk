from __future__ import annotations

from registry.policy_service import build_registry_policy_response


def test_policy_response_warns_for_auto_approve_first_binding():
    response = build_registry_policy_response(
        {"registration": {"auto_approve_first_binding": True}}
    )

    assert response["effective"]["registration"]["auto_approve_first_binding"] is True
    assert "warnings" not in response["effective"]
    assert response["requires_restart"] is False
    assert response["warnings"] == [
        {
            "field": "registration.auto_approve_first_binding",
            "severity": "warning",
            "message": "Это позволит автоматически подтверждать первую регистрацию устройства. Рекомендуется только для тестового стенда.",
        }
    ]


def test_policy_response_exposes_validation_and_default_drift():
    response = build_registry_policy_response(
        {"account_sessions": {"verified_other_account_ttl_hours": 48}}
    )

    assert response["defaults"]["account_sessions"]["verified_other_account_ttl_hours"] == 24
    assert response["effective"]["account_sessions"]["verified_other_account_ttl_hours"] == 48
    assert response["changed_from_defaults"] == {
        "account_sessions.verified_other_account_ttl_hours": {
            "default": 24,
            "effective": 48,
        }
    }
    assert response["validation"]["account_sessions.verified_other_account_ttl_hours"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 8760,
        "nullable": False,
    }


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

from __future__ import annotations

import json
from types import SimpleNamespace

import scripts.registry_visibility_live_smoke as smoke


def test_sanitize_for_report_redacts_tokens_and_auth_headers() -> None:
    payload = {
        "session_token": "raw-session-token",
        "account_session_token": "raw-account-session-token",
        "headers": {"Authorization": "Bearer raw-auth-token", "Cookie": "session=raw-cookie"},
        "nested": [{"machine_token": "raw-machine-token", "safe": "kept"}],
    }

    sanitized = smoke.sanitize_for_report(payload)
    rendered = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)

    assert "raw-session-token" not in rendered
    assert "raw-account-session-token" not in rendered
    assert "raw-auth-token" not in rendered
    assert "raw-cookie" not in rendered
    assert "raw-machine-token" not in rendered
    assert sanitized["nested"][0]["safe"] == "kept"


def test_initial_report_declares_http_smoke_not_real_agent_signoff() -> None:
    report = smoke.build_initial_report(
        run_id="phase7-test",
        base_url="https://192.168.100.17:9443",
        commit="abc1234",
    )

    assert report["phase"] == "phase7_registry_visibility"
    assert report["evidence"]["http_db_smoke"]["status"] == "pending"
    assert report["evidence"]["real_agent_gui"]["status"] == "not_collected"
    assert report["scenarios"]["registered_owner"]["status"] == "pending"
    assert report["scenarios"]["verified_other_account"]["status"] == "pending"
    assert report["scenarios"]["registration_pending"]["status"] == "pending"
    assert report["scenarios"]["revoked_session"]["status"] == "pending"
    assert any("does not replace real-agent" in item for item in report["limitations"])


def test_default_output_path_uses_registry_visibility_foundation_folder() -> None:
    output = smoke.default_output_path(run_id="phase7-test", today="20260614")

    assert output.as_posix().endswith(
        "artifacts/registry-visibility-foundation-20260614/registry-visibility-live-smoke-phase7-test.json"
    )


def test_person_id_from_effective_identity_uses_nested_person_contract() -> None:
    identity = SimpleNamespace(person={"person_id": "person-1"})

    assert smoke.person_id_from_effective_identity(identity) == "person-1"

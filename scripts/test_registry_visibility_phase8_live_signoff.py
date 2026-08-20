from __future__ import annotations

import json

import pytest

import scripts.registry_visibility_phase8_live_signoff as signoff


def test_phase8_default_output_path_uses_registry_visibility_foundation_folder() -> None:
    output = signoff.default_output_path(run_id="phase8-test", today="20260614")

    assert output.as_posix().endswith(
        "artifacts/registry-visibility-foundation-20260614/registry-visibility-phase8-live-signoff-phase8-test.json"
    )


def test_phase8_initial_report_declares_browser_quality_tab_as_separate_evidence() -> None:
    report = signoff.build_initial_report(
        run_id="phase8-test",
        base_url="https://example.test:9443",
        commit="abc1234",
    )

    assert report["phase"] == "phase8_registry_operability"
    assert report["checks"]["quality_before"]["status"] == "pending"
    assert report["checks"]["import_preview_apply"]["status"] == "pending"
    assert report["evidence"]["browser_quality_tab"]["status"] == "not_collected"
    assert report["evidence"]["browser_quality_tab"]["required"] is True


def test_phase8_csv_sample_keeps_header_and_matching_rows() -> None:
    csv_text = "code,name\nalpha,Alpha\nphase8_empty_1,=Formula\nbeta,Beta\n"

    sample = signoff._csv_sample(csv_text, marker="phase8_empty_1")

    assert sample == ["code,name", "alpha,Alpha", "phase8_empty_1,=Formula"]


def test_phase8_secret_audit_rejects_raw_authorization_markers() -> None:
    with pytest.raises(signoff.SmokeFailure):
        signoff._assert_no_raw_secret({"headers": {"Authorization": "Bearer raw"}})


def test_phase8_secret_audit_accepts_sanitized_report() -> None:
    report = signoff.sanitize_for_report({
        "checks": {"quality_before": {"status": "passed"}},
        "created": {"audience_group_id": "group-1"},
    })
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert "Bearer raw" not in rendered
    signoff._assert_no_raw_secret(report)

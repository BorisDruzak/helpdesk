from __future__ import annotations

import json

import pytest

from scripts import helpdesk_data_cleanup as cleanup


def test_detect_text_issues_flags_mojibake_and_placeholders() -> None:
    assert cleanup.detect_text_issues("Переход должен быть заблокирован по роли.") == []
    assert cleanup.detect_text_issues("1161327d-e873-4ded-bd48-a38b98209722") == []

    mojibake_issues = cleanup.detect_text_issues(
        "РџРµСЂРµС…РѕРґ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ."
    )
    assert "mojibake" in mojibake_issues

    placeholder_issues = cleanup.detect_text_issues("???")
    assert "placeholder" in placeholder_issues


def test_collect_findings_keeps_valid_utf8_and_reports_redacted_samples() -> None:
    rows = [
        cleanup.ScanRow(
            table="tickets",
            row_key="ticket_id=t-1",
            fields={
                "title": "Не открывается сайт",
                "custom_fields.user_display_name": "token abcdef1234567890abcdef1234567890abcdef1234567890",
                "description": "РќРµ РѕС‚РєСЂС‹РІР°РµС‚СЃСЏ СЃР°Р№С‚",
            },
        )
    ]

    findings = cleanup.collect_findings(rows)

    assert len(findings) == 2
    assert {finding.field_path for finding in findings} == {
        "description",
        "custom_fields.user_display_name",
    }
    token_finding = next(f for f in findings if f.field_path == "custom_fields.user_display_name")
    assert "[REDACTED_TOKEN]" in token_finding.sample
    assert "abcdef1234567890abcdef1234567890" not in token_finding.sample


def test_render_json_preserves_russian_text() -> None:
    report = cleanup.build_report(
        [
            cleanup.DataFinding(
                table="tickets",
                row_key="ticket_id=t-1",
                field_path="title",
                issue_codes=["mojibake"],
                sample="Не открывается сайт",
                cleanup_strategy="manual_review_required",
            )
        ],
        scanned_rows={"tickets": 1},
        dry_run=True,
    )

    rendered = cleanup.render_json(report)
    assert "Не открывается сайт" in rendered
    assert "\\u041d" not in rendered
    assert json.loads(rendered)["mode"] == "dry_run"


def test_extract_nested_description_fields_from_module_and_tool_json() -> None:
    fields = cleanup.extract_json_text_fields(
        {
            "description": "Диагностика сайта",
            "tools": [
                {
                    "tool": "dns.resolve",
                    "description": "Resolve DNS",
                    "params_schema": [{"name": "target", "description": "???"}],
                }
            ],
        },
        root_path="manifest_json",
        interesting_keys={"description", "label", "title", "name"},
    )

    assert fields["manifest_json.description"] == "Диагностика сайта"
    assert fields["manifest_json.tools[0].description"] == "Resolve DNS"
    assert fields["manifest_json.tools[0].params_schema[0].description"] == "???"


@pytest.mark.parametrize(
    "apply, expected",
    [
        (False, "dry_run"),
        (True, "apply_requested_but_not_implemented"),
    ],
)
def test_mode_is_explicitly_safe_until_cleanup_rules_are_implemented(apply: bool, expected: str) -> None:
    assert cleanup.compute_mode(apply=apply) == expected

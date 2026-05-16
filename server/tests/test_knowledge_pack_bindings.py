from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validate_knowledge_pack_bindings import (
    ValidationIssue,
    build_catalog_baseline,
    validate_pack_file,
    validate_pack_payload,
)


PACK_DIR = Path("content_packs/knowledge")


def test_all_baseline_content_pack_bindings_match_service_catalog_defaults() -> None:
    baseline = build_catalog_baseline()
    issues: list[ValidationIssue] = []
    for path in sorted(PACK_DIR.glob("*.yaml")):
        issues.extend(validate_pack_file(path, baseline=baseline, strict=True))

    assert [issue.as_dict() for issue in issues if issue.severity == "error"] == []


def test_validator_detects_invalid_service_code() -> None:
    pack = {
        "code": "invalid-service",
        "version": 1,
        "items": [{"slug": "bad", "bindings": [{"service_code": "communications"}]}],
    }

    issues = validate_pack_payload(pack, baseline=build_catalog_baseline(), source="inline", strict=True)

    assert any(issue.code == "unknown_service_code" and issue.slug == "bad" for issue in issues)


def test_validator_detects_invalid_offering_code() -> None:
    pack = {
        "code": "invalid-offering",
        "version": 1,
        "items": [{"slug": "bad", "bindings": [{"service_code": "access", "offering_code": "access.password_reset"}]}],
    }

    issues = validate_pack_payload(pack, baseline=build_catalog_baseline(), source="inline", strict=True)

    assert any(issue.code == "unknown_offering_code" and issue.slug == "bad" for issue in issues)


def test_validator_detects_mismatched_request_template_key() -> None:
    pack = {
        "code": "invalid-template",
        "version": 1,
        "items": [
            {
                "slug": "bad",
                "bindings": [
                    {
                        "service_code": "workplace",
                        "offering_code": "workplace.laptop_broken",
                        "request_template_key": "laptop_issue",
                    }
                ],
            }
        ],
    }

    issues = validate_pack_payload(pack, baseline=build_catalog_baseline(), source="inline", strict=True)

    assert any(issue.code == "template_mismatch" and issue.slug == "bad" for issue in issues)


def test_validator_accepts_canonical_fallback_binding() -> None:
    pack = {
        "code": "fallback",
        "version": 1,
        "items": [
            {
                "slug": "fallback-help",
                "bindings": [
                    {
                        "service_code": "other",
                        "offering_code": "other.unknown",
                        "request_template_key": "general_request",
                    }
                ],
            }
        ],
    }

    issues = validate_pack_payload(pack, baseline=build_catalog_baseline(), source="inline", strict=True)

    assert [issue.as_dict() for issue in issues if issue.severity == "error"] == []


@pytest.mark.parametrize("obsolete", ["communications.mail_issue", "password_reset", "laptop_issue", "other_unknown"])
def test_baseline_files_do_not_contain_obsolete_binding_keys(obsolete: str) -> None:
    joined = "\n".join(path.read_text(encoding="utf-8") for path in PACK_DIR.glob("*.yaml"))

    assert obsolete not in joined


def test_known_errors_and_glossary_have_no_structured_offering_bindings() -> None:
    for pack_code in ("known-errors-baseline", "glossary-baseline"):
        payload = yaml.safe_load((PACK_DIR / f"{pack_code}.yaml").read_text(encoding="utf-8"))
        assert all(not item.get("bindings") for item in payload["items"])

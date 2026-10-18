import json

import pytest

pytestmark = pytest.mark.no_db


def test_readiness_separates_feature_blockers_from_attention_and_optional_devices():
    from registry.scenario_readiness_service import summarize_readiness, registry_issue_projection
    missing_device = registry_issue_projection({"kind": "asset_missing_confirmed_user", "object_type": "asset", "object_id": "private-device", "description": "private@example.test", "title": "private phone 12345"})
    missing_department = registry_issue_projection({"kind": "person_missing_department", "object_type": "person", "object_id": "p"})
    manager = {"dimension": "managers", "impact": "blocks_function", "affected_function": "manager_approval", "title": "Для услуги невозможно определить руководителя", "object_id": "p", "issue_key": "manager_unavailable:person:p"}
    report = summarize_readiness([missing_device, missing_department, manager])
    assert report["counts"] == {"blocks_function": 1, "attention": 1, "information": 1}
    assert missing_device["impact"] == "information"
    assert "private@example.test" not in json.dumps(missing_device)
    exported = json.dumps(report["export"])
    assert "private-device" not in exported
    assert "object_id" not in exported
    assert "issue_key" not in exported
    assert len(report["dimensions"]) == 9


def test_readiness_keeps_existing_issue_keys_and_exceptions():
    from registry.scenario_readiness_service import registry_issue_projection, summarize_readiness
    issue = registry_issue_projection({"kind": "binding_stale", "object_type": "binding", "object_id": "b", "issue_key": "binding_stale:binding:b", "issue_state": "snoozed"})
    assert issue["issue_key"] == "binding_stale:binding:b"
    assert issue["issue_state"] == "snoozed"
    assert summarize_readiness([issue])["counts"] == {"blocks_function": 0, "attention": 0, "information": 0}

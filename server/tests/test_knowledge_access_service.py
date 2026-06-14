from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.access_service import KnowledgeAccessService
from registry.audience_contracts import EffectiveAudience


pytestmark = pytest.mark.no_db


def _audience(*, department_id: str, role: str = "requester") -> EffectiveAudience:
    return EffectiveAudience(
        person_id="person-1",
        actor_id="requester@example.test",
        actor_role=role,
        department_path=[{"department_id": department_id, "code": department_id}],
        access_groups=["it_requesters"],
        audience_groups=["it_staff"],
    )


def _item(*, visibility: str = "requester") -> dict:
    return {
        "item_id": "item-it",
        "space_id": "space-it",
        "status": "published",
        "visibility": visibility,
        "current_version_id": "version-it",
    }


def _space() -> dict:
    return {"space_id": "space-it", "lifecycle_status": "active", "visibility": "requester"}


def test_requester_can_read_item_when_department_rule_matches() -> None:
    decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=_audience(department_id="it"),
        rules=[
            {
                "rule_id": "rule-it",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department",
                "target_id": "it",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert decision.allowed is True
    assert decision.reason_code == "audience_rule_matched"
    assert decision.matched_rule_ids == ["rule-it"]


def test_requester_cannot_infer_item_when_department_rule_does_not_match() -> None:
    decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=_audience(department_id="finance"),
        rules=[
            {
                "rule_id": "rule-it",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department",
                "target_id": "it",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert decision.allowed is False
    assert decision.reason_code == "audience_rule_not_matched"
    assert decision.matched_rule_ids == []
    assert "rule-it" not in str(decision.safe_denial_payload())


def test_audience_rule_does_not_make_support_internal_item_requester_visible() -> None:
    decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(visibility="support_internal"),
        space={**_space(), "visibility": "support_internal"},
        audience=_audience(department_id="it"),
        rules=[
            {
                "rule_id": "rule-it",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department",
                "target_id": "it",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert decision.allowed is False
    assert decision.reason_code == "coarse_visibility_denied"
    assert decision.matched_rule_ids == []


def test_filter_authorized_items_removes_hidden_projection_candidates() -> None:
    visible = {**_item(), "item_id": "item-it", "title": "IT visible article"}
    hidden = {**_item(), "item_id": "item-finance", "title": "Finance hidden article"}

    filtered = KnowledgeAccessService.filter_authorized_items(
        items=[visible, hidden],
        spaces_by_id={"space-it": _space()},
        audience=_audience(department_id="it"),
        rules=[
            {
                "rule_id": "rule-finance",
                "subject_type": "item",
                "subject_id": "item-finance",
                "target_type": "department",
                "target_id": "finance",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert [item["item_id"] for item in filtered] == ["item-it"]
    assert "Finance hidden article" not in str(filtered)


def test_knowledge_audience_rules_migration_declares_table_contract() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "20260614_121_knowledge_audience_rules.py"
    )

    text = migration.read_text(encoding="utf-8")

    assert 'revision: str = "121"' in text
    assert 'down_revision: Union[str, None] = "120"' in text
    assert '"knowledge_audience_rules"' in text
    assert "ck_knowledge_audience_rules_subject_type" in text
    assert "ck_knowledge_audience_rules_target_type" in text
    assert "ix_knowledge_audience_rules_subject" in text

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.access_service import KnowledgeAccessService
from registry.audience_contracts import EffectiveAudience


pytestmark = pytest.mark.no_db


def _audience(
    *,
    department_id: str,
    role: str = "requester",
    department_path: list[dict[str, str]] | None = None,
    audience_groups: list[object] | None = None,
) -> EffectiveAudience:
    return EffectiveAudience(
        person_id="person-1",
        actor_id="requester@example.test",
        actor_role=role,
        department_path=department_path or [{"department_id": department_id, "code": department_id}],
        access_groups=["it_requesters"],
        audience_groups=audience_groups if audience_groups is not None else ["it_staff"],
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


def test_department_rule_matches_only_current_department_not_parent_path() -> None:
    audience = _audience(
        department_id="child",
        department_path=[
            {"department_id": "parent", "code": "parent"},
            {"department_id": "child", "code": "child"},
        ],
    )

    parent_decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=audience,
        rules=[
            {
                "rule_id": "rule-parent",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department",
                "target_id": "parent",
                "effect": "allow",
                "status": "active",
            }
        ],
    )
    child_decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=audience,
        rules=[
            {
                "rule_id": "rule-child",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department",
                "target_id": "child",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert parent_decision.allowed is False
    assert parent_decision.reason_code == "audience_rule_not_matched"
    assert child_decision.allowed is True
    assert child_decision.matched_rule_ids == ["rule-child"]


def test_department_tree_rule_matches_parent_path() -> None:
    decision = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=_audience(
            department_id="child",
            department_path=[
                {"department_id": "parent", "code": "parent"},
                {"department_id": "child", "code": "child"},
            ],
        ),
        rules=[
            {
                "rule_id": "rule-parent-tree",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "department_tree",
                "target_id": "parent",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert decision.allowed is True
    assert decision.matched_rule_ids == ["rule-parent-tree"]


def test_audience_group_rule_matches_resolved_id_and_code_payloads() -> None:
    audience = _audience(
        department_id="it",
        audience_groups=[{"audience_group_id": "group-it", "code": "it_staff"}],
    )

    by_id = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=audience,
        rules=[
            {
                "rule_id": "rule-group-id",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "audience_group",
                "target_id": "group-it",
                "effect": "allow",
                "status": "active",
            }
        ],
    )
    by_code = KnowledgeAccessService.evaluate_item_access(
        item=_item(),
        space=_space(),
        audience=audience,
        rules=[
            {
                "rule_id": "rule-group-code",
                "subject_type": "item",
                "subject_id": "item-it",
                "target_type": "audience_group",
                "target_id": "it_staff",
                "effect": "allow",
                "status": "active",
            }
        ],
    )

    assert by_id.allowed is True
    assert by_id.matched_rule_ids == ["rule-group-id"]
    assert by_code.allowed is True
    assert by_code.matched_rule_ids == ["rule-group-code"]


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

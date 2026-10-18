from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from registry.organization_trust import confirm_fields

pytestmark = pytest.mark.no_db


def test_assigned_decision_is_not_granted_to_all_ordinary_users():
    from access_control.catalog import get_role_permission_codes
    assert "approval.decide.assigned" not in get_role_permission_codes("user")


def test_department_fallback_policy_requires_an_explicit_boolean():
    from app.repos.helpdesk_policy_repo import _validate_approval_source
    with pytest.raises(ValueError):
        _validate_approval_source({"type": "requester_manager", "allow_department_fallback": "true"}, field_name="approver_source")


@pytest.mark.asyncio
@pytest.mark.parametrize("case,expected", [
    ("person", "available"), ("department", "available"), ("department_disabled", "missing_manager"),
    ("unconfirmed", "unconfirmed_manager"), ("inactive", "inactive_manager"),
    ("ambiguous", "ambiguous_manager_identity"), ("unlinked", "missing_manager_identity"),
    ("permission", "manager_permission_missing"), ("stale", "unconfirmed_department"),
])
async def test_manager_resolution_is_source_aware_and_unambiguous(monkeypatch, case, expected):
    from registry import manager_resolution as module
    requester = SimpleNamespace(person_id="requester", department_id="dept", metadata_json={})
    manager = SimpleNamespace(person_id="manager", status="inactive" if case == "inactive" else "active", metadata_json={})
    department = SimpleNamespace(department_id="dept", status="active", metadata_json={"manager_person_id": "manager"})
    user = SimpleNamespace(user_login="manager@example.test", actor_role="user", is_active=True)
    confirm_fields(requester, ["department_id"], actor_id="admin")
    confirm_fields(department, ["manager_person_id"], actor_id="admin")
    if case not in {"department", "department_disabled", "stale"}:
        requester.metadata_json = {**requester.metadata_json, "manager_person_id": "manager"}
        if case != "unconfirmed":
            confirm_fields(requester, ["manager_person_id"], actor_id="admin")
    if case == "stale":
        requester.department_id = "changed"
    identities = [user.user_login, "second@example.test"] if case == "ambiguous" else [] if case == "unlinked" else [user.user_login]
    objects = {"manager": manager, "dept": department, user.user_login: user}
    session = SimpleNamespace(get=AsyncMock(side_effect=lambda model, key: objects.get(key)), scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: identities)))
    monkeypatch.setattr(module, "can", AsyncMock(return_value=case != "permission"))
    resolution = await module.resolve_person_manager(session, requester, allow_department_fallback=case != "department_disabled")
    assert resolution["status"] == expected
    assert resolution.get("actor_id") == (user.user_login if expected == "available" else None)

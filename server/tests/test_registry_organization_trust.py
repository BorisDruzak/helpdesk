from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_db


def person(**extra):
    return SimpleNamespace(person_id="p", department_id="old", location_id="l", metadata_json={}, **extra)


def test_verified_login_or_active_status_does_not_confirm_organization():
    from registry.organization_trust import field_trust, organization_value
    row = person(status="active")
    assert field_trust(row, "department_id")["state"] == "legacy_unknown"
    assert organization_value(row, "department_id", allow_legacy=True) == "old"
    assert organization_value(row, "department_id", allow_legacy=False) is None


def test_confirmed_department_proposal_keeps_authority_until_review():
    from registry.organization_trust import confirm_fields, propose_fields, decide_proposal, organization_value
    row = person()
    confirm_fields(row, ["department_id", "location_id"], actor_id="admin")
    proposal = propose_fields(row, {"department_id": "new"}, actor_id="employee")["department_id"]
    assert row.department_id == "old"
    assert organization_value(row, "department_id", allow_legacy=False) == "old"
    decide_proposal(row, "department_id", proposal["proposal_id"], approve=True, actor_id="admin")
    assert row.department_id == "new"
    assert organization_value(row, "department_id", allow_legacy=False) == "new"
    with pytest.raises(ValueError):
        decide_proposal(row, "department_id", proposal["proposal_id"], approve=True, actor_id="admin")


def test_legacy_edit_preserves_access_baseline_without_marking_confirmed():
    from registry.organization_trust import propose_fields, field_trust, organization_value, decide_proposal
    row = person()
    proposal = propose_fields(row, {"department_id": "new"}, actor_id="employee")["department_id"]
    assert row.department_id == "old"
    assert field_trust(row, "department_id")["state"] == "legacy_unknown"
    assert organization_value(row, "department_id", allow_legacy=True) == "old"
    decide_proposal(row, "department_id", proposal["proposal_id"], approve=False, actor_id="admin")
    assert row.department_id == "old"


def test_new_self_reported_context_never_grants_department_access():
    from registry.organization_trust import propose_fields, organization_value, field_trust
    row = SimpleNamespace(person_id="p", department_id=None, location_id=None, metadata_json={})
    assert propose_fields(row, {"department_id": "new", "location_id": "l"}, actor_id="employee") == {}
    assert row.department_id == "new"
    assert field_trust(row, "department_id")["state"] == "self_reported"
    assert organization_value(row, "department_id", allow_legacy=True) is None


def test_stale_confirmed_metadata_cannot_authorize_a_different_department():
    from registry.organization_trust import confirm_fields, organization_value
    row = person()
    confirm_fields(row, ["department_id"], actor_id="admin")
    row.department_id = "changed-outside-reviewed-flow"
    assert organization_value(row, "department_id", allow_legacy=True) is None


def test_unknown_provenance_version_does_not_fall_back_to_legacy_access():
    from registry.organization_trust import organization_value
    row = person()
    row.metadata_json = {"organization_context_v1": {"version": 99, "fields": {}}}
    assert organization_value(row, "department_id", allow_legacy=True) is None


@pytest.mark.asyncio
async def test_unrelated_policy_update_preserves_explicit_strict_mode():
    from unittest.mock import AsyncMock
    from registry.policy_service import RegistryPolicyService
    row = SimpleNamespace(config_json={"organizational_trust": {"strict_legacy_audiences": True}})
    service = RegistryPolicyService(SimpleNamespace(get=AsyncMock(return_value=row), flush=AsyncMock()))
    assert (await service.update_policies({"registration": {"stale_after_days": 30}}))["organizational_trust"]["strict_legacy_audiences"] is True
    assert (await service.update_policies({"organizational_trust": {}}))["organizational_trust"]["strict_legacy_audiences"] is True
    assert (await service.reset_to_defaults())["organizational_trust"]["strict_legacy_audiences"] is False

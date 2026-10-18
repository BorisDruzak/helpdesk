"""Portable document creation keeps bindings canonical and preview read-only."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError
from tests.test_request_scenario_unified import source

pytestmark = pytest.mark.no_db
CREATION_KEY = "cfbc826d-cf71-449b-b3cf-66c16a861c20"


def portable():
    raw = source()
    for key in ("scenario_key", "service_code", "offering_full_code"):
        raw.pop(key)
    raw.pop("process_binding")
    return raw


def setup_repo(monkeypatch):
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), execute=AsyncMock(), add=Mock(),
        get=AsyncMock(return_value=None), scalars=AsyncMock(), flush=AsyncMock(), commit=AsyncMock())
    repo = RequestScenarioRepo(session, SimpleNamespace(actor_id="admin", actor_role="admin"))
    repo.catalog.get_service_by_code = AsyncMock(return_value={"code": "selected", "metadata": {"studio_default_template": "bridge"}, "default_ticket_type_code": "incident"})
    repo.catalog.list_offerings = AsyncMock(return_value=[])
    repo.catalog.upsert_offering_draft = AsyncMock()
    effective = {"request_template": {"template_code": "bridge", "ticket_type": "incident", "published_at": "2026-10-18", "is_active": True},
        "resolved_policies": {"closure": {"require_resolution_code": True}}, "policy_refs": {}}
    resolver = AsyncMock(return_value=effective)
    monkeypatch.setattr(HelpdeskPolicyRepo, "resolve_effective_request_template", resolver)
    return repo, session, effective


def payload(raw=None, *, format="json", **extra):
    raw = portable() if raw is None else raw
    content = json.dumps(raw, ensure_ascii=False) if format == "json" else yaml.safe_dump(raw, allow_unicode=True)
    return SimpleNamespace(content=content, format=format, service_code="selected", category_id=None, creation_key=CREATION_KEY, **extra)


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["json", "yaml"])
async def test_portable_preview_resolves_new_binding_without_any_dml(monkeypatch, format):
    repo, session, _ = setup_repo(monkeypatch)
    result = await repo.preview_service_document(payload(format=format))
    definition = result["definition"]
    assert result["creation_key"] == CREATION_KEY and len(result["source_hash"]) == 64
    assert definition["scenario_key"] == "scenario_import_" + CREATION_KEY.replace("-", "")
    assert definition["service_code"] == "selected"
    assert definition["offering_full_code"].startswith("selected.map_")
    assert definition["process_binding"]["request_template_key"] == "bridge"
    assert definition["blocks"] and result["issues"] == []
    session.execute.assert_not_awaited()
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()
    repo.catalog.upsert_offering_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_exported_foreign_identity_is_explicitly_rebound_and_source_untouched(monkeypatch):
    repo, _, _ = setup_repo(monkeypatch)
    raw = source()
    raw["category_id"] = "11111111-1111-1111-1111-111111111111"
    raw["entry_points"][0]["category_id"] = "22222222-2222-2222-2222-222222222222"
    before = deepcopy(raw)
    result = await repo.preview_service_document(payload(raw))
    assert result["definition"]["scenario_key"] != raw["scenario_key"]
    assert result["definition"]["category_id"] is None
    assert result["definition"]["entry_points"][0]["category_id"] is None
    assert result["definition"]["entry_points"][0]["target_block_id"] == raw["entry_points"][0]["target_block_id"]
    assert raw == before


@pytest.mark.asyncio
async def test_preview_hash_tracks_effective_defaults_without_changing_document(monkeypatch):
    repo, _, effective = setup_repo(monkeypatch)
    first = await repo.preview_service_document(payload())
    effective["resolved_policies"]["closure"]["require_resolution_code"] = False
    second = await repo.preview_service_document(payload())
    assert first["definition"] == second["definition"]
    assert first["source_hash"] != second["source_hash"]
    with pytest.raises(ScenarioAdminError) as error:
        await repo.create_service_document(payload(source_hash=first["source_hash"]))
    assert error.value.code == "IMPORT_PREVIEW_CHANGED" and error.value.status == 409


@pytest.mark.asyncio
async def test_invalid_graph_returns_paths_without_preview_writes(monkeypatch):
    repo, session, _ = setup_repo(monkeypatch)
    raw = portable()
    raw["blocks"][0]["transitions"][0]["to"] = "missing"
    result = await repo.preview_service_document(payload(raw))
    assert any(issue["code"] == "unknown_target" and issue["path"].startswith("blocks.questions") for issue in result["issues"])
    session.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("other_ref", [None, "priority", "approval"])
async def test_v3_document_uses_canonical_map_owned_policy_filter(monkeypatch, other_ref):
    repo, _, _ = setup_repo(monkeypatch)
    raw = portable()
    refs = {"routing": "missing_legacy_route", "sla": "inactive_legacy_sla"}
    if other_ref:
        refs[other_ref] = "missing_non_map_policy"
    raw.update(schema_version=3, process_binding={"policy_refs": refs}, processing={
        "routes": {"support": {"title": "Support", "queue_code": "support"}},
        "sla_profiles": {"standard": {"title": "Standard", "first_response_minutes": 30, "resolution_minutes": 120}},
        "defaults": {"route": "support", "sla_profile": "standard"}})
    monkeypatch.setattr("tickets.request_scenario_document.document_reference_issues", AsyncMock(return_value=[]))

    async def unavailable_references(session, validated, references):
        if references:
            raise ValueError("unavailable canonical policy")
        return validated

    resolver = AsyncMock(side_effect=unavailable_references)
    monkeypatch.setattr("tickets.request_scenario_processing.apply_scenario_policy_refs", resolver)
    result = await repo.preview_service_document(payload(raw))
    assert result["definition"]["process_binding"]["policy_refs"] == refs
    expected = {other_ref: "missing_non_map_policy"} if other_ref else {}
    assert resolver.await_args.args[2] == expected
    assert [issue["code"] for issue in result["issues"]] == (["policy_reference_unavailable"] if other_ref else [])


@pytest.mark.parametrize("format,content", [("json", '{"title":"A","title":"B"}'), ("yaml", "title: A\ntitle: B"),
    ("yaml", "x: &x [1]\ny: *x"), ("yaml", "!!python/object/apply:os.system [whoami]")])
def test_shared_raw_parser_keeps_duplicate_and_unsafe_yaml_guards(format, content):
    from tickets.request_scenario_document import parse_scenario_document_raw
    with pytest.raises(ValueError):
        parse_scenario_document_raw(content, format)

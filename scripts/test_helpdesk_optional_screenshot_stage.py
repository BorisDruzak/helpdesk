from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import json

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "server"))


def catalog():
    raw = json.loads((Path(__file__).parents[1] / "server/tests/fixtures/phase1_other_base.json").read_text(encoding="utf-8"))
    for block in raw["blocks"]:
        for edge in block.get("transitions", []):
            if edge["to"] == "submit":
                edge["to"] = "q_evidence"
    raw["blocks"].append({"id": "q_evidence", "kind": "form_page", "title": "Скриншот или фото ошибки", "fields": [
        {"key": "evidence_note", "type": "textarea", "label": "Скриншот подготовлен или почему его невозможно приложить?", "required": True},
        {"key": "evidence_caption", "type": "textarea", "label": "Что видно на снимке или что происходит вместо видимой ошибки?", "required": False}],
        "transitions": [{"to": "submit"}]})
    return {
        "request_studio_scenarios": [{"id": "map", "scenario_key": "legacy", "service_code": "other", "title": "Other",
            "enabled": True, "archived": False, "published_version_id": "old"}],
        "request_studio_drafts": [{"scenario_id": "map", "revision": 4, "base_version_id": "old", "definition": deepcopy(raw)}],
        "request_studio_scenario_versions": [{"id": "old", "scenario_id": "map", "state": "published", "definition": raw}],
    }


def test_plan_removes_only_stage_and_never_mutates_catalog():
    from scripts.helpdesk_optional_screenshot_stage import build_plan
    snapshot = catalog()
    before = deepcopy(snapshot)
    plan = build_plan(snapshot)
    assert plan["applied"] is False and plan["active_count"] == 1
    assert plan["changed_count"] == 1 and plan["scenarios"][0]["rewired_transitions"] == 3
    assert plan["scenarios"][0]["revision"] == 4
    assert all(block["id"] != "q_evidence" for block in plan["scenarios"][0]["definition"]["blocks"])
    assert len(plan["scenarios"][0]["definition"]["blocks"]) == len(before["request_studio_drafts"][0]["definition"]["blocks"]) - 1
    assert snapshot == before


@pytest.mark.parametrize("change", ["draft", "base_version", "missing_version", "version_state", "foreign_version", "lookalike"])
def test_plan_aborts_on_user_draft_or_publication_drift(change):
    from scripts.helpdesk_optional_screenshot_stage import build_plan
    snapshot = catalog()
    if change == "draft": snapshot["request_studio_drafts"][0]["definition"]["title"] = "User work"
    if change == "base_version": snapshot["request_studio_drafts"][0]["base_version_id"] = "other"
    if change == "missing_version": snapshot["request_studio_scenario_versions"] = []
    if change == "version_state": snapshot["request_studio_scenario_versions"][0]["state"] = "revoked"
    if change == "foreign_version": snapshot["request_studio_scenario_versions"][0]["scenario_id"] = "other"
    if change == "lookalike":
        for row in (snapshot["request_studio_drafts"][0], snapshot["request_studio_scenario_versions"][0]):
            row["definition"]["blocks"][-1]["fields"][0]["process_mapping"] = {"roles": ["closure_evidence"]}
    with pytest.raises(ValueError):
        build_plan(snapshot)


def test_plan_is_idempotent_after_canonical_publication_and_preserves_inactive_drafts():
    from scripts.helpdesk_optional_screenshot_stage import build_plan
    snapshot = catalog()
    wanted = build_plan(snapshot)["scenarios"][0]["definition"]
    snapshot["request_studio_drafts"][0]["definition"] = deepcopy(wanted)
    snapshot["request_studio_scenario_versions"][0]["definition"] = deepcopy(wanted)
    snapshot["request_studio_scenarios"].append({"id": "disabled", "enabled": False, "archived": False})
    snapshot["request_studio_drafts"].append({"scenario_id": "disabled", "definition": {"title": "Unsaved work"}})
    assert build_plan(snapshot)["changed_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", [SimpleNamespace(is_admin=lambda: False, actor_id="user"), SimpleNamespace(is_admin=lambda: True, actor_id=None)])
async def test_publication_rejects_untrusted_actor_before_opening_database(actor):
    from scripts.helpdesk_optional_screenshot_stage import publish_optional_screenshot_stage
    def forbidden():
        raise AssertionError("Must not open database")
    with pytest.raises(ValueError, match="admin"):
        await publish_optional_screenshot_stage(forbidden, actor, apply=True)


def publication_boundary(monkeypatch, *, fail_second=False, database="helpdesk_staging_db"):
    """Replace only the external transaction/repository boundary; execute helper."""
    from contextlib import asynccontextmanager
    import scripts.helpdesk_optional_screenshot_stage as module
    snapshot = catalog()
    if fail_second:
        row = {**deepcopy(snapshot["request_studio_scenarios"][0]), "id": "map2", "published_version_id": "old2"}
        snapshot["request_studio_scenarios"].append(row)
        snapshot["request_studio_drafts"].append({**deepcopy(snapshot["request_studio_drafts"][0]), "scenario_id": "map2", "base_version_id": "old2"})
        snapshot["request_studio_scenario_versions"].append({**deepcopy(snapshot["request_studio_scenario_versions"][0]), "id": "old2", "scenario_id": "map2"})
    state = {"snapshot": snapshot}
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        @asynccontextmanager
        async def begin(self):
            before = deepcopy(state["snapshot"])
            try: yield
            except Exception:
                state["snapshot"] = before
                raise
        async def scalar(self, statement): return database
        async def execute(self, statement): pass
        async def scalars(self, statement):
            return SimpleNamespace(all=lambda: ["other"])
    async def read_catalog(session): return deepcopy(state["snapshot"])
    class Repo:
        def __init__(self, session, auth): pass
        async def _service_lock(self, code): pass
        async def save(self, identifier, payload):
            draft = next(row for row in state["snapshot"]["request_studio_drafts"] if row["scenario_id"] == identifier)
            if draft["revision"] != payload.revision:
                raise ValueError("CAS conflict")
            draft["revision"] += 1
            draft["definition"] = payload.definition.model_dump(mode="json")
            return {"draft": deepcopy(draft)}
    class Publisher:
        def __init__(self, repo): pass
        async def _freeze_sources(self, **kwargs): pass
        async def preview(self, identifier, revision):
            return {"readiness": {"can_publish": not (fail_second and identifier == "map2")}, "confirmation_token": "test-private-confirmation"}
        async def publish(self, identifier, payload):
            data = state["snapshot"]
            scenario = next(row for row in data["request_studio_scenarios"] if row["id"] == identifier)
            draft = next(row for row in data["request_studio_drafts"] if row["scenario_id"] == identifier)
            current = next(row for row in data["request_studio_scenario_versions"] if row["id"] == scenario["published_version_id"])
            current["state"] = "retired"
            version = {"id": "new-" + identifier, "scenario_id": identifier, "state": "published", "definition": deepcopy(draft["definition"])}
            data["request_studio_scenario_versions"].append(version)
            scenario["published_version_id"] = draft["base_version_id"] = version["id"]
            return {"version": version}
    monkeypatch.setattr(module, "read_catalog", read_catalog)
    monkeypatch.setattr("app.repos.request_scenario_repo.RequestScenarioRepo", Repo)
    monkeypatch.setattr("tickets.request_scenario_publication.ScenarioPublicationService", Publisher)
    return module, Session, state


ADMIN = SimpleNamespace(is_admin=lambda: True, actor_id="admin")


@pytest.mark.asyncio
async def test_apply_uses_fresh_fingerprint_and_repeated_apply_creates_no_version(monkeypatch):
    module, factory, state = publication_boundary(monkeypatch)
    plan = await module.publish_optional_screenshot_stage(factory, ADMIN)
    result = await module.publish_optional_screenshot_stage(factory, ADMIN, apply=True, expected_fingerprint=plan["fingerprint"])
    assert result["changed_count"] == 1 and result["scenarios"][0]["previous_version_id"] == "old"
    assert result["scenarios"][0]["version_id"] == "new-map"
    assert "confirmation_token" not in result
    plan = await module.publish_optional_screenshot_stage(factory, ADMIN)
    again = await module.publish_optional_screenshot_stage(factory, ADMIN, apply=True, expected_fingerprint=plan["fingerprint"])
    assert again["changed_count"] == 0 and len(state["snapshot"]["request_studio_scenario_versions"]) == 2
    assert state["snapshot"]["request_studio_scenario_versions"][0]["definition"]["blocks"][-1]["id"] == "q_evidence"


@pytest.mark.asyncio
async def test_apply_aborts_and_rolls_back_earlier_map_on_late_readiness_failure(monkeypatch):
    module, factory, state = publication_boundary(monkeypatch, fail_second=True)
    before = deepcopy(state["snapshot"])
    plan = await module.publish_optional_screenshot_stage(factory, ADMIN)
    with pytest.raises(ValueError, match="readiness"):
        await module.publish_optional_screenshot_stage(factory, ADMIN, apply=True, expected_fingerprint=plan["fingerprint"])
    assert state["snapshot"] == before


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing_fingerprint", "source_drift", "wrong_database"])
async def test_apply_guard_failure_preserves_every_map(monkeypatch, change):
    module, factory, state = publication_boundary(monkeypatch, database="production" if change == "wrong_database" else "helpdesk_staging_db")
    from scripts.helpdesk_phase1_catalog import fingerprint
    expected = fingerprint(state["snapshot"])
    if change == "source_drift": state["snapshot"]["policies"] = [{"version": "new"}]
    if change == "missing_fingerprint": expected = None
    before = deepcopy(state["snapshot"])
    with pytest.raises(ValueError):
        await module.publish_optional_screenshot_stage(factory, ADMIN, apply=True, expected_fingerprint=expected)
    assert state["snapshot"] == before

"""Plan/apply removal of the reviewed screenshot stage via audited Studio APIs.

No CLI or credentials. The release wrapper owns host/backup guards and supplies
a trusted admin context. Plan performs SELECTs only. Apply uses one transaction
for all CAS draft saves, readiness checks, tokens and canonical publications.
Existing session state, uploads and immutable version definitions are untouched.
"""
from sqlalchemy import select, text

from scripts.helpdesk_phase1_catalog import fingerprint, read_catalog, require_target
from tickets.request_scenario_optional_evidence import EVIDENCE_BLOCK, without_evidence_stage


def build_plan(snapshot):
    """Reject diverged user drafts before preparing any batch mutation."""
    versions = {row["id"]: row for row in snapshot["request_studio_scenario_versions"]}
    drafts = {row["scenario_id"]: row for row in snapshot["request_studio_drafts"]}
    active = sorted((row for row in snapshot["request_studio_scenarios"] if row["enabled"] and not row["archived"]), key=lambda row: row["id"])
    if not active:
        raise ValueError("No active published maps; explicit review is required")
    scenarios = []
    for row in active:
        version = versions.get(row.get("published_version_id"))
        draft = drafts.get(row["id"])
        if not version or version["scenario_id"] != row["id"] or version["state"] != "published":
            raise ValueError("An active map has no matching published version")
        if not draft or draft.get("base_version_id") != version["id"] or draft["definition"] != version["definition"]:
            raise ValueError("An active map has a diverged user draft; preserve and review it")
        definition = without_evidence_stage(version["definition"])
        scenarios.append({"scenario_id": row["id"], "scenario_key": row["scenario_key"], "title": row["title"],
            "revision": draft["revision"], "version_id": version["id"], "changed": definition != version["definition"],
            "rewired_transitions": sum(edge.get("to") == EVIDENCE_BLOCK for block in version["definition"]["blocks"] for edge in block.get("transitions", [])),
            "definition": definition})
    return {"applied": False, "fingerprint": fingerprint(snapshot), "active_count": len(scenarios),
        "changed_count": sum(item["changed"] for item in scenarios), "scenarios": scenarios}


async def publish_optional_screenshot_stage(session_factory, auth, *, apply=False, expected_fingerprint=None):
    from app.db.request_scenario_models import RequestStudioScenario
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from tickets.request_scenario_publication import ScenarioPublicationService
    from web_api.dto.request_scenario_admin import ScenarioSave, ScenarioPublish

    if not auth.is_admin() or not auth.actor_id:
        raise ValueError("A trusted authenticated admin context is required")
    async with session_factory() as session:
        async with session.begin():
            require_target(await session.scalar(text("SELECT current_database()")))
            locked_codes = set()
            if apply:
                await session.execute(text("SELECT pg_advisory_xact_lock(20261106, 12)"))
                locked_codes = set((await session.scalars(select(RequestStudioScenario.service_code).where(
                    RequestStudioScenario.enabled.is_(True), RequestStudioScenario.archived.is_(False)))).all())
                repo = RequestScenarioRepo(session, auth)
                for code in sorted(locked_codes):
                    await repo._service_lock(code)
                # Canonical service-before-source-before-scenario lock order.
                await ScenarioPublicationService(repo)._freeze_sources(write_offering=True)
                await session.execute(text("LOCK TABLE request_studio_scenarios, request_studio_drafts, request_studio_scenario_versions IN SHARE ROW EXCLUSIVE MODE"))
            snapshot = await read_catalog(session)
            plan = build_plan(snapshot)
            if not apply:
                return plan
            if not expected_fingerprint or plan["fingerprint"] != expected_fingerprint:
                raise ValueError("Publication inputs changed; obtain and review a fresh plan")
            current_codes = {row["service_code"] for row in snapshot["request_studio_scenarios"] if row["enabled"] and not row["archived"]}
            if not current_codes.issubset(locked_codes):
                raise ValueError("Active service bindings changed while locking; obtain a fresh plan")
            publisher = ScenarioPublicationService(repo)
            published = []
            for item in plan["scenarios"]:
                result = {key: item[key] for key in ("scenario_id", "scenario_key", "version_id", "changed", "rewired_transitions")}
                if item["changed"]:
                    saved = await repo.save(item["scenario_id"], ScenarioSave.model_validate({
                        "revision": item["revision"], "definition": item["definition"]}))
                    revision = saved["draft"]["revision"]
                    preview = await publisher.preview(item["scenario_id"], revision)
                    if not preview["readiness"]["can_publish"]:
                        raise ValueError("Map failed canonical publication readiness: " + item["scenario_key"])
                    current = await publisher.publish(item["scenario_id"], ScenarioPublish(
                        revision=revision, confirm=True, confirmation_token=preview["confirmation_token"]))
                    result["previous_version_id"] = item["version_id"]
                    result["version_id"] = current["version"]["id"]
                published.append(result)
            after = build_plan(await read_catalog(session))
            if after["changed_count"] or after["active_count"] != plan["active_count"]:
                raise ValueError("Published batch did not retain all active maps without screenshot stages")
            return {"applied": True, "before_fingerprint": plan["fingerprint"], "after_fingerprint": after["fingerprint"],
                "active_count": after["active_count"], "changed_count": plan["changed_count"], "scenarios": published}

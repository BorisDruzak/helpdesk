"""Server-owned Studio files, independent of scalar answers and ticket creation."""
from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import select

from app.db.request_scenario_models import RequestStudioAsset, RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion
from tickets.request_scenario_conditions import evaluate_condition


def safe_asset_name(value):
    name = str(value or "file").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(" .")[:255]
    return name or "file"


def asset_metadata(row):
    return {"asset_id": row.id, "name": row.name, "mime_type": row.mime_type,
            "size_bytes": row.size_bytes, "url": f"/api/web/request-scenario-assets/{row.id}/download"}


def material_references(definition):
    raw = definition.model_dump(mode="json") if hasattr(definition, "model_dump") else definition
    for block in raw.get("blocks", []):
        yield from (block.get("content") or {}).get("attachments", [])
        for field in block.get("fields", []):
            yield from field.get("help_attachments", [])


async def validate_material_references(session, scenario_id, definition):
    from app.repos.request_scenario_repo import ScenarioAdminError
    for ref in material_references(definition):
        row = await session.get(RequestStudioAsset, ref["asset_id"])
        if not row or not scenario_id or row.scenario_id != scenario_id or row.removed_at or asset_metadata(row) != ref:
            raise ScenarioAdminError("ATTACHMENT_REFERENCE_INVALID")


async def copy_material_sources(session, source_id, definition):
    """An explicit admin copy can reuse only material actually in its source."""
    from app.repos.request_scenario_repo import ScenarioAdminError
    source = await session.get(RequestStudioScenario, source_id)
    draft = await session.get(RequestStudioDraft, source_id)
    if not source or not draft:
        raise ScenarioAdminError("COPY_SOURCE_NOT_FOUND", 404)
    source_refs = {item["asset_id"] for item in material_references(draft.definition)}
    versions = (await session.scalars(select(RequestStudioScenarioVersion).where(
        RequestStudioScenarioVersion.scenario_id == source_id, RequestStudioScenarioVersion.state != "revoked"))).all()
    source_refs.update(item["asset_id"] for version in versions for item in material_references(version.definition))
    await validate_material_references(session, source_id, definition)
    result = {}
    for item in material_references(definition):
        if item["asset_id"] not in source_refs:
            raise ScenarioAdminError("ATTACHMENT_REFERENCE_INVALID")
        result[item["asset_id"]] = await session.get(RequestStudioAsset, item["asset_id"])
    return result


async def material_content_definition(session, scenario_id, definition):
    """Compare immutable contents and placement, independent of copied ids."""
    await validate_material_references(session, scenario_id, definition)
    raw = deepcopy(definition)
    indices = {}
    for ref in material_references(raw):
        asset_id = ref["asset_id"]
        index = indices.setdefault(asset_id, len(indices))
        row = await session.get(RequestStudioAsset, asset_id)
        ref.clear()
        ref.update(name=row.name, mime_type=row.mime_type, size_bytes=row.size_bytes, sha256=row.sha256, material_index=index)
    return raw


async def clone_material_assets(session, target_id, definition, sources, owner):
    raw, rebindings = deepcopy(definition), {}
    for ref in material_references(raw):
        source_id = ref["asset_id"]
        if source_id not in rebindings:
            source = sources[source_id]
            clone = RequestStudioAsset(scenario_id=target_id, owner_actor_id=owner,
                storage_path=source.storage_path, name=source.name, mime_type=source.mime_type,
                size_bytes=source.size_bytes, sha256=source.sha256)
            session.add(clone)
            await session.flush()
            rebindings[source_id] = asset_metadata(clone)
        ref.clear()
        ref.update(rebindings[source_id])
    return raw, rebindings


def retained_attachment_fields(runtime, state, *, include_current=False):
    identifiers = list(state.history) + ([state.current_block_id] if include_current else [])
    return {(block_id, field.key) for block_id in identifiers if block_id in runtime.blocks
            for field in getattr(runtime.blocks[block_id], "fields", ())
            if field.type in {"text", "textarea"} and evaluate_condition(field.visible_when, state.answers)}


async def session_assets(session, session_id):
    return list((await session.scalars(select(RequestStudioAsset).where(
        RequestStudioAsset.session_id == session_id, RequestStudioAsset.removed_at.is_(None),
    ).order_by(RequestStudioAsset.created_at, RequestStudioAsset.id))).all())


async def project_answer_assets(session, row_id, runtime, state, projection):
    rows = await session_assets(session, row_id)
    allowed = retained_attachment_fields(runtime, state, include_current=True)
    by_field = {}
    for row in rows:
        if (row.block_id, row.field_key) in allowed:
            metadata = asset_metadata(row)
            if row.artifact_id:
                metadata["url"] = f"/api/artifacts/{row.artifact_id}/download"
            by_field.setdefault(row.field_key, []).append(metadata)
    block = projection["block"]
    for item in block.get("fields", []) + block.get("answers", []):
        item["answer_attachments"] = by_field.get(item["key"], [])
    # Optional text with only a file must still appear on review; scalar value
    # remains absent and is never manufactured for validation or policy input.
    if block["kind"] in {"review", "submit_ticket"}:
        seen = {item["key"] for item in block["answers"]}
        for identifier in state.history:
            for field in getattr(runtime.blocks[identifier], "fields", ()):
                if field.key not in seen and field.key in by_field:
                    block["answers"].append({"key": field.key, "label": field.label, "type": field.type,
                        "value": None, "display_value": "", "answer_attachments": by_field[field.key]})
    return projection


async def prune_answer_assets(session, row_id, runtime, state):
    allowed = retained_attachment_fields(runtime, state, include_current=True)
    for row in await session_assets(session, row_id):
        if not row.artifact_id and (row.block_id, row.field_key) not in allowed:
            row.removed_at = datetime.now(timezone.utc)


async def claim_answer_assets(session, row, runtime, ticket_id):
    """Claim only retained visible fields, inside the ticket transaction."""
    from app.db.models import Artifact, Ticket, TicketEvent
    from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo
    from tickets.handlers import _artifact_type
    state = RequestScenarioSessionRepo._state(row)
    allowed = retained_attachment_fields(runtime, state)
    attachments, associations = [], []
    for asset in await session_assets(session, row.id):
        if (asset.block_id, asset.field_key) not in allowed:
            asset.removed_at = datetime.now(timezone.utc)
            continue
        if not asset.artifact_id:
            asset.artifact_id = str(uuid.uuid4())
            session.add(Artifact(artifact_id=asset.artifact_id, storage_path=asset.storage_path,
                original_name=asset.name, mime_type=asset.mime_type, size_bytes=asset.size_bytes,
                sha256=asset.sha256, kind="screenshot" if asset.mime_type.startswith("image/") else "file",
                ticket_id=ticket_id, device_id=None))
            await session.flush()
        descriptor = {"artifact_id": asset.artifact_id, "name": asset.name, "mime_type": asset.mime_type,
                      "size_bytes": asset.size_bytes, "url": f"/api/artifacts/{asset.artifact_id}/download",
                      "kind": "screenshot" if asset.mime_type.startswith("image/") else "file",
                      "type": _artifact_type(asset.mime_type, "screenshot" if asset.mime_type.startswith("image/") else "file")}
        attachments.append(descriptor)
        associations.append({"block_id": asset.block_id, "field_key": asset.field_key, **descriptor})
    if not attachments:
        return
    ticket = await session.get(Ticket, ticket_id)
    context = deepcopy(ticket.custom_fields or {})
    scenario_context = context.setdefault("request_scenario", {})
    scenario_context["answer_attachments"] = associations
    for item in scenario_context.get("summary", []):
        if "answer_attachments" in item:
            item["answer_attachments"] = [deepcopy(ref) for ref in associations if ref["field_key"] == item["key"]]
    ticket.custom_fields = context
    event = await session.scalar(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id,
        TicketEvent.event_type == "chat_message", TicketEvent.payload["is_initial"].as_boolean().is_(True)
    ).order_by(TicketEvent.id).limit(1))
    if event is None:
        raise ValueError("Initial ticket message is required for attachments")
    event.payload = {**event.payload, "attachments": attachments,
                     "attachment_refs": [item["artifact_id"] for item in attachments]}

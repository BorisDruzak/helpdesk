from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBinding


CANONICAL_BINDING_SURFACES = {
    "requester_pre_submit",
    "requester_after_submit",
    "support_ticket_workspace",
    "support_command_center",
    "agent",
    "ai_rag",
}

SURFACE_ALIASES = {
    "requester_portal": "requester_pre_submit",
    "requester_pre_submit": "requester_pre_submit",
    "request_form": "requester_pre_submit",
    "requester_form": "requester_pre_submit",
    "help_portal": "requester_pre_submit",
    "requester_after_submit": "requester_after_submit",
    "requester_ticket": "requester_after_submit",
    "requester_ticket_detail": "requester_after_submit",
    "support_workspace": "support_ticket_workspace",
    "support_ticket_workspace": "support_ticket_workspace",
    "ticket_workspace": "support_ticket_workspace",
    "support_command_center": "support_command_center",
    "command_center": "support_command_center",
    "agent_gui": "agent",
    "agent": "agent",
    "knowledge_ask": "ai_rag",
    "admin_knowledge_ask": "ai_rag",
    "admin_ask_preview": "ai_rag",
    "admin_knowledge_retrieve": "ai_rag",
    "knowledge_retrieve": "ai_rag",
    "retrieve": "ai_rag",
    "rag": "ai_rag",
    "ai_rag": "ai_rag",
    "eval_suite": "ai_rag",
}


def binding_surface_for_request(surface: Any) -> str | None:
    value = str(surface or "").strip().lower()
    if not value:
        return None
    return SURFACE_ALIASES.get(value)


def normalize_binding_surfaces(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        surface = SURFACE_ALIASES.get(str(item or "").strip().lower())
        if surface and surface not in seen:
            normalized.append(surface)
            seen.add(surface)
    return normalized


def binding_metadata_surfaces(metadata: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    return normalize_binding_surfaces(metadata.get("surfaces"))


def binding_allows_surface(metadata: Any, request_surface: Any) -> bool:
    canonical = binding_surface_for_request(request_surface)
    if canonical is None:
        return True
    surfaces = binding_metadata_surfaces(metadata)
    return not surfaces or canonical in surfaces


async def allowed_item_ids_for_binding_surface(
    session: AsyncSession,
    item_ids: list[str] | set[str] | tuple[str, ...],
    *,
    surface: Any,
) -> set[str]:
    ids = {str(item_id) for item_id in item_ids if item_id}
    if not ids:
        return set()
    canonical = binding_surface_for_request(surface)
    if canonical is None:
        return ids

    rows = (
        await session.execute(
            select(KnowledgeBinding.item_id, KnowledgeBinding.metadata_json).where(KnowledgeBinding.item_id.in_(sorted(ids)))
        )
    ).all()
    if not rows:
        return ids

    state: dict[str, dict[str, bool]] = {
        item_id: {"has_binding": False, "allows_surface": False}
        for item_id in ids
    }
    for item_id, metadata in rows:
        item_state = state.setdefault(str(item_id), {"has_binding": False, "allows_surface": False})
        item_state["has_binding"] = True
        surfaces = binding_metadata_surfaces(metadata)
        if not surfaces or canonical in surfaces:
            item_state["allows_surface"] = True

    return {
        item_id
        for item_id, item_state in state.items()
        if not item_state["has_binding"] or item_state["allows_surface"]
    }

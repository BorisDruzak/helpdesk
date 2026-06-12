from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRuntimeAudit, KnowledgeAiProposal
from knowledge.contracts import actor_visible_visibilities
from knowledge.graph_service import KnowledgeGraphService


PROPOSAL_TYPES = {"summary", "tags", "glossary_term", "graph_node", "graph_edge", "duplicate"}
TARGET_KINDS = {"item", "version", "graph", "space", "import_job"}
STATUSES = {"pending", "approved", "rejected", "archived"}
REDACT_KEYS = {
    "source_ticket_id",
    "source_passport_id",
    "requester_id",
    "device_id",
    "custom_fields",
    "raw_chunks",
    "metadata_json",
    "trace_id",
    "operation_id",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _clean_text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None:
        text = text[:max_length]
    return text


def _confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("confidence_score must be a number") from None
    if not math.isfinite(number) or number < 0 or number > 1:
        raise ValueError("confidence_score must be between 0 and 1")
    return round(number, 4)


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if key_text in REDACT_KEYS or any(marker in lowered for marker in ("token", "secret", "password", "cookie", "authorization")):
                continue
            cleaned[key_text] = _sanitize_payload(child)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value[:200]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def serialize_ai_proposal(row: KnowledgeAiProposal) -> dict[str, Any]:
    return {
        "proposal_id": row.proposal_id,
        "proposal_type": row.proposal_type,
        "target_kind": row.target_kind,
        "target_ref": row.target_ref,
        "title": row.title,
        "rationale": row.rationale,
        "proposed_payload": row.proposed_payload_json or {},
        "status": row.status,
        "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
        "visibility": row.visibility,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "applied_refs": row.applied_refs_json or {},
        "review_note": row.review_note,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


class KnowledgeAiProposalService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        proposal_type = _clean_text(payload.get("proposal_type"), max_length=40) or ""
        target_kind = _clean_text(payload.get("target_kind"), max_length=40) or ""
        target_ref = _clean_text(payload.get("target_ref"), max_length=500) or ""
        title = _clean_text(payload.get("title"), max_length=500) or ""
        if proposal_type not in PROPOSAL_TYPES:
            raise ValueError("unsupported proposal_type")
        if target_kind not in TARGET_KINDS:
            raise ValueError("unsupported target_kind")
        if not target_ref:
            raise ValueError("target_ref is required")
        if not title:
            raise ValueError("title is required")
        row = KnowledgeAiProposal(
            proposal_id=_new_id(),
            proposal_type=proposal_type,
            target_kind=target_kind,
            target_ref=target_ref,
            title=title,
            rationale=_clean_text(payload.get("rationale"), max_length=4000),
            proposed_payload_json=_sanitize_payload(payload.get("proposed_payload") or {}),
            confidence_score=_confidence(payload.get("confidence_score")),
            visibility=_clean_text(payload.get("visibility"), max_length=40) or "support_internal",
            source_kind=_clean_text(payload.get("source_kind"), max_length=60),
            source_ref=_clean_text(payload.get("source_ref"), max_length=1000),
            created_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        await self._audit("knowledge.ai_proposal.created", row, actor_id=actor_id, actor_role=actor_role)
        return serialize_ai_proposal(row)

    async def list(self, *, actor_role: str, status: str | None = None, target_kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        allowed = set(actor_visible_visibilities(actor_role))
        stmt = select(KnowledgeAiProposal).where(KnowledgeAiProposal.visibility.in_(allowed))
        if status:
            if status not in STATUSES:
                raise ValueError("unsupported status")
            stmt = stmt.where(KnowledgeAiProposal.status == status)
        if target_kind:
            if target_kind not in TARGET_KINDS:
                raise ValueError("unsupported target_kind")
            stmt = stmt.where(KnowledgeAiProposal.target_kind == target_kind)
        stmt = stmt.order_by(KnowledgeAiProposal.created_at.desc()).limit(max(1, min(limit, 200)))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [serialize_ai_proposal(row) for row in rows]

    async def review(self, proposal_id: str, payload: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any] | None:
        row = await self.session.get(KnowledgeAiProposal, proposal_id)
        if row is None:
            return None
        action = _clean_text(payload.get("action"), max_length=30) or ""
        note = _clean_text(payload.get("note"), max_length=4000)
        if action not in {"approve", "reject", "comment"}:
            raise ValueError("unsupported action")
        row.review_note = note or row.review_note
        row.reviewed_by = actor_id
        row.reviewed_at = datetime.now(timezone.utc)
        event_type = "knowledge.ai_proposal.commented"
        if action == "approve":
            row.applied_refs_json = await self._apply(row, actor_id=actor_id)
            row.status = "approved"
            event_type = "knowledge.ai_proposal.approved"
        elif action == "reject":
            row.status = "rejected"
            event_type = "knowledge.ai_proposal.rejected"
        await self.session.flush()
        await self._audit(event_type, row, actor_id=actor_id, actor_role=actor_role)
        return serialize_ai_proposal(row)

    async def _apply(self, row: KnowledgeAiProposal, *, actor_id: str | None) -> dict[str, Any]:
        if row.proposal_type not in {"graph_node", "graph_edge"}:
            return {}
        graph_payload = (row.proposed_payload_json or {}).get("graph")
        if not isinstance(graph_payload, dict):
            return {}
        graph = KnowledgeGraphService(self.session)
        node_ids: list[str] = []
        for node_payload in graph_payload.get("nodes") or []:
            if not isinstance(node_payload, dict):
                continue
            node = await graph.upsert_node(
                stable_key=str(node_payload.get("stable_key") or ""),
                node_type=str(node_payload.get("node_type") or "concept"),
                label=str(node_payload.get("label") or node_payload.get("stable_key") or ""),
                visibility=str(node_payload.get("visibility") or row.visibility),
                linked_item_id=node_payload.get("linked_item_id"),
                service_code=node_payload.get("service_code"),
                offering_code=node_payload.get("offering_code"),
                actor_id=actor_id,
            )
            node_ids.append(node.node_id)
        edge_ids: list[str] = []
        for edge_payload in graph_payload.get("edges") or []:
            if not isinstance(edge_payload, dict):
                continue
            source = await graph.get_node(str(edge_payload.get("source_stable_key") or ""), actor_role="admin")
            target = await graph.get_node(str(edge_payload.get("target_stable_key") or ""), actor_role="admin")
            if source is None or target is None:
                raise ValueError("proposal graph edge references missing nodes")
            edge = await graph.create_edge(
                source,
                target,
                relation_type=str(edge_payload.get("relation_type") or "mentions"),
                visibility=str(edge_payload.get("visibility") or row.visibility),
                actor_id=actor_id,
            )
            edge_ids.append(edge.edge_id)
        return {"node_ids": node_ids, "edge_ids": edge_ids}

    async def _audit(self, event_type: str, row: KnowledgeAiProposal, *, actor_id: str | None, actor_role: str) -> None:
        self.session.add(
            AgentRuntimeAudit(
                device_id="server",
                event_type=event_type,
                severity="info",
                source="knowledge_ai_proposals",
                actor_id=actor_id,
                actor_role=actor_role,
                details_json={
                    "proposal_id": row.proposal_id,
                    "proposal_type": row.proposal_type,
                    "target_kind": row.target_kind,
                    "target_ref": row.target_ref,
                    "status": row.status,
                },
            )
        )
        await self.session.flush()

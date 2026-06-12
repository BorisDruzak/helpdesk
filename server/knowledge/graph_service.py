from __future__ import annotations

from collections import deque
import math
from typing import Any
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import KnowledgeEdge, KnowledgeGraphLayout, KnowledgeItem, KnowledgeNode
from knowledge.contracts import actor_visible_visibilities


NODE_TYPES = {
    "knowledge_item",
    "article",
    "known_error",
    "workaround",
    "glossary_term",
    "service",
    "offering",
    "ticket",
    "asset",
    "registry_service",
    "diagnostic_playbook",
    "external_entity",
    "concept",
    "document",
}
NODE_STATUSES = {"proposed", "confirmed", "rejected", "archived"}
EDGE_STATUSES = {"proposed", "confirmed", "rejected", "archived"}
EDGE_RELATION_TYPES = {
    "explains",
    "causes",
    "caused_by",
    "depends_on",
    "affects",
    "affected_by",
    "has_workaround",
    "has_permanent_fix",
    "requires",
    "replaces",
    "duplicates",
    "similar_to",
    "belongs_to_service",
    "belongs_to_offering",
    "suggested_for",
    "tried_in_ticket",
    "resolved_by",
    "source_of",
    "mentions",
    "synonym_of",
    "contradicts",
    "supersedes",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _serialize_node(row: KnowledgeNode) -> dict[str, Any]:
    return {
        "node_id": row.node_id,
        "node_type": row.node_type,
        "stable_key": row.stable_key,
        "label": row.label,
        "description": row.description,
        "visibility": row.visibility,
        "linked_item_id": row.linked_item_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "status": row.status,
    }


def _serialize_edge(row: KnowledgeEdge) -> dict[str, Any]:
    weight = float(row.weight) if row.weight is not None else 1
    if weight.is_integer():
        weight = int(weight)
    return {
        "edge_id": row.edge_id,
        "source_node_id": row.source_node_id,
        "target_node_id": row.target_node_id,
        "relation_type": row.relation_type,
        "weight": weight,
        "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
        "visibility": row.visibility,
        "status": row.status,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
    }


def _serialize_layout(row: KnowledgeGraphLayout | None, *, scope_type: str, scope_ref: str) -> dict[str, Any]:
    if row is None:
        return {
            "layout_id": None,
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "layout_json": {},
            "created_at": None,
            "updated_at": None,
        }
    return {
        "layout_id": row.layout_id,
        "scope_type": row.scope_type,
        "scope_ref": row.scope_ref,
        "layout_json": row.layout_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _safe_number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    rounded = round(float(value), 3)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _sanitize_layout_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, Any] = {}
    raw_nodes = value.get("nodes")
    if isinstance(raw_nodes, dict):
        nodes: dict[str, dict[str, float | int]] = {}
        for stable_key, position in list(raw_nodes.items())[:500]:
            if not isinstance(stable_key, str) or len(stable_key) > 240 or not isinstance(position, dict):
                continue
            x = _safe_number(position.get("x"))
            y = _safe_number(position.get("y"))
            if x is None or y is None:
                continue
            nodes[stable_key] = {"x": x, "y": y}
        sanitized["nodes"] = nodes
    raw_viewport = value.get("viewport")
    if isinstance(raw_viewport, dict):
        viewport: dict[str, float | int] = {}
        for key in ("zoom", "pan_x", "pan_y"):
            number = _safe_number(raw_viewport.get(key))
            if number is not None:
                viewport[key] = number
        sanitized["viewport"] = viewport
    return sanitized


def _clean_text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None:
        text = text[:max_length]
    return text


def _safe_weight(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("weight must be a number") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError("weight must be non-negative")
    return round(number, 3)


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def serialize_node(self, row: KnowledgeNode) -> dict[str, Any]:
        return _serialize_node(row)

    def serialize_edge(self, row: KnowledgeEdge) -> dict[str, Any]:
        return _serialize_edge(row)

    async def upsert_node(
        self,
        *,
        stable_key: str,
        node_type: str,
        label: str,
        visibility: str,
        linked_item_id: str | None = None,
        service_code: str | None = None,
        offering_code: str | None = None,
        actor_id: str | None = None,
    ) -> KnowledgeNode:
        row = (
            await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == stable_key))
        ).scalar_one_or_none()
        if row is None:
            if not stable_key:
                raise ValueError("stable_key is required")
            if node_type not in NODE_TYPES:
                raise ValueError("unsupported node_type")
            row = KnowledgeNode(
                node_id=_new_id(),
                stable_key=stable_key,
                node_type=node_type,
                label=label,
                visibility=visibility,
                linked_item_id=linked_item_id,
                service_code=service_code,
                offering_code=offering_code,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.session.add(row)
        else:
            row.label = label or row.label
            row.visibility = visibility or row.visibility
            row.updated_by = actor_id
        await self.session.flush()
        return row

    async def list_nodes(self, *, actor_role: str, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        allowed = set(actor_visible_visibilities(actor_role))
        stmt = (
            select(KnowledgeNode)
            .where(KnowledgeNode.visibility.in_(allowed), KnowledgeNode.status != "archived")
            .order_by(KnowledgeNode.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        query = _clean_text(q, max_length=120)
        if query:
            needle = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(KnowledgeNode.stable_key).like(needle),
                    func.lower(KnowledgeNode.label).like(needle),
                    func.lower(KnowledgeNode.node_type).like(needle),
                    func.lower(KnowledgeNode.visibility).like(needle),
                    func.lower(func.coalesce(KnowledgeNode.service_code, "")).like(needle),
                    func.lower(func.coalesce(KnowledgeNode.offering_code, "")).like(needle),
                )
            )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_serialize_node(row) for row in rows]

    async def get_node(self, node_ref: str, *, actor_role: str) -> KnowledgeNode | None:
        allowed = set(actor_visible_visibilities(actor_role))
        return (
            await self.session.execute(
                select(KnowledgeNode).where(
                    (KnowledgeNode.node_id == node_ref) | (KnowledgeNode.stable_key == node_ref),
                    KnowledgeNode.visibility.in_(allowed),
                )
            )
        ).scalar_one_or_none()

    async def update_node(
        self,
        node_ref: str,
        payload: dict[str, Any],
        *,
        actor_role: str,
        actor_id: str | None = None,
    ) -> dict[str, Any] | None:
        row = await self.get_node(node_ref, actor_role=actor_role)
        if row is None:
            return None
        if "label" in payload:
            label = _clean_text(payload.get("label"), max_length=500)
            if not label:
                raise ValueError("label is required")
            row.label = label
        if "description" in payload:
            row.description = _clean_text(payload.get("description"), max_length=4000)
        if "node_type" in payload:
            node_type = _clean_text(payload.get("node_type"), max_length=40) or ""
            if node_type not in NODE_TYPES:
                raise ValueError("unsupported node_type")
            row.node_type = node_type
        if "visibility" in payload:
            visibility = _clean_text(payload.get("visibility"), max_length=40) or ""
            row.visibility = visibility
        if "status" in payload:
            status = _clean_text(payload.get("status"), max_length=30) or ""
            if status not in NODE_STATUSES:
                raise ValueError("unsupported status")
            row.status = status
        for field in ("linked_item_id", "service_code", "offering_code"):
            if field in payload:
                setattr(row, field, _clean_text(payload.get(field), max_length=240))
        row.updated_by = actor_id
        await self.session.flush()
        return _serialize_node(row)

    async def archive_node(self, node_ref: str, *, actor_role: str, actor_id: str | None = None) -> dict[str, Any] | None:
        row = await self.get_node(node_ref, actor_role=actor_role)
        if row is None:
            return None
        row.status = "archived"
        row.updated_by = actor_id
        connected_edges = (
            await self.session.execute(
                select(KnowledgeEdge).where(
                    (KnowledgeEdge.source_node_id == row.node_id) | (KnowledgeEdge.target_node_id == row.node_id),
                    KnowledgeEdge.status != "archived",
                )
            )
        ).scalars().all()
        for edge in connected_edges:
            edge.status = "archived"
            edge.updated_by = actor_id
        await self.session.flush()
        return _serialize_node(row)

    async def create_edge(
        self,
        source: KnowledgeNode,
        target: KnowledgeNode,
        *,
        relation_type: str,
        visibility: str,
        actor_id: str | None = None,
    ) -> KnowledgeEdge:
        existing = (
            await self.session.execute(
                select(KnowledgeEdge).where(
                    KnowledgeEdge.source_node_id == source.node_id,
                    KnowledgeEdge.target_node_id == target.node_id,
                    KnowledgeEdge.relation_type == relation_type,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        if relation_type not in EDGE_RELATION_TYPES:
            raise ValueError("unsupported relation_type")
        row = KnowledgeEdge(
            edge_id=_new_id(),
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            relation_type=relation_type,
            visibility=visibility,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_edges(self, *, actor_role: str, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        allowed = set(actor_visible_visibilities(actor_role))
        source_node = aliased(KnowledgeNode)
        target_node = aliased(KnowledgeNode)
        stmt = (
            select(KnowledgeEdge)
            .join(source_node, KnowledgeEdge.source_node_id == source_node.node_id)
            .join(target_node, KnowledgeEdge.target_node_id == target_node.node_id)
            .where(
                KnowledgeEdge.visibility.in_(allowed),
                KnowledgeEdge.status != "archived",
                source_node.visibility.in_(allowed),
                target_node.visibility.in_(allowed),
                source_node.status != "archived",
                target_node.status != "archived",
            )
            .order_by(KnowledgeEdge.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        query = _clean_text(q, max_length=120)
        if query:
            needle = f"%{query.lower()}%"
            stmt = stmt.where(func.lower(KnowledgeEdge.relation_type).like(needle))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_serialize_edge(row) for row in rows]

    async def get_edge(self, edge_id: str, *, actor_role: str) -> KnowledgeEdge | None:
        allowed = set(actor_visible_visibilities(actor_role))
        source_node = aliased(KnowledgeNode)
        target_node = aliased(KnowledgeNode)
        return (
            await self.session.execute(
                select(KnowledgeEdge)
                .join(source_node, KnowledgeEdge.source_node_id == source_node.node_id)
                .join(target_node, KnowledgeEdge.target_node_id == target_node.node_id)
                .where(
                    KnowledgeEdge.edge_id == edge_id,
                    KnowledgeEdge.visibility.in_(allowed),
                    source_node.visibility.in_(allowed),
                    target_node.visibility.in_(allowed),
                )
            )
        ).scalar_one_or_none()

    async def update_edge(
        self,
        edge_id: str,
        payload: dict[str, Any],
        *,
        actor_role: str,
        actor_id: str | None = None,
    ) -> dict[str, Any] | None:
        row = await self.get_edge(edge_id, actor_role=actor_role)
        if row is None:
            return None
        if "relation_type" in payload:
            relation_type = _clean_text(payload.get("relation_type"), max_length=50) or ""
            if relation_type not in EDGE_RELATION_TYPES:
                raise ValueError("unsupported relation_type")
            row.relation_type = relation_type
        if "visibility" in payload:
            row.visibility = _clean_text(payload.get("visibility"), max_length=40) or row.visibility
        if "status" in payload:
            status = _clean_text(payload.get("status"), max_length=30) or ""
            if status not in EDGE_STATUSES:
                raise ValueError("unsupported status")
            row.status = status
        if "weight" in payload:
            row.weight = _safe_weight(payload.get("weight"))
        if "source_kind" in payload:
            row.source_kind = _clean_text(payload.get("source_kind"), max_length=40)
        if "source_ref" in payload:
            row.source_ref = _clean_text(payload.get("source_ref"), max_length=1000)
        row.updated_by = actor_id
        await self.session.flush()
        return _serialize_edge(row)

    async def archive_edge(self, edge_id: str, *, actor_role: str, actor_id: str | None = None) -> dict[str, Any] | None:
        row = await self.get_edge(edge_id, actor_role=actor_role)
        if row is None:
            return None
        row.status = "archived"
        row.updated_by = actor_id
        await self.session.flush()
        return _serialize_edge(row)

    async def search(self, *, query: str, actor_role: str, limit: int = 50) -> dict[str, Any]:
        query = _clean_text(query, max_length=120) or ""
        nodes = await self.list_nodes(actor_role=actor_role, q=query, limit=limit)
        node_ids = {node["node_id"] for node in nodes}
        allowed = set(actor_visible_visibilities(actor_role))
        edge_rows: list[KnowledgeEdge] = []
        if node_ids:
            source_node = aliased(KnowledgeNode)
            target_node = aliased(KnowledgeNode)
            edge_rows.extend(
                (
                    await self.session.execute(
                        select(KnowledgeEdge)
                        .join(source_node, KnowledgeEdge.source_node_id == source_node.node_id)
                        .join(target_node, KnowledgeEdge.target_node_id == target_node.node_id)
                        .where(
                            KnowledgeEdge.visibility.in_(allowed),
                            KnowledgeEdge.status != "archived",
                            source_node.visibility.in_(allowed),
                            target_node.visibility.in_(allowed),
                            source_node.status != "archived",
                            target_node.status != "archived",
                            (KnowledgeEdge.source_node_id.in_(node_ids)) | (KnowledgeEdge.target_node_id.in_(node_ids)),
                        )
                        .limit(max(1, min(limit, 200)))
                    )
                )
                .scalars()
                .all()
            )
        if query:
            needle = f"%{query.lower()}%"
            source_node = aliased(KnowledgeNode)
            target_node = aliased(KnowledgeNode)
            edge_rows.extend(
                (
                    await self.session.execute(
                        select(KnowledgeEdge)
                        .join(source_node, KnowledgeEdge.source_node_id == source_node.node_id)
                        .join(target_node, KnowledgeEdge.target_node_id == target_node.node_id)
                        .where(
                            KnowledgeEdge.visibility.in_(allowed),
                            KnowledgeEdge.status != "archived",
                            source_node.visibility.in_(allowed),
                            target_node.visibility.in_(allowed),
                            source_node.status != "archived",
                            target_node.status != "archived",
                            func.lower(KnowledgeEdge.relation_type).like(needle),
                        )
                        .limit(max(1, min(limit, 200)))
                    )
                )
                .scalars()
                .all()
            )
        deduped_edges = {edge.edge_id: edge for edge in edge_rows}
        return {"nodes": nodes, "edges": [_serialize_edge(row) for row in deduped_edges.values()]}

    async def get_layout(self, *, scope_ref: str, scope_type: str = "graph") -> dict[str, Any]:
        row = (
            await self.session.execute(
                select(KnowledgeGraphLayout).where(
                    KnowledgeGraphLayout.scope_type == scope_type,
                    KnowledgeGraphLayout.scope_ref == scope_ref,
                )
            )
        ).scalar_one_or_none()
        return _serialize_layout(row, scope_type=scope_type, scope_ref=scope_ref)

    async def save_layout(
        self,
        *,
        scope_ref: str,
        layout_json: Any,
        scope_type: str = "graph",
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        safe_layout = _sanitize_layout_json(layout_json)
        row = (
            await self.session.execute(
                select(KnowledgeGraphLayout).where(
                    KnowledgeGraphLayout.scope_type == scope_type,
                    KnowledgeGraphLayout.scope_ref == scope_ref,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgeGraphLayout(
                layout_id=_new_id(),
                scope_type=scope_type,
                scope_ref=scope_ref,
                layout_json=safe_layout,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.session.add(row)
        else:
            row.layout_json = safe_layout
            row.updated_by = actor_id
        await self.session.flush()
        return _serialize_layout(row, scope_type=scope_type, scope_ref=scope_ref)

    async def ensure_item_binding_edges(
        self,
        item_id_or_slug: str,
        *,
        service_code: str | None,
        offering_code: str | None,
        actor_id: str | None,
    ) -> None:
        item = (
            await self.session.execute(
                select(KnowledgeItem).where(or_(KnowledgeItem.item_id == item_id_or_slug, KnowledgeItem.slug == item_id_or_slug))
            )
        ).scalar_one()
        item_node = await self.upsert_node(
            stable_key=f"knowledge_item:{item.slug}",
            node_type="knowledge_item",
            label=item.title,
            visibility=item.visibility,
            linked_item_id=item.item_id,
            actor_id=actor_id,
        )
        if service_code:
            service_node = await self.upsert_node(
                stable_key=f"service:{service_code}",
                node_type="service",
                label=service_code,
                visibility=item.visibility,
                service_code=service_code,
                actor_id=actor_id,
            )
            await self.create_edge(item_node, service_node, relation_type="belongs_to_service", visibility=item.visibility, actor_id=actor_id)
        if offering_code:
            offering_node = await self.upsert_node(
                stable_key=f"offering:{offering_code}",
                node_type="offering",
                label=offering_code,
                visibility=item.visibility,
                service_code=service_code,
                offering_code=offering_code,
                actor_id=actor_id,
            )
            await self.create_edge(item_node, offering_node, relation_type="belongs_to_offering", visibility=item.visibility, actor_id=actor_id)

    async def neighborhood(self, *, stable_key: str, actor_role: str, depth: int = 1) -> dict[str, Any]:
        if depth < 1 or depth > 2:
            raise ValueError("depth must be 1 or 2")
        allowed = set(actor_visible_visibilities(actor_role))
        root = (
            await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == stable_key))
        ).scalar_one_or_none()
        if root is None or root.visibility not in allowed:
            return {"nodes": [], "edges": []}
        nodes: dict[str, KnowledgeNode] = {root.node_id: root}
        edges: dict[str, KnowledgeEdge] = {}
        queue: deque[tuple[str, int]] = deque([(root.node_id, 0)])
        while queue:
            node_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            rows = (
                await self.session.execute(
                    select(KnowledgeEdge).where(
                        (KnowledgeEdge.source_node_id == node_id) | (KnowledgeEdge.target_node_id == node_id),
                        KnowledgeEdge.visibility.in_(allowed),
                    )
                )
            ).scalars().all()
            for edge in rows:
                neighbor_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
                if neighbor_id in nodes:
                    edges[edge.edge_id] = edge
                    continue

                neighbor = (
                    await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.node_id == neighbor_id))
                ).scalar_one_or_none()
                if neighbor is None or neighbor.visibility not in allowed:
                    continue

                nodes[neighbor.node_id] = neighbor
                queue.append((neighbor.node_id, current_depth + 1))
                edges[edge.edge_id] = edge

        visible_node_ids = set(nodes)
        visible_edges = {
            edge_id: edge
            for edge_id, edge in edges.items()
            if edge.source_node_id in visible_node_ids and edge.target_node_id in visible_node_ids
        }
        return {"nodes": [_serialize_node(row) for row in nodes.values()], "edges": [_serialize_edge(row) for row in visible_edges.values()]}

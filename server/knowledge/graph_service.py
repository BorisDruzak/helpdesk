from __future__ import annotations

from collections import deque
from typing import Any
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeEdge, KnowledgeItem, KnowledgeNode
from knowledge.contracts import actor_visible_visibilities


def _new_id() -> str:
    return str(uuid.uuid4())


def _serialize_node(row: KnowledgeNode) -> dict[str, Any]:
    return {
        "node_id": row.node_id,
        "node_type": row.node_type,
        "stable_key": row.stable_key,
        "label": row.label,
        "visibility": row.visibility,
        "linked_item_id": row.linked_item_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "status": row.status,
    }


def _serialize_edge(row: KnowledgeEdge) -> dict[str, Any]:
    return {
        "edge_id": row.edge_id,
        "source_node_id": row.source_node_id,
        "target_node_id": row.target_node_id,
        "relation_type": row.relation_type,
        "visibility": row.visibility,
        "status": row.status,
    }


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession):
        self.session = session

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
                edges[edge.edge_id] = edge
                neighbor_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
                if neighbor_id not in nodes:
                    neighbor = (await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.node_id == neighbor_id))).scalar_one()
                    if neighbor.visibility in allowed:
                        nodes[neighbor.node_id] = neighbor
                        queue.append((neighbor.node_id, current_depth + 1))
        return {"nodes": [_serialize_node(row) for row in nodes.values()], "edges": [_serialize_edge(row) for row in edges.values()]}

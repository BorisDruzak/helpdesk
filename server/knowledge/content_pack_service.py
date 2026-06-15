from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBinding, KnowledgeContentPack, KnowledgeContentPackItem, KnowledgeEdge, KnowledgeNode
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.contracts import KnowledgeValidationError, normalize_knowledge_slug
from knowledge.graph_service import KnowledgeGraphService


def _new_id() -> str:
    return str(uuid.uuid4())


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pack_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise KnowledgeValidationError("content pack version must be an integer") from exc
    if version <= 0:
        raise KnowledgeValidationError("content pack version must be positive")
    return version


def _redact_error(error: BaseException) -> str:
    text = str(error)
    for marker in ("token", "password", "secret"):
        text = text.replace(marker, f"{marker[:1]}***")
    return text[:500]


def load_content_pack_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise KnowledgeValidationError("content pack file must contain an object")
    return payload


class KnowledgeContentPackService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _normalize_pack(self, pack: dict[str, Any]) -> dict[str, Any]:
        code = normalize_knowledge_slug(pack.get("code"))
        version = _pack_version(pack.get("version"))
        items = pack.get("items") if isinstance(pack.get("items"), list) else []
        spaces = pack.get("spaces") if isinstance(pack.get("spaces"), list) else []
        graph = pack.get("graph") if isinstance(pack.get("graph"), dict) else {}
        return {
            **deepcopy(pack),
            "code": code,
            "version": version,
            "title": str(pack.get("title") or code),
            "description": str(pack.get("description") or "").strip() or None,
            "spaces": [deepcopy(item) for item in spaces if isinstance(item, dict)],
            "items": [deepcopy(item) for item in items if isinstance(item, dict)],
            "graph": {
                "nodes": [deepcopy(node) for node in graph.get("nodes", []) if isinstance(node, dict)],
                "edges": [deepcopy(edge) for edge in graph.get("edges", []) if isinstance(edge, dict)],
            },
        }

    async def apply_pack(
        self,
        pack: dict[str, Any],
        *,
        actor_id: str | None,
        dry_run: bool = False,
        force: bool = False,
        retire_missing: bool = False,
        publish: bool = False,
    ) -> dict[str, Any]:
        normalized = self._normalize_pack(pack)
        source_hash = _canonical_hash(normalized)
        summary = {"created": 0, "updated": 0, "skipped": 0, "conflict": 0, "failed": 0, "retired": 0}
        item_results: list[dict[str, Any]] = []
        repo = KnowledgeRepo(self.session)

        if dry_run:
            for item in normalized["items"]:
                slug = normalize_knowledge_slug(item.get("slug") or item.get("title"))
                existing = await repo.get_item_row(slug)
                item_hash = _canonical_hash(item)
                prior_hash = await self._last_success_hash(normalized["code"], normalized["version"], slug)
                status = "created" if existing is None else "skipped" if prior_hash == item_hash else "updated" if force else "conflict"
                summary[status] += 1
                item_results.append({"item_slug": slug, "install_status": status, "content_hash": item_hash})
            return {"status": "dry_run", "summary": summary, "items": item_results, "source_hash": source_hash}

        for space in normalized["spaces"]:
            space_payload = {
                "code": space.get("code"),
                "title": space.get("title"),
                "description": space.get("description"),
                "visibility": space.get("visibility") or "support_internal",
                "lifecycle_status": space.get("lifecycle_status") or "active",
                "owner_actor_id": space.get("owner") or space.get("owner_actor_id"),
                "default_reviewer_actor_id": space.get("reviewer") or space.get("default_reviewer_actor_id"),
                "default_review_period_days": space.get("default_review_period_days"),
                "allow_publication": space.get("allow_publication", True),
                "allow_ingestion": space.get("allow_ingestion", True),
                "allow_rag": space.get("allow_rag", False),
                "metadata": space.get("metadata") if isinstance(space.get("metadata"), dict) else {},
            }
            if "allowed_item_types" in space:
                space_payload["allowed_item_types"] = space.get("allowed_item_types")
            await repo.upsert_space(
                space_payload,
                actor_id=actor_id,
            )

        for raw_item in normalized["items"]:
            slug = normalize_knowledge_slug(raw_item.get("slug") or raw_item.get("title"))
            item_hash = _canonical_hash(raw_item)
            try:
                existing = await repo.get_item_row(slug)
                prior_hash = await self._last_success_hash(normalized["code"], normalized["version"], slug)
                if existing is not None and prior_hash == item_hash:
                    result = await self._record_item(normalized, raw_item, item_hash, "skipped", existing.item_id, existing.current_version_id)
                    summary["skipped"] += 1
                elif existing is not None and not force:
                    result = await self._record_item(normalized, raw_item, item_hash, "conflict", existing.item_id, existing.current_version_id)
                    summary["conflict"] += 1
                else:
                    result = await self._install_item(repo, normalized, raw_item, item_hash, actor_id=actor_id, force=force, publish=publish)
                    summary[result["install_status"]] += 1
                item_results.append(result)
            except Exception as exc:
                summary["failed"] += 1
                item_results.append(await self._record_item(normalized, raw_item, item_hash, "failed", None, None, error=_redact_error(exc)))

        if retire_missing:
            current_slugs = {normalize_knowledge_slug(item.get("slug") or item.get("title")) for item in normalized["items"]}
            retired = await self._retire_missing_items(repo, normalized, current_slugs, actor_id=actor_id)
            item_results.extend(retired)
            summary["retired"] += len(retired)

        if normalized["graph"]["nodes"] or normalized["graph"]["edges"]:
            try:
                await self._install_graph(repo, normalized["graph"], actor_id=actor_id)
            except Exception as exc:
                summary["failed"] += 1
                item_results.append(
                    {
                        "item_slug": "__graph__",
                        "install_status": "failed",
                        "content_hash": _canonical_hash(normalized["graph"]),
                        "last_error_redacted": _redact_error(exc),
                    }
                )

        status = "installed" if not (summary["failed"] or summary["conflict"]) else "partially_installed"
        pack_row = await self._upsert_pack_record(normalized, source_hash, status=status, actor_id=actor_id, summary=summary)
        return {"status": pack_row.status, "summary": summary, "items": item_results, "source_hash": source_hash}

    async def _last_success_hash(self, pack_code: str, pack_version: int, slug: str) -> str | None:
        row = (
            await self.session.execute(
                select(KnowledgeContentPackItem)
                .where(
                    KnowledgeContentPackItem.pack_code == pack_code,
                    KnowledgeContentPackItem.pack_version == pack_version,
                    KnowledgeContentPackItem.item_slug == slug,
                    KnowledgeContentPackItem.install_status.in_(("created", "updated", "skipped")),
                )
                .order_by(KnowledgeContentPackItem.installed_at.desc(), KnowledgeContentPackItem.id.desc())
            )
        ).scalars().first()
        return row.content_hash if row else None

    async def _install_item(
        self,
        repo: KnowledgeRepo,
        pack: dict[str, Any],
        raw_item: dict[str, Any],
        item_hash: str,
        *,
        actor_id: str | None,
        force: bool,
        publish: bool,
    ) -> dict[str, Any]:
        slug = normalize_knowledge_slug(raw_item.get("slug") or raw_item.get("title"))
        existing = await repo.get_item_row(slug)
        status = "updated" if existing is not None and force else "created"
        if existing is None:
            item = await repo.create_item_draft(
                {
                    "space_code": raw_item.get("space"),
                    "slug": slug,
                    "item_type": raw_item.get("item_type") or raw_item.get("type") or "article",
                    "title": raw_item.get("title"),
                    "summary": raw_item.get("summary"),
                    "visibility": raw_item.get("visibility") or "support_internal",
                    "owner_actor_id": raw_item.get("owner") or raw_item.get("owner_actor_id"),
                    "reviewer_actor_id": raw_item.get("reviewer") or raw_item.get("reviewer_actor_id"),
                    "source_kind": "manual",
                    "source_ref": f"content_pack:{pack['code']}@{pack['version']}",
                    "tags": raw_item.get("tags") or [],
                    "metadata": {
                        "content_pack": {"code": pack["code"], "version": pack["version"]},
                        "quality": raw_item.get("quality") if isinstance(raw_item.get("quality"), dict) else {},
                    },
                },
                actor_id=actor_id,
                actor_role="admin",
            )
            item_id = item["item_id"]
        else:
            item_id = existing.item_id
            existing.title = str(raw_item.get("title") or existing.title)
            existing.summary = str(raw_item.get("summary") or existing.summary or "") or None
            existing.reviewer_actor_id = str(raw_item.get("reviewer") or existing.reviewer_actor_id or "") or None
            existing.owner_actor_id = str(raw_item.get("owner") or existing.owner_actor_id or "") or None
            existing.tags = list(raw_item.get("tags") or existing.tags or [])
        review_due_days = raw_item.get("review_due_days")
        if review_due_days:
            row = await repo.get_item_row(item_id)
            if row is not None:
                row.review_due_at = datetime.now(timezone.utc) + timedelta(days=int(review_due_days))
        version = await repo.create_version(
            item_id,
            {
                "title": raw_item.get("title"),
                "summary": raw_item.get("summary"),
                "body_format": raw_item.get("body_format") or "markdown",
                "body": raw_item.get("body") or "",
                "change_summary": f"Applied content pack {pack['code']}@{pack['version']}",
                "source_refs": raw_item.get("source_refs") or [{"content_pack": pack["code"], "version": pack["version"]}],
                "metadata": {"content_hash": item_hash},
            },
            actor_id=actor_id,
            actor_role="admin",
        )
        for binding in raw_item.get("bindings") or []:
            if isinstance(binding, dict):
                await repo.add_binding(item_id, binding, actor_id=actor_id, actor_role="admin")
        should_publish = raw_item.get("status") == "published"
        if raw_item.get("visibility") == "support_internal" and not publish:
            should_publish = False
        if should_publish:
            await repo.publish_item(item_id, version["version_id"], actor_id=actor_id, actor_role="admin", review_note="Content pack baseline review")
        return await self._record_item(pack, raw_item, item_hash, status, item_id, version["version_id"])

    async def _retire_missing_items(
        self,
        repo: KnowledgeRepo,
        pack: dict[str, Any],
        current_slugs: set[str],
        *,
        actor_id: str | None,
    ) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(KnowledgeContentPackItem)
                .where(KnowledgeContentPackItem.pack_code == pack["code"], KnowledgeContentPackItem.pack_version == pack["version"], KnowledgeContentPackItem.item_id.is_not(None))
                .order_by(KnowledgeContentPackItem.installed_at.desc(), KnowledgeContentPackItem.id.desc())
            )
        ).scalars().all()
        seen: set[str] = set()
        retired: list[dict[str, Any]] = []
        for row in rows:
            if row.item_slug in seen or row.item_slug in current_slugs:
                continue
            seen.add(row.item_slug)
            item = await repo.get_item_row(row.item_slug)
            if item is None:
                continue
            item.status = "archived"
            item.archived_at = datetime.now(timezone.utc)
            item.updated_by = actor_id
            retired.append(
                await self._record_item(
                    pack,
                    {"slug": row.item_slug, "title": row.item_slug},
                    row.content_hash,
                    "retired",
                    item.item_id,
                    item.current_version_id,
                )
            )
        return retired

    async def repair_pack_bindings(
        self,
        pack: dict[str, Any],
        *,
        actor_id: str | None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        normalized = self._normalize_pack(pack)
        summary = {"bindings_repaired": 0, "skipped": 0, "missing": 0}
        results: list[dict[str, Any]] = []
        repo = KnowledgeRepo(self.session)
        graph = KnowledgeGraphService(self.session)
        for raw_item in normalized["items"]:
            slug = normalize_knowledge_slug(raw_item.get("slug") or raw_item.get("title"))
            desired_bindings = [deepcopy(binding) for binding in raw_item.get("bindings") or [] if isinstance(binding, dict)]
            if not desired_bindings:
                summary["skipped"] += 1
                continue
            managed = await self._latest_pack_item(normalized["code"], slug)
            if managed is None or not managed.item_id:
                summary["missing"] += 1
                results.append({"item_slug": slug, "status": "missing_pack_managed_item"})
                continue
            item = await repo.get_item_row(managed.item_id)
            if item is None:
                summary["missing"] += 1
                results.append({"item_slug": slug, "status": "missing_item"})
                continue
            current_rows = (
                await self.session.execute(select(KnowledgeBinding).where(KnowledgeBinding.item_id == item.item_id).order_by(KnowledgeBinding.created_at, KnowledgeBinding.binding_id))
            ).scalars().all()
            old_bindings = [self._binding_payload(row) for row in current_rows]
            new_bindings = [self._normalize_binding_payload(binding) for binding in desired_bindings]
            if old_bindings == new_bindings:
                summary["skipped"] += 1
                results.append({"item_slug": slug, "status": "skipped"})
                continue
            summary["bindings_repaired"] += 1
            result = {
                "item_slug": slug,
                "item_id": item.item_id,
                "status": "bindings_repaired",
                "old_bindings": old_bindings,
                "new_bindings": new_bindings,
            }
            results.append(result)
            if dry_run:
                continue
            await self.session.execute(delete(KnowledgeBinding).where(KnowledgeBinding.item_id == item.item_id))
            await self._remove_item_binding_graph_edges(item.slug)
            for binding in desired_bindings:
                await repo.add_binding(item.item_id, binding, actor_id=actor_id, actor_role="admin")
                await graph.ensure_item_binding_edges(
                    item.item_id,
                    service_code=str(binding.get("service_code") or "").strip() or None,
                    offering_code=str(binding.get("offering_code") or "").strip() or None,
                    actor_id=actor_id,
                )
            audit = KnowledgeContentPackItem(
                pack_code=normalized["code"],
                pack_version=normalized["version"],
                item_slug=slug,
                item_id=item.item_id,
                version_id=item.current_version_id,
                content_hash=_canonical_hash(raw_item),
                install_status="bindings_repaired",
                installed_at=datetime.now(timezone.utc),
                metadata_json={
                    "title": raw_item.get("title"),
                    "old_bindings": old_bindings,
                    "new_bindings": new_bindings,
                    "actor": actor_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.session.add(audit)
            await self.session.flush()
        return {"status": "dry_run" if dry_run else "ok", "summary": summary, "items": results}

    async def _latest_pack_item(self, pack_code: str, slug: str) -> KnowledgeContentPackItem | None:
        return (
            await self.session.execute(
                select(KnowledgeContentPackItem)
                .where(
                    KnowledgeContentPackItem.pack_code == pack_code,
                    KnowledgeContentPackItem.item_slug == slug,
                    KnowledgeContentPackItem.item_id.is_not(None),
                    KnowledgeContentPackItem.install_status.in_(("created", "updated", "skipped", "bindings_repaired")),
                )
                .order_by(KnowledgeContentPackItem.installed_at.desc(), KnowledgeContentPackItem.id.desc())
            )
        ).scalars().first()

    @staticmethod
    def _normalize_binding_payload(binding: dict[str, Any]) -> dict[str, Any]:
        return {
            "service_code": str(binding.get("service_code") or "").strip() or None,
            "offering_code": str(binding.get("offering_code") or "").strip() or None,
            "request_template_key": str(binding.get("request_template_key") or "").strip() or None,
            "weight": float(binding.get("weight") or 1),
        }

    def _binding_payload(self, row: KnowledgeBinding) -> dict[str, Any]:
        return {
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_template_key": row.request_template_key,
            "weight": float(row.weight or 1),
        }

    async def _remove_item_binding_graph_edges(self, slug: str) -> None:
        item_node = (
            await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == f"knowledge_item:{slug}"))
        ).scalar_one_or_none()
        if item_node is None:
            return
        await self.session.execute(
            delete(KnowledgeEdge).where(
                KnowledgeEdge.source_node_id == item_node.node_id,
                KnowledgeEdge.relation_type.in_(("belongs_to_service", "belongs_to_offering")),
            )
        )

    async def _install_graph(self, repo: KnowledgeRepo, graph_payload: dict[str, Any], *, actor_id: str | None) -> None:
        graph = KnowledgeGraphService(self.session)
        for raw_node in graph_payload.get("nodes") or []:
            stable_key = str(raw_node.get("stable_key") or "").strip()
            if not stable_key:
                raise KnowledgeValidationError("graph node stable_key is required")
            await self._ensure_graph_node(repo, graph, stable_key, raw_node, actor_id=actor_id)

        for raw_edge in graph_payload.get("edges") or []:
            source_key = str(raw_edge.get("source") or raw_edge.get("source_key") or "").strip()
            target_key = str(raw_edge.get("target") or raw_edge.get("target_key") or "").strip()
            relation_type = str(raw_edge.get("relation_type") or "").strip()
            if not source_key or not target_key or not relation_type:
                raise KnowledgeValidationError("graph edge source, target and relation_type are required")
            source = await self._ensure_graph_node(repo, graph, source_key, {}, actor_id=actor_id)
            target = await self._ensure_graph_node(repo, graph, target_key, {}, actor_id=actor_id)
            await graph.create_edge(
                source,
                target,
                relation_type=relation_type,
                visibility=str(raw_edge.get("visibility") or source.visibility or target.visibility or "support_internal"),
                actor_id=actor_id,
            )

    async def _ensure_graph_node(
        self,
        repo: KnowledgeRepo,
        graph: KnowledgeGraphService,
        stable_key: str,
        raw_node: dict[str, Any],
        *,
        actor_id: str | None,
    ) -> KnowledgeNode:
        existing = (await self.session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == stable_key))).scalar_one_or_none()
        if existing is not None and not raw_node:
            return existing
        if stable_key.startswith("knowledge_item:") and not raw_node:
            slug = stable_key.removeprefix("knowledge_item:")
            item = await repo.get_item_row(slug)
            if item is None:
                raise KnowledgeValidationError(f"graph item node references missing item {slug}")
            return await graph.upsert_node(
                stable_key=stable_key,
                node_type="knowledge_item",
                label=item.title,
                visibility=item.visibility,
                linked_item_id=item.item_id,
                actor_id=actor_id,
            )
        return await graph.upsert_node(
            stable_key=stable_key,
            node_type=str(raw_node.get("node_type") or raw_node.get("type") or "concept"),
            label=str(raw_node.get("label") or stable_key),
            visibility=str(raw_node.get("visibility") or "support_internal"),
            linked_item_id=raw_node.get("linked_item_id"),
            service_code=raw_node.get("service_code"),
            offering_code=raw_node.get("offering_code"),
            actor_id=actor_id,
        )

    async def _record_item(
        self,
        pack: dict[str, Any],
        raw_item: dict[str, Any],
        content_hash: str,
        status: str,
        item_id: str | None,
        version_id: str | None,
        *,
        error: str | None = None,
    ) -> dict[str, Any]:
        slug = normalize_knowledge_slug(raw_item.get("slug") or raw_item.get("title"))
        row = KnowledgeContentPackItem(
            pack_code=pack["code"],
            pack_version=pack["version"],
            item_slug=slug,
            item_id=item_id,
            version_id=version_id,
            content_hash=content_hash,
            install_status=status,
            last_error_redacted=error,
            installed_at=datetime.now(timezone.utc),
            metadata_json={"title": raw_item.get("title")},
        )
        self.session.add(row)
        await self.session.flush()
        return {
            "item_slug": slug,
            "item_id": item_id,
            "version_id": version_id,
            "install_status": status,
            "content_hash": content_hash,
            "last_error_redacted": error,
        }

    async def _upsert_pack_record(
        self,
        pack: dict[str, Any],
        source_hash: str,
        *,
        status: str,
        actor_id: str | None,
        summary: dict[str, int],
    ) -> KnowledgeContentPack:
        row = (
            await self.session.execute(
                select(KnowledgeContentPack).where(KnowledgeContentPack.code == pack["code"], KnowledgeContentPack.version == pack["version"])
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgeContentPack(pack_id=_new_id(), code=pack["code"], version=pack["version"], title=pack["title"], source_hash=source_hash)
            self.session.add(row)
        row.title = pack["title"]
        row.description = pack.get("description")
        row.installed_at = datetime.now(timezone.utc)
        row.installed_by = actor_id
        row.source_hash = source_hash
        row.status = status
        row.metadata_json = {"summary": deepcopy(summary)}
        await self.session.flush()
        return row

    async def retire_pack(self, code: str, *, actor_id: str | None) -> dict[str, Any]:
        pack_code = normalize_knowledge_slug(code)
        rows = (
            await self.session.execute(
                select(KnowledgeContentPackItem)
                .where(KnowledgeContentPackItem.pack_code == pack_code, KnowledgeContentPackItem.item_id.is_not(None))
                .order_by(KnowledgeContentPackItem.installed_at.desc(), KnowledgeContentPackItem.id.desc())
            )
        ).scalars().all()
        seen: set[str] = set()
        summary = {"created": 0, "updated": 0, "skipped": 0, "conflict": 0, "failed": 0, "retired": 0}
        results: list[dict[str, Any]] = []
        repo = KnowledgeRepo(self.session)
        for row in rows:
            if row.item_slug in seen:
                continue
            seen.add(row.item_slug)
            item = await repo.get_item_row(row.item_slug)
            if item is None:
                continue
            item.status = "archived"
            item.archived_at = datetime.now(timezone.utc)
            item.updated_by = actor_id
            result = await self._record_item(
                {"code": row.pack_code, "version": row.pack_version},
                {"slug": row.item_slug, "title": row.item_slug},
                row.content_hash,
                "retired",
                item.item_id,
                item.current_version_id,
            )
            results.append(result)
            summary["retired"] += 1
        pack_rows = (await self.session.execute(select(KnowledgeContentPack).where(KnowledgeContentPack.code == pack_code))).scalars().all()
        for pack in pack_rows:
            pack.status = "retired"
            pack.installed_at = datetime.now(timezone.utc)
            pack.installed_by = actor_id
        await self.session.flush()
        return {"status": "retired", "summary": summary, "items": results}

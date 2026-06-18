from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeContentPack, KnowledgeContentPackItem
from knowledge.content_pack_service import KnowledgeContentPackService, load_content_pack_file
from knowledge.graph_service import KnowledgeGraphService


def _baseline_pack(body: str = "## Steps\n\n1. Reconnect VPN.") -> dict:
    return {
        "code": "it-self-service-baseline",
        "version": 1,
        "title": "IT Self-Service Baseline",
        "description": "Requester-safe starter content for common IT issues.",
        "spaces": [
            {
                "code": "it-self-service",
                "title": "IT Self-Service",
                "visibility": "requester",
                "lifecycle_status": "active",
                "default_reviewer_actor_id": "servicedesk",
            }
        ],
        "items": [
            {
                "slug": "vpn-reconnect-basic",
                "type": "article",
                "space": "it-self-service",
                "title": "Как переподключить VPN",
                "summary": "Безопасная инструкция для пользователя.",
                "visibility": "requester",
                "status": "published",
                "owner": "servicedesk",
                "reviewer": "servicedesk",
                "tags": ["vpn", "remote_work"],
                "review_due_days": 90,
                "bindings": [{"service_code": "network", "offering_code": "network.vpn_issue", "weight": 1.0}],
                "body_format": "markdown",
                "body": body,
                "quality": {"source": "baseline_pack", "reviewed": True},
            }
        ],
    }


@pytest.mark.asyncio
async def test_content_pack_dry_run_install_skip_conflict_and_force_update(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)

        dry_run = await service.apply_pack(_baseline_pack(), actor_id="admin-test", dry_run=True)
        assert dry_run["summary"] == {"created": 1, "updated": 0, "skipped": 0, "conflict": 0, "failed": 0, "retired": 0}
        assert not (await session.execute(select(KnowledgeContentPack))).scalars().all()

        installed = await service.apply_pack(_baseline_pack(), actor_id="admin-test")
        await session.commit()
        assert installed["status"] == "installed"
        assert installed["summary"]["created"] == 1

    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        skipped = await service.apply_pack(_baseline_pack(), actor_id="admin-test")
        await session.commit()
        assert skipped["summary"]["skipped"] == 1

        changed = _baseline_pack(body="## Steps\n\n1. Reconnect VPN.\n2. Reboot the VPN client.")
        conflict = await service.apply_pack(changed, actor_id="admin-test")
        await session.commit()
        assert conflict["summary"]["conflict"] == 1

        forced = await service.apply_pack(changed, actor_id="admin-test", force=True)
        await session.commit()
        assert forced["summary"]["updated"] == 1

        rows = (await session.execute(select(KnowledgeContentPackItem))).scalars().all()
        statuses = [row.install_status for row in rows]
        assert statuses == ["created", "skipped", "conflict", "updated"]


@pytest.mark.asyncio
async def test_content_pack_retire_archives_installed_item(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        await service.apply_pack(_baseline_pack(), actor_id="admin-test")
        retired = await service.retire_pack("it-self-service-baseline", actor_id="admin-test")
        await session.commit()

    assert retired["summary"]["retired"] == 1
    assert retired["items"][0]["install_status"] == "retired"


@pytest.mark.asyncio
async def test_content_pack_installs_declared_graph_nodes_and_edges(test_engine) -> None:
    pack = _baseline_pack()
    pack["graph"] = {
        "nodes": [
            {
                "stable_key": "concept:vpn",
                "node_type": "concept",
                "label": "VPN",
                "visibility": "requester",
            }
        ],
        "edges": [
            {
                "source": "knowledge_item:vpn-reconnect-basic",
                "target": "concept:vpn",
                "relation_type": "mentions",
                "visibility": "requester",
            }
        ],
    }
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await KnowledgeContentPackService(session).apply_pack(pack, actor_id="admin-test")
        await session.commit()

    async with session_maker() as session:
        neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="knowledge_item:vpn-reconnect-basic",
            actor_role="requester",
            depth=1,
        )

    node_keys = {node["stable_key"] for node in neighborhood["nodes"]}
    relation_types = {edge["relation_type"] for edge in neighborhood["edges"]}
    assert "concept:vpn" in node_keys
    assert "mentions" in relation_types


def test_required_baseline_content_packs_are_present_and_safe() -> None:
    required = {
        "it-self-service-baseline": 6,
        "support-runbooks-baseline": 5,
        "known-errors-baseline": 2,
        "glossary-baseline": 8,
    }
    for code, minimum_items in required.items():
        pack = load_content_pack_file(f"content_packs/knowledge/{code}.yaml")
        assert pack["code"] == code
        assert len(pack["items"]) >= minimum_items
        for item in pack["items"]:
            body = str(item.get("body") or "").lower()
            if item.get("visibility") in {"requester", "public", "agent_requester_safe"}:
                assert "queue_id" not in body
                assert "device_id" not in body
                assert "requester_id" not in body
                assert "run command" not in body


@pytest.mark.no_db
def test_primary_agent_requester_guides_pack_contains_pa11_articles() -> None:
    pack = load_content_pack_file("content_packs/knowledge/primary-agent-requester-guides.yaml")
    expected_titles = {
        "Как создать обращение за другого сотрудника",
        "Что делать, если мой ПК не включается",
        "Как запросить смену владельца устройства",
        "Как привязать устройство к аккаунту",
        "Как заполнить профиль пользователя",
    }
    forbidden_terms = {"affected_person_id", "target_device_id", "binding_id", "claim_id"}

    assert pack["code"] == "primary-agent-requester-guides"
    titles = {item["title"] for item in pack["items"]}
    assert expected_titles <= titles
    assert len(pack["items"]) == 5
    bindings_by_title = {
        item["title"]: {
            binding.get("request_template_key")
            for binding in item.get("bindings", [])
            if isinstance(binding, dict)
        }
        for item in pack["items"]
    }
    assert "agent_binding_help" in bindings_by_title["Как привязать устройство к аккаунту"]
    assert "profile_completion_help" in bindings_by_title["Как заполнить профиль пользователя"]
    for item in pack["items"]:
        assert item["visibility"] == "requester"
        article_text = "\n".join(str(item.get(key) or "") for key in ("title", "summary", "body"))
        assert not any(term in article_text for term in forbidden_terms)


@pytest.mark.asyncio
async def test_unsafe_requester_content_pack_item_fails_lint(test_engine) -> None:
    pack = _baseline_pack(body="Ask support to run command and inspect queue_id=42.")
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await KnowledgeContentPackService(session).apply_pack(pack, actor_id="admin-test")
        await session.commit()

    assert result["summary"]["failed"] == 1
    assert result["items"][0]["install_status"] == "failed"

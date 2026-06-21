from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeAudienceRule
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.operations_service import KnowledgeOperationsService
from knowledge.suggestion_service import KnowledgeSuggestionService
from registry.audience_contracts import EffectiveAudience


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_knowledge_suggestions_return_requester_safe_bound_items(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-reconnect",
                "item_type": "article",
                "title": "Как переподключить VPN",
                "summary": "Подходит для проблем с VPN",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "Как переподключить VPN", "body_format": "markdown", "body": "1. Отключите VPN.\n2. Подключите снова."},
            actor_id="support",
        )
        await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "vpn_issue"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "request_template_key": "vpn_issue",
                "query": "VPN не подключается",
                "surface": "requester_portal",
            },
            actor_role="requester",
        )

    assert suggestions["suggestions"][0]["slug"] == "vpn-reconnect"
    assert suggestions["suggestions"][0]["reason"]
    assert "source_ticket_id" not in suggestions["suggestions"][0]


@pytest.mark.asyncio
async def test_knowledge_suggestions_use_requester_context_as_pre_submit_query(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "r9-context", "title": "R9 Context", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        unrelated = await repo.create_item_draft(
            {
                "space_code": "r9-context",
                "slug": "aaa-unrelated-r9-context",
                "item_type": "article",
                "title": "AAA unrelated requester context article",
                "summary": "No matching device context here",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        unrelated_version = await repo.create_version(
            unrelated["item_id"],
            {"title": "AAA unrelated requester context article", "body_format": "markdown", "body": "Generic requester content."},
            actor_id="support",
        )
        await repo.publish_item(unrelated["item_id"], unrelated_version["version_id"], actor_id="admin")

        context_item = await repo.create_item_draft(
            {
                "space_code": "r9-context",
                "slug": "zzz-r9-asset-context",
                "item_type": "article",
                "title": "ZZZ asset context article",
                "summary": "Use the device asset context before submit",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        context_version = await repo.create_version(
            context_item["item_id"],
            {
                "title": "ZZZ asset context article",
                "body_format": "markdown",
                "body": "needle-r9-asset-context power adapter steps.",
            },
            actor_id="support",
        )
        await repo.publish_item(context_item["item_id"], context_version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {
                "surface": "requester_portal",
                "requester_context": {
                    "device": {"asset_name": "needle-r9-asset-context", "device_id": "raw-device-id"},
                    "profile": {"department": "IT Operations", "person_id": "raw-person-id"},
                },
            },
            actor_role="requester",
        )

    assert [item["slug"] for item in suggestions["suggestions"]] == ["zzz-r9-asset-context"]
    assert "raw-device-id" not in str(suggestions)
    assert "raw-person-id" not in str(suggestions)


@pytest.mark.asyncio
async def test_on_behalf_affected_context_is_safe_query_signal_not_audience_bypass(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "pa7-on-behalf", "title": "PA7 On Behalf", "visibility": "requester", "lifecycle_status": "active"},
            actor_id="admin",
        )
        creator_visible = await repo.create_item_draft(
            {
                "space_code": "pa7-on-behalf",
                "slug": "creator-visible-affected-context",
                "item_type": "article",
                "title": "Creator visible affected context",
                "summary": "General requester-safe Finance guidance for payroll-pa7-marker",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        creator_visible_version = await repo.create_version(
            creator_visible["item_id"],
            {
                "title": "Creator visible affected context",
                "body_format": "markdown",
                "body": "Finance payroll-pa7-marker general requester-safe guidance.",
            },
            actor_id="support",
        )
        await repo.publish_item(creator_visible["item_id"], creator_visible_version["version_id"], actor_id="admin")

        finance_only = await repo.create_item_draft(
            {
                "space_code": "pa7-on-behalf",
                "slug": "finance-only-affected-context",
                "item_type": "article",
                "title": "Finance only affected context",
                "summary": "Finance-only restricted guidance for payroll-pa7-marker",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        finance_only_version = await repo.create_version(
            finance_only["item_id"],
            {
                "title": "Finance only affected context",
                "body_format": "markdown",
                "body": "payroll-pa7-marker restricted finance-only instructions.",
            },
            actor_id="support",
        )
        await repo.publish_item(finance_only["item_id"], finance_only_version["version_id"], actor_id="admin")
        session.add(
            KnowledgeAudienceRule(
                rule_id="pa7-finance-only-context",
                subject_type="item",
                subject_id=finance_only["item_id"],
                target_type="department",
                target_id="finance",
                effect="allow",
                status="active",
            )
        )
        await session.commit()

    creator_audience = EffectiveAudience(
        person_id="creator-it-pa7",
        actor_id="creator-it-pa7@example.test",
        actor_role="requester",
        department_path=[{"department_id": "it", "code": "it"}],
    )
    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {
                "surface": "requester_portal",
                "affected_context": {
                    "department_name": "Finance payroll-pa7-marker",
                    "person_id": "raw-affected-person",
                    "phone": "+7 900 111-22-33",
                    "email": "affected@example.test",
                    "session_token": "secret-session-token",
                },
            },
            actor_role="requester",
            effective_audience=creator_audience,
        )

    slugs = [item["slug"] for item in suggestions["suggestions"]]
    assert slugs == ["creator-visible-affected-context"]
    assert "finance-only-affected-context" not in str(suggestions)
    assert "Finance only affected context" not in str(suggestions)
    assert "raw-affected-person" not in str(suggestions)
    assert "affected@example.test" not in str(suggestions)
    assert "secret-session-token" not in str(suggestions)


@pytest.mark.asyncio
async def test_knowledge_suggestions_use_binding_context_before_audience_projection(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "service-context", "title": "Service Context", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        visible = await repo.create_item_draft(
            {
                "space_code": "service-context",
                "slug": "it-context-visible",
                "item_type": "article",
                "title": "IT onboarding visible",
                "summary": "Visible through Service Catalog context",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        visible_version = await repo.create_version(
            visible["item_id"],
            {"title": "IT onboarding visible", "body_format": "markdown", "body": "Visible body."},
            actor_id="support",
        )
        await repo.add_binding(
            visible["item_id"],
            {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "network"},
            actor_id="support",
        )
        await repo.publish_item(visible["item_id"], visible_version["version_id"], actor_id="admin")

        hidden = await repo.create_item_draft(
            {
                "space_code": "service-context",
                "slug": "finance-context-hidden",
                "item_type": "article",
                "title": "Finance hidden context article",
                "summary": "Hidden finance context",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        hidden_version = await repo.create_version(
            hidden["item_id"],
            {"title": "Finance hidden context article", "body_format": "markdown", "body": "Hidden finance body."},
            actor_id="support",
        )
        await repo.add_binding(
            hidden["item_id"],
            {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "network"},
            actor_id="support",
        )
        await repo.publish_item(hidden["item_id"], hidden_version["version_id"], actor_id="admin")
        session.add(
            KnowledgeAudienceRule(
                rule_id="rule-finance-context-hidden",
                subject_type="item",
                subject_id=hidden["item_id"],
                target_type="department",
                target_id="finance",
                effect="allow",
                status="active",
            )
        )

        internal = await repo.create_item_draft(
            {
                "space_code": "service-context",
                "slug": "support-context-runbook",
                "item_type": "runbook",
                "title": "Support context runbook",
                "summary": "Internal support context",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        internal_version = await repo.create_version(
            internal["item_id"],
            {"title": "Support context runbook", "body_format": "markdown", "body": "Internal runbook body."},
            actor_id="support",
        )
        await repo.add_binding(
            internal["item_id"],
            {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "network"},
            actor_id="support",
        )
        await repo.publish_item(internal["item_id"], internal_version["version_id"], actor_id="admin")
        await session.commit()

    context = {
        "service_code": "network",
        "offering_code": "network.vpn_issue",
        "request_template_key": "network",
        "query": "text that does not match article content",
        "surface": "requester_portal",
    }
    requester_audience = EffectiveAudience(
        person_id="person-it",
        actor_id="it@example.test",
        actor_role="requester",
        department_path=[{"department_id": "it", "code": "it"}],
    )
    async with session_maker() as session:
        requester_result = await KnowledgeSuggestionService(session).suggest(
            context,
            actor_role="requester",
            effective_audience=requester_audience,
        )
        support_result = await KnowledgeSuggestionService(session).suggest(
            {**context, "surface": "support_workspace"},
            actor_role="support",
        )

    requester_slugs = {item["slug"] for item in requester_result["suggestions"]}
    assert "it-context-visible" in requester_slugs
    assert "finance-context-hidden" not in requester_slugs
    assert "Finance hidden context article" not in str(requester_result)
    assert "Hidden finance body" not in str(requester_result)
    assert "support-context-runbook" in {item["slug"] for item in support_result["suggestions"]}


@pytest.mark.asyncio
async def test_knowledge_suggestions_respect_binding_surface_metadata(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "surface-context", "title": "Surface Context", "visibility": "requester", "lifecycle_status": "active"},
            actor_id="admin",
        )
        requester_item = await repo.create_item_draft(
            {
                "space_code": "surface-context",
                "slug": "vpn-requester-surface",
                "item_type": "article",
                "title": "VPN surface gate marker requester",
                "summary": "Requester pre-submit surface only",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        requester_version = await repo.create_version(
            requester_item["item_id"],
            {
                "title": "VPN surface gate marker requester",
                "body_format": "markdown",
                "body": "VPN surface gate marker requester body.",
            },
            actor_id="support",
        )
        await repo.add_binding(
            requester_item["item_id"],
            {
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "request_template_key": "network",
                "metadata": {"surfaces": ["requester_pre_submit"]},
            },
            actor_id="support",
        )
        await repo.publish_item(requester_item["item_id"], requester_version["version_id"], actor_id="admin")

        support_item = await repo.create_item_draft(
            {
                "space_code": "surface-context",
                "slug": "vpn-support-surface",
                "item_type": "article",
                "title": "VPN surface gate marker support",
                "summary": "Support workspace surface only",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        support_version = await repo.create_version(
            support_item["item_id"],
            {
                "title": "VPN surface gate marker support",
                "body_format": "markdown",
                "body": "VPN surface gate marker support body.",
            },
            actor_id="support",
        )
        await repo.add_binding(
            support_item["item_id"],
            {
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "request_template_key": "network",
                "metadata": {"surfaces": ["support_ticket_workspace"]},
            },
            actor_id="support",
        )
        await repo.publish_item(support_item["item_id"], support_version["version_id"], actor_id="admin")
        await session.commit()

    context = {
        "service_code": "network",
        "offering_code": "network.vpn_issue",
        "request_template_key": "network",
        "query": "VPN surface gate marker",
        "limit": 10,
    }
    async with session_maker() as session:
        requester_result = await KnowledgeSuggestionService(session).suggest(
            {**context, "surface": "requester_portal"},
            actor_role="requester",
        )
        support_result = await KnowledgeSuggestionService(session).suggest(
            {**context, "surface": "support_workspace"},
            actor_role="support",
        )

    assert [item["slug"] for item in requester_result["suggestions"]] == ["vpn-requester-surface"]
    assert [item["slug"] for item in support_result["suggestions"]] == ["vpn-support-surface"]
    assert "vpn-support-surface" not in str(requester_result)
    assert "vpn-requester-surface" not in str(support_result)


@pytest.mark.asyncio
async def test_support_suggestions_can_include_internal_runbooks(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "ops", "title": "Ops", "visibility": "support_internal", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "ops",
                "slug": "vpn-escalation-runbook",
                "item_type": "runbook",
                "title": "VPN escalation runbook",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "VPN escalation runbook", "body_format": "markdown", "body": "Internal escalation."},
            actor_id="support",
        )
        await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "query": "vpn", "surface": "support_workspace"},
            actor_role="support",
        )

    assert "vpn-escalation-runbook" in {item["slug"] for item in suggestions["suggestions"]}


@pytest.mark.asyncio
async def test_show_known_errors_false_removes_known_error_from_all_suggestion_buckets(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "ops", "title": "Ops", "visibility": "support_internal", "lifecycle_status": "active"},
            actor_id="admin",
        )
        known_error = await repo.create_item_draft(
            {
                "space_code": "ops",
                "slug": "vpn-known-error",
                "item_type": "known_error",
                "title": "VPN known error",
                "summary": "VPN known error summary",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
            actor_role="support",
        )
        version = await repo.create_version(
            known_error["item_id"],
            {
                "title": "VPN known error",
                "body_format": "markdown",
                "body": "Known error workaround.",
                "metadata": {"status": "open", "workaround": "Reconnect VPN manually."},
            },
            actor_id="support",
        )
        await repo.add_binding(
            known_error["item_id"],
            {"service_code": "network", "offering_code": "network.vpn_issue"},
            actor_id="support",
        )
        await repo.publish_item(known_error["item_id"], version["version_id"], actor_id="admin")
        await KnowledgeOperationsService(session).upsert_rollout_policy(
            {"surface": "support_workspace", "show_known_errors": False},
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "query": "VPN", "surface": "support_workspace"},
            actor_role="support",
        )

    assert suggestions["suggestions"] == []
    assert suggestions["known_errors"] == []


@pytest.mark.asyncio
async def test_rollout_max_suggestions_zero_returns_no_suggestions(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-zero-max",
                "item_type": "article",
                "title": "VPN zero max",
                "summary": "VPN help",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "VPN zero max", "body_format": "markdown", "body": "Reconnect VPN."},
            actor_id="support",
        )
        await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await KnowledgeOperationsService(session).upsert_rollout_policy(
            {"surface": "requester_portal", "max_suggestions": 0},
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "query": "VPN", "surface": "requester_portal"},
            actor_role="requester",
        )

    assert suggestions["suggestions"] == []
    assert suggestions["rollout"]["max_suggestions"] == 0

from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain_ports.knowledge import KnowledgeSuggestionRequest, KnowledgeUnavailable
from tickets import knowledge_provider
from tickets.policy_health_service import PolicyHealthService


pytestmark = pytest.mark.no_db


class _UnavailableKnowledgePort:
    def __init__(self) -> None:
        self.requests: list[KnowledgeSuggestionRequest] = []

    async def suggest(self, request: KnowledgeSuggestionRequest) -> KnowledgeUnavailable:
        self.requests.append(request)
        return KnowledgeUnavailable()


class _EmptyScalarResult:
    def scalars(self) -> _EmptyScalarResult:
        return self

    def all(self) -> list[object]:
        return []


class _EmptyTicketSession:
    async def execute(self, _statement: object) -> _EmptyScalarResult:
        return _EmptyScalarResult()


def test_legacy_attempt_projection_keeps_only_redacted_ticket_metadata() -> None:
    project = getattr(knowledge_provider, "project_legacy_knowledge_attempts", None)

    assert project is not None
    assert project(
        [
            {
                "item_id": "external-secret-item-ref",
                "version_id": "external-secret-version-ref",
                "title": "Private article title",
                "body": "Private article body",
                "content": "Private article content",
                "result": "not_helpful",
                "surface": "requester_portal",
                "visibility_scope": "creator_visible",
                "audience_scope": "creator",
                "occurred_at": "2026-06-08T08:00:00Z",
            },
            {"item_id": "unsanitized-only-item"},
        ]
    ) == [
        {
            "result": "not_helpful",
            "surface": "requester_portal",
            "visibility_scope": "creator_visible",
            "audience_scope": "creator",
            "occurred_at": "2026-06-08T08:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_unavailable_knowledge_port_degrades_to_local_similar_tickets_only() -> None:
    port = _UnavailableKnowledgePort()
    ticket = SimpleNamespace(
        ticket_id="ticket-boundary",
        ticket_code="T-BOUNDARY",
        title="VPN does not connect",
        description="client-supplied body must not become Knowledge state",
        requester_resolution_summary=None,
        resolution_summary=None,
        ticket_type="incident",
        source="requester",
        custom_fields={},
        category_id=None,
        service_id=None,
    )

    suggestions = await knowledge_provider.build_knowledge_suggestions(
        _EmptyTicketSession(),
        ticket,
        (),
        knowledge_port=port,
    )

    assert suggestions.articles == []
    assert suggestions.similar_tickets == []
    assert suggestions.diagnostics.external_provider_status == "not_configured"
    assert len(port.requests) == 1
    assert port.requests[0].query == "VPN does not connect"


def test_policy_health_marks_external_knowledge_coverage_not_configured() -> None:
    item = PolicyHealthService()._catalog_health_item(
        "offering",
        {
            "full_code": "network.vpn",
            "service_code": "network",
            "public_title": "VPN",
            "lifecycle_status": "published",
            "visibility": "public",
        },
        {"status": "ok", "issues": [], "blocking": False},
    )

    assert item["knowledge_coverage_status"] == "not_configured"
    assert item["knowledge_count"] is None
    assert not any(issue.get("policy_kind") == "knowledge" for issue in item["issues"])

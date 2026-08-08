from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from domain_ports import (
    DomainPortContainer,
    KnowledgeFeedbackRequest,
    KnowledgeItemProjection,
    KnowledgeResolutionDraftRequest,
    KnowledgeSearchRequest,
    KnowledgeSuggestionRequest,
    KnowledgeUnavailable,
    UnavailableKnowledgePort,
)


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_unavailable_knowledge_port_never_returns_content() -> None:
    result = await UnavailableKnowledgePort().suggest(KnowledgeSuggestionRequest(query="vpn"))

    assert isinstance(result, KnowledgeUnavailable)
    assert result.status == "unavailable"
    assert result.code == "knowledge_unavailable"
    assert result.items == ()


@pytest.mark.asyncio
async def test_unavailable_knowledge_port_degrades_every_operation() -> None:
    port = UnavailableKnowledgePort()

    results = (
        await port.availability(),
        await port.search(KnowledgeSearchRequest(query="vpn")),
        await port.record_feedback(
            KnowledgeFeedbackRequest(item_ref="opaque-item", feedback_code="helpful")
        ),
        await port.create_resolution_draft(
            KnowledgeResolutionDraftRequest(
                ticket_ref="opaque-ticket",
                resolution_facts=("vpn_profile_recreated",),
            )
        ),
    )

    assert all(isinstance(result, KnowledgeUnavailable) for result in results)
    assert all(result.code == "knowledge_unavailable" for result in results)
    assert all(result.items == () for result in results)


def test_knowledge_requests_are_validated_and_immutable() -> None:
    request = KnowledgeSuggestionRequest(query="vpn", audience_context=("requester",))

    with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
        request.query = "changed"  # type: ignore[misc]

    with pytest.raises(ValueError):
        KnowledgeSuggestionRequest(query="   ")


def test_knowledge_projection_rejects_content_fields() -> None:
    with pytest.raises(ValueError):
        KnowledgeItemProjection(
            item_ref="opaque-item",
            version_ref="opaque-version",
            title="VPN setup",
            summary="Requester-safe summary",
            status="published",
            body="must not cross the boundary",  # type: ignore[call-arg]
        )


def test_container_defaults_to_fresh_unavailable_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.KNOWLEDGE_PORT_MODE", "unavailable")

    first = DomainPortContainer.from_config()
    second = DomainPortContainer.from_config()

    assert isinstance(first.knowledge, UnavailableKnowledgePort)
    assert isinstance(second.knowledge, UnavailableKnowledgePort)
    assert first is not second
    assert first.knowledge is not second.knowledge


def test_container_rejects_unimplemented_knowledge_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.KNOWLEDGE_PORT_MODE", "external")

    with pytest.raises(ValueError, match="KNOWLEDGE_PORT_MODE"):
        DomainPortContainer.from_config()

"""Side-effect-free adapters used until external domain clients exist."""

from __future__ import annotations

from .endpoint import EndpointAvailability
from .knowledge import (
    KnowledgeFeedbackOutcome,
    KnowledgeFeedbackRequest,
    KnowledgeResolutionDraftOutcome,
    KnowledgeResolutionDraftRequest,
    KnowledgeSearchRequest,
    KnowledgeSuggestionRequest,
    KnowledgeUnavailable,
)
from .registry import RegistryAvailability


class UnavailableKnowledgePort:
    async def availability(self) -> KnowledgeUnavailable:
        return KnowledgeUnavailable()

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeUnavailable:
        del request
        return KnowledgeUnavailable()

    async def suggest(self, request: KnowledgeSuggestionRequest) -> KnowledgeUnavailable:
        del request
        return KnowledgeUnavailable()

    async def record_feedback(self, request: KnowledgeFeedbackRequest) -> KnowledgeFeedbackOutcome:
        del request
        return KnowledgeUnavailable()

    async def create_resolution_draft(
        self,
        request: KnowledgeResolutionDraftRequest,
    ) -> KnowledgeResolutionDraftOutcome:
        del request
        return KnowledgeUnavailable()


class UnavailableRegistryPort:
    async def availability(self) -> RegistryAvailability:
        return RegistryAvailability(status="unavailable", code="registry_unavailable")


class UnavailableEndpointPort:
    async def availability(self) -> EndpointAvailability:
        return EndpointAvailability(status="unavailable", code="endpoint_unavailable")

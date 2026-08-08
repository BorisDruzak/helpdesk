"""Public external-domain ports and their fail-closed composition defaults."""

from .container import DomainPortContainer
from .endpoint import EndpointAvailability, EndpointPort
from .knowledge import (
    KnowledgeAvailability,
    KnowledgeAvailabilityOutcome,
    KnowledgeFeedbackOutcome,
    KnowledgeFeedbackRequest,
    KnowledgeFeedbackResult,
    KnowledgeItemProjection,
    KnowledgePort,
    KnowledgeReadResult,
    KnowledgeResolutionDraftOutcome,
    KnowledgeResolutionDraftRequest,
    KnowledgeResolutionDraftResult,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    KnowledgeSuggestionRequest,
    KnowledgeUnavailable,
)
from .registry import RegistryAvailability, RegistryPort
from .unavailable import UnavailableEndpointPort, UnavailableKnowledgePort, UnavailableRegistryPort

__all__ = (
    "DomainPortContainer",
    "EndpointAvailability",
    "EndpointPort",
    "KnowledgeAvailability",
    "KnowledgeAvailabilityOutcome",
    "KnowledgeFeedbackOutcome",
    "KnowledgeFeedbackRequest",
    "KnowledgeFeedbackResult",
    "KnowledgeItemProjection",
    "KnowledgePort",
    "KnowledgeReadResult",
    "KnowledgeResolutionDraftOutcome",
    "KnowledgeResolutionDraftRequest",
    "KnowledgeResolutionDraftResult",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResult",
    "KnowledgeSuggestionRequest",
    "KnowledgeUnavailable",
    "RegistryAvailability",
    "RegistryPort",
    "UnavailableEndpointPort",
    "UnavailableKnowledgePort",
    "UnavailableRegistryPort",
)

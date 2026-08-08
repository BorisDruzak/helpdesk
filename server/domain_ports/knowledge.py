"""Neutral client-side contract for the external Knowledge domain."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


OpaqueRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
SafeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
SafeCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9_.-]*$"),
]


class _ImmutableDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeSearchRequest(_ImmutableDTO):
    query: SafeText
    audience_context: tuple[SafeCode, ...] = ()
    service_ref: OpaqueRef | None = None
    page_size: int | None = Field(default=None, ge=1, le=100)
    cursor: OpaqueRef | None = None
    correlation_id: OpaqueRef | None = None


class KnowledgeSuggestionRequest(KnowledgeSearchRequest):
    """Safe suggestion signals; callers must not pass ticket conversation text."""


class KnowledgeFeedbackRequest(_ImmutableDTO):
    item_ref: OpaqueRef
    version_ref: OpaqueRef | None = None
    feedback_code: SafeCode
    reason_category: SafeCode | None = None
    correlation_id: OpaqueRef | None = None


class KnowledgeResolutionDraftRequest(_ImmutableDTO):
    ticket_ref: OpaqueRef
    item_ref: OpaqueRef | None = None
    version_ref: OpaqueRef | None = None
    resolution_facts: tuple[SafeText, ...] = ()
    correlation_id: OpaqueRef | None = None


class KnowledgeItemProjection(_ImmutableDTO):
    item_ref: OpaqueRef
    version_ref: OpaqueRef
    title: SafeText
    summary: SafeText | None = None
    status: SafeCode


class KnowledgeAvailability(_ImmutableDTO):
    status: Literal["available"] = "available"
    code: SafeCode | None = None


class KnowledgeSearchResult(_ImmutableDTO):
    status: Literal["ok"] = "ok"
    code: SafeCode | None = None
    items: tuple[KnowledgeItemProjection, ...] = ()
    next_cursor: OpaqueRef | None = None
    correlation_id: OpaqueRef | None = None


class KnowledgeFeedbackResult(_ImmutableDTO):
    status: SafeCode
    code: SafeCode | None = None
    feedback_ref: OpaqueRef | None = None
    correlation_id: OpaqueRef | None = None


class KnowledgeResolutionDraftResult(_ImmutableDTO):
    status: SafeCode
    code: SafeCode | None = None
    draft_ref: OpaqueRef | None = None
    summary: SafeText | None = None
    correlation_id: OpaqueRef | None = None


class KnowledgeUnavailable(_ImmutableDTO):
    """Typed degraded outcome that can never carry Knowledge content."""

    status: Literal["unavailable"] = "unavailable"
    code: Literal["knowledge_unavailable"] = "knowledge_unavailable"
    items: tuple[()] = ()


KnowledgeReadResult = KnowledgeSearchResult | KnowledgeUnavailable
KnowledgeFeedbackOutcome = KnowledgeFeedbackResult | KnowledgeUnavailable
KnowledgeResolutionDraftOutcome = KnowledgeResolutionDraftResult | KnowledgeUnavailable
KnowledgeAvailabilityOutcome = KnowledgeAvailability | KnowledgeUnavailable


@runtime_checkable
class KnowledgePort(Protocol):
    async def availability(self) -> KnowledgeAvailabilityOutcome: ...

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeReadResult: ...

    async def suggest(self, request: KnowledgeSuggestionRequest) -> KnowledgeReadResult: ...

    async def record_feedback(self, request: KnowledgeFeedbackRequest) -> KnowledgeFeedbackOutcome: ...

    async def create_resolution_draft(
        self,
        request: KnowledgeResolutionDraftRequest,
    ) -> KnowledgeResolutionDraftOutcome: ...

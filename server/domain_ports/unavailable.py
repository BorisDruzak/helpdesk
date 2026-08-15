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
from .registry_contracts import (
    BindingRevocationRequest,
    DeviceContextOutcome,
    DeviceRef,
    InventoryQualityOutcome,
    DirectorySearchOutcome,
    DirectorySearchText,
    PersonRef,
    RegistrationApprovalRequest,
    RegistrationRequest,
    RegistryCommandResult,
    RegistryReadActor,
    RegistryUnavailable,
    RequesterHistoryOutcome,
    RequesterProfileOutcome,
)


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
    def __init__(self, *, code: str = "registry_unavailable") -> None:
        self._unavailable = RegistryUnavailable(code=code)

    async def availability(self) -> RegistryAvailability:
        return RegistryAvailability(status="unavailable", code=self._unavailable.code)

    async def requester_snapshot(self, person: PersonRef) -> RegistryUnavailable:
        del person
        return self._unavailable

    async def active_binding(self, device: DeviceRef) -> RegistryUnavailable:
        del device
        return self._unavailable

    async def account_status(self, device: DeviceRef) -> RegistryUnavailable:
        del device
        return self._unavailable

    async def audience_projection(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
    ) -> RegistryUnavailable:
        del person, actor
        return self._unavailable

    async def requester_profile(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
    ) -> RequesterProfileOutcome:
        del person, actor
        return self._unavailable

    async def search_people(
        self,
        query: DirectorySearchText,
        *,
        actor: RegistryReadActor,
        limit: int = 20,
    ) -> DirectorySearchOutcome:
        del query, actor, limit
        return self._unavailable

    async def device_context(self, device: DeviceRef) -> DeviceContextOutcome:
        del device
        return self._unavailable

    async def inventory_quality(self) -> InventoryQualityOutcome:
        return self._unavailable

    async def requester_history(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
        limit: int = 50,
    ) -> RequesterHistoryOutcome:
        del person, actor, limit
        return self._unavailable

    def _command_result(self, operation_id: str) -> RegistryCommandResult:
        return RegistryCommandResult(
            operation_id=operation_id,
            status="unavailable",
            code=self._unavailable.code,
            idempotency_status="not_evaluated",
        )

    async def request_registration(self, request: RegistrationRequest) -> RegistryCommandResult:
        return self._command_result(request.operation_id)

    async def approve_registration(
        self,
        request: RegistrationApprovalRequest,
    ) -> RegistryCommandResult:
        return self._command_result(request.operation_id)

    async def revoke_binding(self, request: BindingRevocationRequest) -> RegistryCommandResult:
        return self._command_result(request.operation_id)


class UnavailableEndpointPort:
    async def availability(self) -> EndpointAvailability:
        return EndpointAvailability(status="unavailable", code="endpoint_unavailable")

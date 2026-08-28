"""Side-effect-free adapters used until external domain clients exist."""

from __future__ import annotations

from .endpoint import (
    EndpointAvailability,
    EndpointCapabilitiesOutcome,
    EndpointDeviceOutcome,
    EndpointDeviceRef,
    EndpointOperationCreateOutcome,
    EndpointOperationCreateRequest,
    EndpointOperationReadOutcome,
    EndpointOperationRef,
    EndpointUnavailable,
    OpaqueEndpointRef,
    SafeEndpointCode,
)
from .endpoint_modules import (
    EndpointModuleAvailability,
    EndpointModuleCapabilityCatalogOutcome,
    EndpointModuleValidationOutcome,
    EndpointModuleVersionCreateOutcome,
    EndpointModuleVersionCreateRequest,
    EndpointModuleVersionStateOutcome,
    EndpointModuleListOutcome,
    EndpointModuleOperationCreateOutcome,
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationReadOutcome,
    EndpointModuleOperationRef,
    EndpointModuleReadOutcome,
    EndpointModuleRef,
    EndpointModuleUnavailable,
    EndpointModuleVersionReadOutcome,
    EndpointModuleVersionRef,
)
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
    OnBehalfAuthorizationOutcome,
    OnBehalfCandidatesOutcome,
    OnBehalfLookupText,
    OnBehalfPolicyProjection,
    PersonRef,
    RegistrationApprovalRequest,
    RegistrationRequest,
    RegistryCommandResult,
    RegistryObserverReadContext,
    RegistryReadActor,
    RegistryUnavailable,
    RequesterRef,
    RequesterHistoryOutcome,
    RequesterProfileOutcome,
    RequesterProfileCompletionOutcome,
    TicketParticipantOutcome,
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

    async def ticket_participant(self, person: PersonRef) -> TicketParticipantOutcome:
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

    async def requester_profile_completion(
        self,
        observer: RegistryObserverReadContext,
        person: RequesterRef,
    ) -> RequesterProfileCompletionOutcome:
        del observer, person
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

    async def on_behalf_candidates(
        self,
        *,
        actor: RegistryReadActor,
        creator: RequesterRef,
        policy: OnBehalfPolicyProjection,
        query: DirectorySearchText,
    ) -> OnBehalfCandidatesOutcome:
        del actor, creator, policy, query
        return self._unavailable

    async def authorize_on_behalf(
        self,
        *,
        actor: RegistryReadActor,
        creator: RequesterRef,
        affected: RequesterRef,
        policy: OnBehalfPolicyProjection,
        lookup: OnBehalfLookupText | None = None,
    ) -> OnBehalfAuthorizationOutcome:
        del actor, creator, affected, policy, lookup
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
    def __init__(self, *, code: SafeEndpointCode = "endpoint_unavailable") -> None:
        self._unavailable = EndpointUnavailable(code=code)

    async def availability(self) -> EndpointAvailability:
        return EndpointAvailability(status="unavailable", code=self._unavailable.code)

    async def read_device(self, device: EndpointDeviceRef) -> EndpointDeviceOutcome:
        del device
        return self._unavailable

    async def list_capabilities(self, device: EndpointDeviceRef) -> EndpointCapabilitiesOutcome:
        del device
        return self._unavailable

    async def create_operation(
        self,
        device: EndpointDeviceRef,
        request: EndpointOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointOperationCreateOutcome:
        del device, request, idempotency_key
        return self._unavailable

    async def read_operation(self, operation: EndpointOperationRef) -> EndpointOperationReadOutcome:
        del operation
        return self._unavailable


class UnavailableEndpointModulePort:
    def __init__(self, *, code: SafeEndpointCode = "endpoint_module_unavailable") -> None:
        self._unavailable = EndpointModuleUnavailable(code=code)

    async def availability(self) -> EndpointModuleAvailability:
        return EndpointModuleAvailability(status="unavailable", code=self._unavailable.code)

    async def list_recipe_capabilities(self) -> EndpointModuleCapabilityCatalogOutcome:
        return self._unavailable

    async def list_modules(self) -> EndpointModuleListOutcome:
        return self._unavailable

    async def read_module(self, module: EndpointModuleRef) -> EndpointModuleReadOutcome:
        del module
        return self._unavailable

    async def read_module_version(
        self,
        version: EndpointModuleVersionRef,
    ) -> EndpointModuleVersionReadOutcome:
        del version
        return self._unavailable

    async def create_module_version(
        self, request: EndpointModuleVersionCreateRequest
    ) -> EndpointModuleVersionCreateOutcome:
        del request
        return self._unavailable

    async def validate_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleValidationOutcome:
        del version
        return self._unavailable

    async def publish_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleVersionStateOutcome:
        del version
        return self._unavailable

    async def deprecate_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleVersionStateOutcome:
        del version
        return self._unavailable

    async def create_operation(
        self,
        request: EndpointModuleOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointModuleOperationCreateOutcome:
        del request, idempotency_key
        return self._unavailable

    async def read_operation(
        self,
        operation: EndpointModuleOperationRef,
    ) -> EndpointModuleOperationReadOutcome:
        del operation
        return self._unavailable

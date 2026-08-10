"""Neutral dependency-injection seam for the Registry domain."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from .registry_contracts import (
    AccountStatusOutcome,
    ActiveBindingOutcome,
    BindingRef,
    BindingRevocationRequest,
    DeviceRef,
    OpaqueRegistryRef,
    PersonRef,
    RegistrationApprovalRequest,
    RegistrationRequest,
    RegistryCommandResult,
    RequesterRef,
    RequesterDisplayName,
    RequesterSnapshot,
    RequesterSnapshotOutcome,
    AudienceProjectionOutcome,
    requester_persistence_values,
)


class RegistryAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available", "unavailable"]
    code: str | None = None


@runtime_checkable
class RegistryPort(Protocol):
    async def availability(self) -> RegistryAvailability: ...

    async def requester_snapshot(self, person: PersonRef) -> RequesterSnapshotOutcome: ...

    async def active_binding(self, device: DeviceRef) -> ActiveBindingOutcome: ...

    async def account_status(self, device: DeviceRef) -> AccountStatusOutcome: ...

    async def audience_projection(self, person: PersonRef) -> AudienceProjectionOutcome: ...

    async def request_registration(self, request: RegistrationRequest) -> RegistryCommandResult: ...

    async def approve_registration(
        self,
        request: RegistrationApprovalRequest,
    ) -> RegistryCommandResult: ...

    async def revoke_binding(self, request: BindingRevocationRequest) -> RegistryCommandResult: ...

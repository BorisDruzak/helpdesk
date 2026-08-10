"""Frozen, redacted contracts exchanged with the Registry domain."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


# Opaque references are never parsed, trimmed, case-folded or otherwise
# normalized by Helpdesk. Length validation is only a transport-safety bound.
OpaqueRegistryRef = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
RequesterDisplayName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=256),
]
SafeRegistryCode = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    ),
]


class _ImmutableRegistryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PersonRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class DeviceRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class BindingRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class RegistrationRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class AudienceRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class ActorRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class RequesterRef(_ImmutableRegistryDTO):
    """Canonical opaque requester identity retained by Helpdesk history."""

    external_id: OpaqueRegistryRef


class RequesterSnapshot(_ImmutableRegistryDTO):
    """Minimal immutable display projection, deliberately excluding profile data."""

    person: PersonRef
    display_name: RequesterDisplayName


def requester_persistence_values(
    *,
    requester_ref: RequesterRef | None,
    requester_snapshot: RequesterSnapshot | None,
) -> dict[str, str | dict[str, object] | None]:
    """Return only validated, JSON-safe requester persistence fields."""

    if requester_ref is not None and not isinstance(requester_ref, RequesterRef):
        raise TypeError("requester_ref must be a RequesterRef")
    if requester_snapshot is not None and not isinstance(requester_snapshot, RequesterSnapshot):
        raise TypeError("requester_snapshot must be a RequesterSnapshot")
    if (requester_ref is None) != (requester_snapshot is None):
        raise ValueError("requester_ref and requester_snapshot must both be set or both be omitted")

    validated_ref = (
        RequesterRef.model_validate(requester_ref.model_dump(mode="python"))
        if requester_ref is not None
        else None
    )
    validated_snapshot = (
        RequesterSnapshot.model_validate(requester_snapshot.model_dump(mode="python"))
        if requester_snapshot is not None
        else None
    )
    if (
        validated_ref is not None
        and validated_snapshot is not None
        and validated_snapshot.person.external_id != validated_ref.external_id
    ):
        raise ValueError("requester snapshot person does not match requester ref")
    return {
        "requester_external_ref": validated_ref.external_id if validated_ref is not None else None,
        "requester_snapshot_json": (
            validated_snapshot.model_dump(mode="json") if validated_snapshot is not None else None
        ),
    }


class RegistryUnavailable(_ImmutableRegistryDTO):
    status: Literal["unavailable"] = "unavailable"
    code: SafeRegistryCode = "registry_unavailable"


class RegistryNotFound(_ImmutableRegistryDTO):
    status: Literal["not_found"] = "not_found"
    code: SafeRegistryCode


class ActiveBindingProjection(_ImmutableRegistryDTO):
    device: DeviceRef
    binding: BindingRef
    requester: RequesterRef
    requester_snapshot: RequesterSnapshot
    relationship_type: SafeRegistryCode
    status: Literal["active"] = "active"
    source: Literal["local_authoritative", "external_authoritative"]


class AccountStatusProjection(_ImmutableRegistryDTO):
    device: DeviceRef
    status: SafeRegistryCode
    active_binding: ActiveBindingProjection | None = None
    requires_user_action: bool = False
    requires_admin_action: bool = False
    code: SafeRegistryCode | None = None
    source: Literal["local_authoritative", "external_authoritative"]


class AudienceProjection(_ImmutableRegistryDTO):
    requester: RequesterRef
    audiences: tuple[AudienceRef, ...] = ()
    warning_codes: tuple[SafeRegistryCode, ...] = ()
    source: Literal["local_authoritative", "external_authoritative"]


class RegistrationRequest(_ImmutableRegistryDTO):
    operation_id: OpaqueRegistryRef
    device: DeviceRef
    requester: RequesterRef | None = None
    requester_snapshot: RequesterSnapshot | None = None
    relationship_type: SafeRegistryCode = "primary_user"

    @model_validator(mode="after")
    def validate_requester_pair(self) -> "RegistrationRequest":
        if (self.requester is None) != (self.requester_snapshot is None):
            raise ValueError("requester and requester_snapshot must both be set or both be omitted")
        if (
            self.requester is not None
            and self.requester_snapshot is not None
            and self.requester.external_id != self.requester_snapshot.person.external_id
        ):
            raise ValueError("requester snapshot person does not match requester ref")
        return self


class RegistrationApprovalRequest(_ImmutableRegistryDTO):
    operation_id: OpaqueRegistryRef
    registration: RegistrationRef
    actor: ActorRef | None = None
    replace_existing: bool = False


class BindingRevocationRequest(_ImmutableRegistryDTO):
    operation_id: OpaqueRegistryRef
    binding: BindingRef
    reason_code: SafeRegistryCode
    actor: ActorRef | None = None


class RegistryCommandResult(_ImmutableRegistryDTO):
    operation_id: OpaqueRegistryRef
    status: Literal["accepted", "applied", "replayed", "unavailable"]
    code: SafeRegistryCode | None = None
    registration: RegistrationRef | None = None
    binding: BindingRef | None = None
    idempotency_status: Literal["new", "replayed", "not_evaluated"]


RequesterSnapshotOutcome = RequesterSnapshot | RegistryNotFound | RegistryUnavailable
ActiveBindingOutcome = ActiveBindingProjection | RegistryNotFound | RegistryUnavailable
AccountStatusOutcome = AccountStatusProjection | RegistryUnavailable
AudienceProjectionOutcome = AudienceProjection | RegistryNotFound | RegistryUnavailable

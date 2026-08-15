"""Frozen, redacted contracts exchanged with the Registry domain."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


# Opaque references are never parsed, trimmed, case-folded or otherwise
# normalized by Helpdesk. Length validation is only a transport-safety bound.
OpaqueRegistryRef = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
RequesterDisplayName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=256),
]
RegistryDisplayLabel = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=256),
]
TicketParticipantText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]
DirectorySearchText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120),
]
OnBehalfLookupText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=240),
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
MAX_REGISTRY_AUDIENCES = 100
MAX_DIRECTORY_RESULTS = 50
MAX_ON_BEHALF_CANDIDATES = 10
MAX_REQUESTER_HISTORY_EVENTS = 100


class _ImmutableRegistryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PersonRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class DepartmentRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class LocationRef(_ImmutableRegistryDTO):
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


class RegistryReadActor(_ImmutableRegistryDTO):
    """Verified Helpdesk actor context for Registry visibility decisions.

    Composition code may build this only from trusted authentication context,
    never from an HTTP body or a client supplied role. ``requester`` scopes a
    requester actor to their own Registry person; support and admin actors are
    authorized by their verified role and the Registry's own access-group
    resolver.
    """

    actor: ActorRef
    role: Literal["admin", "support", "user"]
    requester: RequesterRef | None = None


class RequesterSnapshot(_ImmutableRegistryDTO):
    """Minimal immutable display projection, deliberately excluding profile data."""

    person: PersonRef
    display_name: RequesterDisplayName


class TicketParticipantProjection(_ImmutableRegistryDTO):
    """Purpose-bound participant fields persisted in ``ticket_context_v1``."""

    person: PersonRef
    display_name: TicketParticipantText | None = None
    full_name: TicketParticipantText | None = None
    email: TicketParticipantText | None = None
    department: DepartmentRef | None = None
    location: LocationRef | None = None
    source: Literal["local_authoritative", "external_authoritative"]


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


class RegistryInvalidProjection(_ImmutableRegistryDTO):
    """The authoritative Registry returned an unusable redacted projection."""

    status: Literal["invalid"] = "invalid"
    code: SafeRegistryCode = "registry_projection_invalid"


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

    @model_validator(mode="after")
    def validate_bounded_collections(self) -> "AudienceProjection":
        if len(self.audiences) > MAX_REGISTRY_AUDIENCES:
            raise ValueError("audience projection exceeds maximum item count")
        if len(self.warning_codes) > MAX_REGISTRY_AUDIENCES:
            raise ValueError("audience projection exceeds maximum warning count")
        return self


class DirectoryPersonProjection(_ImmutableRegistryDTO):
    """Search-safe person result: no contacts, identities or local metadata."""

    requester: RequesterRef
    display_name: RequesterDisplayName
    department_label: RegistryDisplayLabel | None = None
    location_label: RegistryDisplayLabel | None = None
    status: SafeRegistryCode
    source: Literal["local_authoritative", "external_authoritative"]


class DirectorySearchProjection(_ImmutableRegistryDTO):
    items: tuple[DirectoryPersonProjection, ...] = ()
    source: Literal["local_authoritative", "external_authoritative"]

    @model_validator(mode="after")
    def validate_bounded_items(self) -> "DirectorySearchProjection":
        if len(self.items) > MAX_DIRECTORY_RESULTS:
            raise ValueError("directory projection exceeds maximum item count")
        return self


class OnBehalfPolicyProjection(_ImmutableRegistryDTO):
    """Server-owned requester on-behalf policy snapshot."""

    allowed: bool = True
    scope: SafeRegistryCode = "same_department_or_privileged"
    reason_required: bool = False


class OnBehalfCandidateProjection(_ImmutableRegistryDTO):
    """Purpose-bound candidate fields already exposed by the requester API."""

    person: RequesterRef
    display_name: TicketParticipantText
    full_name: TicketParticipantText | None = None
    email: TicketParticipantText | None = None
    department: DepartmentRef | None = None
    department_label: TicketParticipantText | None = None
    location: LocationRef | None = None
    location_label: TicketParticipantText | None = None
    source: Literal["local_authoritative", "external_authoritative"]


class OnBehalfCandidatesProjection(_ImmutableRegistryDTO):
    items: tuple[OnBehalfCandidateProjection, ...] = ()
    source: Literal["local_authoritative", "external_authoritative"]

    @model_validator(mode="after")
    def validate_bounded_items(self) -> "OnBehalfCandidatesProjection":
        if len(self.items) > MAX_ON_BEHALF_CANDIDATES:
            raise ValueError("on-behalf candidate projection exceeds maximum item count")
        return self


class OnBehalfAllowed(_ImmutableRegistryDTO):
    status: Literal["allowed"] = "allowed"
    code: Literal["registry_on_behalf_allowed"] = "registry_on_behalf_allowed"
    affected: RequesterRef
    source: Literal["local_authoritative", "external_authoritative"]


class OnBehalfDenied(_ImmutableRegistryDTO):
    status: Literal["denied"] = "denied"
    code: Literal[
        "registry_actor_forbidden",
        "registry_on_behalf_not_allowed",
        "registry_on_behalf_scope_denied",
    ]


class RequesterProfileProjection(_ImmutableRegistryDTO):
    """Requester profile bounded to labels safe for Helpdesk display."""

    requester: RequesterRef
    display_name: RequesterDisplayName
    department_label: RegistryDisplayLabel | None = None
    location_label: RegistryDisplayLabel | None = None
    status: SafeRegistryCode
    source: Literal["local_authoritative", "external_authoritative"]


class DeviceContextProjection(_ImmutableRegistryDTO):
    """Inventory-safe device context without asset, serial or owner identifiers."""

    device: DeviceRef
    display_name: RegistryDisplayLabel
    asset_type: SafeRegistryCode
    asset_status: SafeRegistryCode
    requester: RequesterRef | None = None
    requester_snapshot: RequesterSnapshot | None = None
    department_label: RegistryDisplayLabel | None = None
    location_label: RegistryDisplayLabel | None = None
    source: Literal["local_authoritative", "external_authoritative"]

    @model_validator(mode="after")
    def validate_requester_pair(self) -> "DeviceContextProjection":
        if (self.requester is None) != (self.requester_snapshot is None):
            raise ValueError("requester and requester_snapshot must both be set or both be omitted")
        if (
            self.requester is not None
            and self.requester_snapshot is not None
            and self.requester.external_id != self.requester_snapshot.person.external_id
        ):
            raise ValueError("requester snapshot person does not match requester ref")
        return self


class InventoryQualityProjection(_ImmutableRegistryDTO):
    """Bounded aggregate for inventory-quality monitoring, without asset detail."""

    active_pc_without_location_count: int = Field(strict=True, ge=0, le=2_147_483_647)
    source: Literal["local_authoritative", "external_authoritative"]


class RegistryHistoryEventProjection(_ImmutableRegistryDTO):
    event_type: SafeRegistryCode
    occurred_at: datetime
    device: DeviceRef | None = None
    relationship_type: SafeRegistryCode | None = None
    status: SafeRegistryCode | None = None
    source: Literal["local_authoritative", "external_authoritative"]


class RequesterHistoryProjection(_ImmutableRegistryDTO):
    requester: RequesterRef
    items: tuple[RegistryHistoryEventProjection, ...] = ()
    source: Literal["local_authoritative", "external_authoritative"]

    @model_validator(mode="after")
    def validate_bounded_items(self) -> "RequesterHistoryProjection":
        if len(self.items) > MAX_REQUESTER_HISTORY_EVENTS:
            raise ValueError("requester history projection exceeds maximum item count")
        return self


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


RequesterSnapshotOutcome = RequesterSnapshot | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
TicketParticipantOutcome = TicketParticipantProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
ActiveBindingOutcome = ActiveBindingProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
AccountStatusOutcome = AccountStatusProjection | RegistryUnavailable | RegistryInvalidProjection
AudienceProjectionOutcome = AudienceProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
RequesterProfileOutcome = RequesterProfileProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
DirectorySearchOutcome = DirectorySearchProjection | RegistryUnavailable | RegistryInvalidProjection
OnBehalfCandidatesOutcome = (
    OnBehalfCandidatesProjection
    | OnBehalfDenied
    | RegistryNotFound
    | RegistryUnavailable
    | RegistryInvalidProjection
)
OnBehalfAuthorizationOutcome = (
    OnBehalfAllowed
    | OnBehalfDenied
    | RegistryNotFound
    | RegistryUnavailable
    | RegistryInvalidProjection
)
DeviceContextOutcome = DeviceContextProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection
InventoryQualityOutcome = InventoryQualityProjection | RegistryUnavailable | RegistryInvalidProjection
RequesterHistoryOutcome = RequesterHistoryProjection | RegistryNotFound | RegistryUnavailable | RegistryInvalidProjection

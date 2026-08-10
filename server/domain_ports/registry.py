"""Neutral dependency-injection seam for the future Registry domain."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, StringConstraints


# Helpdesk never parses or normalizes Registry identifiers.  They are opaque
# references supplied by the Registry boundary and intentionally have no local
# Registry primary-key or foreign-key meaning.
OpaqueRegistryRef = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
RequesterDisplayName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=256),
]


class _ImmutableRegistryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PersonRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class DeviceRef(_ImmutableRegistryDTO):
    external_id: OpaqueRegistryRef


class BindingRef(_ImmutableRegistryDTO):
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
    """Return only validated, JSON-safe requester persistence fields.

    Repository boundaries accept DTO instances rather than dictionaries or
    local ORM rows so that callers cannot write a mutable Registry profile or
    secret-bearing payload into Helpdesk history.
    """

    if requester_ref is not None and not isinstance(requester_ref, RequesterRef):
        raise TypeError("requester_ref must be a RequesterRef")
    if requester_snapshot is not None and not isinstance(requester_snapshot, RequesterSnapshot):
        raise TypeError("requester_snapshot must be a RequesterSnapshot")

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
    return {
        "requester_external_ref": validated_ref.external_id if validated_ref is not None else None,
        "requester_snapshot_json": (
            validated_snapshot.model_dump(mode="json") if validated_snapshot is not None else None
        ),
    }


class RegistryAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available", "unavailable"]
    code: str | None = None


@runtime_checkable
class RegistryPort(Protocol):
    async def availability(self) -> RegistryAvailability: ...

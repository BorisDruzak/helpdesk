"""Bounded, immutable safe service Context projections."""
from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from .endpoint_context_sections import (
    _ImmutableContextDTO, BaselineSectionsV1, HealthSectionsV1, NetworkSectionsV1,
    InventorySectionsV1, SessionSectionsV1, ContextWarningCodeV1, DeviceContextDiffV1,
)

SafeContextProfile = Literal["baseline_v1", "health_v1", "network_v1", "inventory_v1", "session_v1"]
HistoryContextProfile = Literal["baseline_v1", "inventory_v1"]
ContextCollectionStatus = Literal["requested", "queued", "delivered", "collecting", "result_received", "validated", "completed", "failed", "expired"]
SAFE_CONTEXT_PROFILES = ("baseline_v1", "health_v1", "network_v1", "inventory_v1", "session_v1")
_SECTION_MODELS = {"baseline_v1": BaselineSectionsV1, "health_v1": HealthSectionsV1,
    "network_v1": NetworkSectionsV1, "inventory_v1": InventorySectionsV1, "session_v1": SessionSectionsV1}


class EndpointContextDevice(_ImmutableContextDTO):
    id: UUID
    device_identifier: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=256)
    retired_at: AwareDatetime | None
    last_seen_at: AwareDatetime | None
    online: bool = Field(strict=True)


class EndpointProfileAvailability(_ImmutableContextDTO):
    profile: SafeContextProfile
    status: ContextCollectionStatus
    last_collected_at: AwareDatetime | None


class EndpointInventorySummary(_ImmutableContextDTO):
    hostname: str | None = Field(default=None, max_length=256)
    platform: Literal["linux", "windows"] | None = None
    os_name: str | None = Field(default=None, max_length=256)
    os_version: str | None = Field(default=None, max_length=256)
    architecture: Literal["x86_64", "aarch64"] | None = None
    manufacturer: str | None = Field(default=None, max_length=256)
    model: str | None = Field(default=None, max_length=256)
    serial_number: str | None = Field(default=None, max_length=256)
    cpu_model: str | None = Field(default=None, max_length=256)
    memory_bytes: int | None = Field(default=None, ge=1, strict=True)


class EndpointFleetItem(_ImmutableContextDTO):
    device: EndpointContextDevice
    profiles: tuple[EndpointProfileAvailability, ...] = Field(max_length=5)
    inventory_summary: EndpointInventorySummary | None

    @model_validator(mode="after")
    def unique_profiles(self):
        if len({p.profile for p in self.profiles}) != len(self.profiles):
            raise ValueError("duplicate profiles")
        if self.inventory_summary is not None and not any(p.profile == "inventory_v1" for p in self.profiles):
            raise ValueError("inventory requires current profile")
        return self


class EndpointDeviceFleet(_ImmutableContextDTO):
    items: tuple[EndpointFleetItem, ...] = Field(max_length=250)
    next_cursor: UUID | None

    @model_validator(mode="after")
    def ordered_page(self):
        ids = [item.device.id for item in self.items]
        if ids != sorted(set(ids)):
            raise ValueError("fleet identities must be unique and ordered")
        if self.next_cursor is not None and (not ids or self.next_cursor != ids[-1]):
            raise ValueError("invalid fleet cursor")
        return self


class EndpointContextSnapshot(_ImmutableContextDTO):
    id: UUID
    profile: SafeContextProfile
    collected_at: AwareDatetime
    semantic_hash: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    warnings: tuple[ContextWarningCodeV1, ...] = Field(max_length=16)
    sections: BaselineSectionsV1 | HealthSectionsV1 | NetworkSectionsV1 | InventorySectionsV1 | SessionSectionsV1

    @model_validator(mode="before")
    @classmethod
    def exact_sections(cls, value):
        if isinstance(value, Mapping):
            model = _SECTION_MODELS.get(value.get("profile"))
            if model is None:
                raise ValueError("unsafe profile")
            value = {**value, "sections": model.model_validate(value.get("sections"))}
        return value


class EndpointDeviceContext(_ImmutableContextDTO):
    device: EndpointContextDevice
    profiles: tuple[EndpointProfileAvailability, ...] = Field(max_length=5)
    snapshots: tuple[EndpointContextSnapshot, ...] = Field(max_length=5)

    @model_validator(mode="after")
    def unique_profiles(self):
        for items in (self.profiles, self.snapshots):
            if len({p.profile for p in items}) != len(items):
                raise ValueError("duplicate profiles")
        if not {p.profile for p in self.snapshots} <= {p.profile for p in self.profiles}:
            raise ValueError("snapshot without profile")
        return self


class EndpointContextCollection(_ImmutableContextDTO):
    id: UUID
    device_id: UUID
    profile: SafeContextProfile
    status: ContextCollectionStatus
    requested_at: AwareDatetime
    result_received_at: AwareDatetime | None
    completed_at: AwareDatetime | None
    failure_code: str | None = Field(max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")


class EndpointCollectionDetails(_ImmutableContextDTO):
    collection: EndpointContextCollection
    snapshot: EndpointContextSnapshot | None

    @model_validator(mode="after")
    def exact_profile(self):
        if self.snapshot is not None and self.snapshot.profile != self.collection.profile:
            raise ValueError("collection snapshot profile mismatch")
        return self


class EndpointContextHistory(_ImmutableContextDTO):
    snapshots: tuple[EndpointContextSnapshot, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_snapshots(self):
        if len({s.id for s in self.snapshots}) != len(self.snapshots):
            raise ValueError("duplicate snapshots")
        return self


EndpointContextComparison = DeviceContextDiffV1

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


WarningItem = dict[str, str]


@dataclass(frozen=True, slots=True)
class EffectiveIdentity:
    actor_id: str | None
    actor_role: str
    identity_source: str
    person: dict[str, Any] | None = None
    department_path: list[dict[str, Any]] = field(default_factory=list)
    location: dict[str, Any] | None = None
    access_groups: list[str] = field(default_factory=list)
    audience_groups: list[Any] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "identity_source": self.identity_source,
            "person": self.person,
            "department_path": self.department_path,
            "location": self.location,
            "access_groups": self.access_groups,
            "audience_groups": self.audience_groups,
            "warnings": self.warnings,
            "sources": self.sources,
        }


@dataclass(frozen=True, slots=True)
class EffectiveAudience:
    person_id: str | None
    actor_id: str | None
    actor_role: str
    department_path: list[dict[str, Any]] = field(default_factory=list)
    location: dict[str, Any] | None = None
    access_groups: list[str] = field(default_factory=list)
    audience_groups: list[Any] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "department_path": self.department_path,
            "location": self.location,
            "access_groups": self.access_groups,
            "audience_groups": self.audience_groups,
            "warnings": self.warnings,
            "sources": self.sources,
        }

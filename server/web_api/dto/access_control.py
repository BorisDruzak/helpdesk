from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AccessPermissionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    description: str
    risk: str = "normal"


class AccessPermissionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    permissions: list[AccessPermissionItem] = Field(default_factory=list)


class AccessRoleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    permissions: list[str] = Field(default_factory=list)


class AccessCatalogPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    roles: list[AccessRoleItem] = Field(default_factory=list)
    groups: list[AccessPermissionGroup] = Field(default_factory=list)


class AccessQueueMembershipItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: int
    queue_code: str
    queue_name: str
    role_in_queue: str | None = None


class AccessEffectivePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    actor_role: str
    role_label: str
    permissions: list[str] = Field(default_factory=list)
    workspaces: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    queues: list[AccessQueueMembershipItem] = Field(default_factory=list)
    sources: dict[str, str | list[str]] = Field(default_factory=dict)


class AccessUserItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    role_label: str
    is_active: bool
    groups: list[str] = Field(default_factory=list)
    queue_count: int = 0


class AccessQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: int
    queue_code: str
    queue_name: str
    is_active: bool
    members_count: int = 0


class AccessSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    users: list[AccessUserItem] = Field(default_factory=list)
    queues: list[AccessQueueItem] = Field(default_factory=list)
    access_groups: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

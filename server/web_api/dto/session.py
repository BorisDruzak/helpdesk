from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebSessionCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_registration_enabled: bool
    sso_enabled: bool = False


class WebSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    auth_type: str
    login_method: Literal["password", "oidc"] = "password"
    worktime_portal_url: str | None = None
    default_workspace: str | None = None
    available_workspaces: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    permissions_version: str = ""


class WebSessionLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    password: str
    expected_role: str | None = None


class WebSessionRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    password: str
    password_repeat: str


class WebSessionRegisterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    next_path: str


class WebRequesterRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    patronymic: str = Field(default="", max_length=100)
    department_id: str = Field(min_length=1, max_length=80)
    phone: str = Field(default="", max_length=80)
    internal_extension: str = Field(default="", max_length=80)
    position: str = Field(default="", max_length=160)
    workplace_label: str = Field(default="", max_length=160)
    preferred_contact_method: str = Field(default="", max_length=80)
    custom_fields: dict[str, str | bool | int | float | None] = Field(default_factory=dict, max_length=50)
    password: str = Field(max_length=1024)
    password_repeat: str = Field(max_length=1024)


class WebSessionLogoutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool

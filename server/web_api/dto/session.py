from pydantic import BaseModel, ConfigDict, Field


class WebSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    auth_type: str
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
    device_link_code: str | None = None


class WebSessionRegisterDeviceLinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    purpose: str
    expires_at: str | None = None


class WebSessionRegisterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    next_path: str
    device_link: WebSessionRegisterDeviceLinkPayload | None = None


class WebSessionLogoutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool

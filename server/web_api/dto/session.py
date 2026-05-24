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


class WebSessionLogoutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool

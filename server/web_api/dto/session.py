from pydantic import BaseModel, ConfigDict


class WebSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_login: str
    actor_role: str
    auth_type: str


class WebSessionLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    password: str


class WebSessionLogoutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, field_validator


class UserAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    user_login: str = Field(min_length=1, max_length=100)
    password: SecretStr | None = None
    actor_role: Literal["user", "support", "admin", "auditor"]
    is_active: StrictBool
    queue_ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(max_length=1000)
    group_ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(max_length=1000)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("user_login", "reason")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be empty")
        return value

    @field_validator("user_login")
    @classmethod
    def valid_login(cls, value: str) -> str:
        if any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError("Login must not contain whitespace or control characters")
        return value

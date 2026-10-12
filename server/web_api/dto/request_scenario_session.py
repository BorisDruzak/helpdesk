"""Requester session commands carry no actor, policy or version authority."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from web_api.dto.request_scenario import Key, StrictModel


class SessionStart(StrictModel):
    entry_point_key: Key | None = None
    offering_full_code: Annotated[str, Field(max_length=220, pattern=r"^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")]


class SessionRevision(StrictModel):
    revision: int = Field(ge=1)


class SessionBack(SessionRevision):
    target_block_id: Key


class SessionTicketContext(SessionRevision):
    device_id: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    device_scope: Literal["none"] | None = None

    @model_validator(mode="after")
    def device_choice(self):
        if self.device_id and self.device_scope:
            raise ValueError("Select a device or request without a device")
        return self


class SessionSubmit(SessionTicketContext):
    confirm: Literal[True]

    @model_validator(mode="before")
    @classmethod
    def explicit_confirmation(cls, raw):
        if isinstance(raw, dict) and raw.get("confirm") is not True:
            raise ValueError("Explicit boolean confirmation is required")
        return raw

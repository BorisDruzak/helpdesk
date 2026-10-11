"""Requester session commands carry no actor, policy or version authority."""
from typing import Annotated

from pydantic import Field

from web_api.dto.request_scenario import Key, StrictModel


class SessionStart(StrictModel):
    offering_full_code: Annotated[str, Field(max_length=220, pattern=r"^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")]


class SessionRevision(StrictModel):
    revision: int = Field(ge=1)


class SessionBack(SessionRevision):
    target_block_id: Key

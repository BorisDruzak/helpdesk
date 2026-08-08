"""Neutral dependency-injection seam for the Endpoint domain."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class EndpointAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available", "unavailable"]
    code: str | None = None


@runtime_checkable
class EndpointPort(Protocol):
    async def availability(self) -> EndpointAvailability: ...

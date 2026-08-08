"""Neutral dependency-injection seam for the future Registry domain."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class RegistryAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available", "unavailable"]
    code: str | None = None


@runtime_checkable
class RegistryPort(Protocol):
    async def availability(self) -> RegistryAvailability: ...

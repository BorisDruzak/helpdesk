from __future__ import annotations

from typing import Generic, TypeVar

from aiohttp import web
from pydantic import BaseModel, ConfigDict


PayloadT = TypeVar("PayloadT")


class SuccessResponse(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(extra="forbid")

    status: str = "success"
    data: PayloadT


def json_model_response(model: BaseModel, *, status: int = 200) -> web.Response:
    return web.json_response(model.model_dump(mode="json"), status=status)

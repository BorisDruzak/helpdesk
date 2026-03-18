"""
Focused components for command_result pipeline decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from websocket.command_result_parser import normalize_command_result_payload


@dataclass
class NormalizedCommandResult:
    command_id: Optional[str]
    status: str
    error_info: dict[str, Any]
    data_payload: dict[str, Any]
    meta_info: dict[str, Any]
    payload: dict[str, Any]
    is_malformed: bool


class CommandResultNormalizer:
    def normalize(self, message: dict[str, Any]) -> NormalizedCommandResult:
        raw_payload = message.get("payload")
        normalized = normalize_command_result_payload(raw_payload)
        meta_info = normalized["meta"]
        command_id = message.get("request_id") or meta_info.get("command_id")
        return NormalizedCommandResult(
            command_id=command_id,
            status=normalized["status"],
            error_info=normalized["error"],
            data_payload=normalized["data"],
            meta_info=meta_info,
            payload={
                "status": normalized["status"],
                "error": normalized["error"],
                "data": normalized["data"],
                "meta": meta_info,
            },
            is_malformed=normalized["is_malformed"],
        )


class CommandResultFutureResolver:
    def resolve(self, pending_futures: dict[str, Any], command_id: Optional[str], result_data: dict[str, Any]) -> bool:
        if not command_id:
            return False
        future = pending_futures.get(command_id)
        if not future or future.done():
            return False
        future.set_result(result_data)
        del pending_futures[command_id]
        logger.info(f"[command_result] Future resolved via resolver: command_id={command_id}")
        return True

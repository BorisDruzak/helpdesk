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

    def resolve_from_context(self, command_id: Optional[str], result_data: dict[str, Any], ctx: Any) -> bool:
        if not command_id:
            return False
        agent_id = getattr(ctx, "agent_id", None)
        state = getattr(ctx, "state", None)
        if not agent_id or state is None:
            return False
        agent_info = state.get_agent(agent_id)
        if not agent_info:
            return False
        pending_futures = agent_info.get("metadata", {}).get("pending_command_futures", {})
        return self.resolve(pending_futures, command_id, result_data)


@dataclass
class CommandResultLifecycleOutcome:
    processed: bool
    command_id: Optional[str]
    status: str


class CommandResultArtifactHandler:
    """
    Handles payload artifacts independently from lifecycle updates.
    """

    async def post_process(self, normalized: NormalizedCommandResult, ctx: Any) -> None:
        artifacts = normalized.data_payload.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return
        state = getattr(ctx, "state", None)
        if state is None:
            return
        cache_key = "_recent_command_artifacts"
        cache = getattr(state, cache_key, None)
        if cache is None:
            cache = {}
            setattr(state, cache_key, cache)
        if normalized.command_id:
            cache[normalized.command_id] = artifacts
            # Bound memory for long-lived process.
            if len(cache) > 500:
                for key in list(cache.keys())[:200]:
                    cache.pop(key, None)


class CommandResultEventPublisher:
    """
    Publishes operation/result side effects after lifecycle processing.
    """

    async def publish_after_lifecycle(
        self,
        normalized: NormalizedCommandResult,
        ctx: Any,
        lifecycle_outcome: CommandResultLifecycleOutcome,
    ) -> None:
        if not lifecycle_outcome.processed or not lifecycle_outcome.command_id:
            return
        state = getattr(ctx, "state", None)
        if state is None:
            return
        cache_key = "_recent_operation_updates"
        updates = getattr(state, cache_key, None)
        if updates is None:
            updates = {}
            setattr(state, cache_key, updates)
        updates[lifecycle_outcome.command_id] = {
            "status": lifecycle_outcome.status,
            "source": "command_result_pipeline",
            "meta": normalized.meta_info,
        }
        if len(updates) > 1000:
            for key in list(updates.keys())[:400]:
                updates.pop(key, None)

"""
Focused components for command_result pipeline decomposition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from websocket.command_result_parser import normalize_command_result_payload


@dataclass
class NormalizedCommandResult:
    command_id: Optional[str]
    status: str
    lifecycle_status: str
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
        status = normalized["status"]
        lifecycle_status = status
        if status == "success":
            lifecycle_status = "succeeded"
        elif status == "error":
            lifecycle_status = "failed"
        elif status == "consent_required":
            lifecycle_status = "waiting_consent"
        return NormalizedCommandResult(
            command_id=command_id,
            status=status,
            lifecycle_status=lifecycle_status,
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
    operation_id: Optional[str] = None
    operation_kind: Optional[str] = None
    ticket_id: Optional[str] = None
    trace_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


class CommandResultArtifactHandler:
    """
    Handles payload artifacts independently from lifecycle updates.
    """

    async def _sync_command_side_effects(
        self,
        normalized: NormalizedCommandResult,
        ctx: Any,
        lifecycle_outcome: CommandResultLifecycleOutcome,
    ) -> None:
        if lifecycle_outcome.status != "succeeded" or not lifecycle_outcome.operation_id:
            return
        device_id = getattr(ctx, "agent_id", None)
        if not device_id:
            return
        observations = normalized.data_payload.get("observations")
        if not isinstance(observations, dict):
            return

        from app.db import get_session
        from app.repos import DevicesRepo, OperationsRepo, ToolsetSnapshotsRepo
        from utils.toolset_hash import compute_toolset_hash, sort_tools
        from websocket.modules_sync import flatten_modules_list, sync_modules_inventory

        async with get_session() as session:
            op_repo = OperationsRepo(session)
            operation = await op_repo.get_by_operation_id(lifecycle_outcome.operation_id)
            if not operation or operation.kind != "command" or not operation.command_name:
                return

            command_name = operation.command_name
            if command_name == "list_installed_modules":
                modules_list = observations.get("modules")
                if not isinstance(modules_list, list):
                    return
                inventory = flatten_modules_list(modules_list)
                await sync_modules_inventory(
                    session=session,
                    device_id=device_id,
                    inventory=inventory,
                    source="command_result",
                )
                await session.commit()
                logger.info(
                    "[command_result] synced device_modules from list_installed_modules: "
                    f"device_id={device_id} modules={len(inventory)}"
                )
                return

            if command_name != "list_tools":
                return

            tools_list = observations.get("tools")
            if not isinstance(tools_list, list):
                return

            devices_repo = DevicesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)
            device = await devices_repo.get_by_device_id(device_id)
            if not device:
                return

            sorted_tools = sort_tools(tools_list)
            toolset_hash = compute_toolset_hash(sorted_tools)
            snapshot_id = await snapshots_repo.insert_snapshot_if_not_exists(
                device_id=device_id,
                toolset_hash=toolset_hash,
                toolset_json={"tools": sorted_tools},
                agent_version=device.agent_version or "unknown",
                tool_count=len(sorted_tools),
            )
            await devices_repo.update_toolset_refresh_time(device_id)
            if snapshot_id is not None and (
                device.current_toolset_hash != toolset_hash
                or device.current_toolset_snapshot_id != snapshot_id
            ):
                await devices_repo.update_toolset_snapshot_ref(
                    device_id=device_id,
                    toolset_hash=toolset_hash,
                    snapshot_id=snapshot_id,
                )
                if device.current_toolset_hash != toolset_hash:
                    await devices_repo.update_toolset_info(
                        device_id=device_id,
                        toolset_hash=toolset_hash,
                        tools_count=len(sorted_tools),
                    )
            await session.commit()
            logger.info(
                "[command_result] synced toolset snapshot from list_tools: "
                f"device_id={device_id} tool_count={len(sorted_tools)} hash={toolset_hash}"
            )

    async def post_process(
        self,
        normalized: NormalizedCommandResult,
        ctx: Any,
        lifecycle_outcome: CommandResultLifecycleOutcome,
    ) -> None:
        try:
            await self._sync_command_side_effects(normalized, ctx, lifecycle_outcome)
        except Exception as exc:
            logger.warning(f"[command_result] command side effects failed: {exc}")
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
        if lifecycle_outcome.operation_id:
            logger.info(
                "[command_result] captured artifacts: operation_id={} count={}",
                lifecycle_outcome.operation_id,
                len(artifacts),
            )


class CommandResultEventPublisher:
    """
    Publishes operation/result side effects after lifecycle processing.
    """

    async def _load_operation_artifacts(
        self,
        session: Any,
        operation_id: str,
        normalized_artifacts: list[Any],
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from app.db.models import Artifact

        merged: dict[str, dict[str, Any]] = {}
        for item in normalized_artifacts:
            if not isinstance(item, dict):
                continue
            artifact_id = item.get("artifact_id")
            if artifact_id:
                merged[str(artifact_id)] = dict(item)

        rows = (
            await session.execute(
                select(Artifact)
                .where(Artifact.operation_id == operation_id)
                .order_by(Artifact.created_at.asc())
            )
        ).scalars().all()
        for row in rows:
            payload = {
                "artifact_id": row.artifact_id,
                "name": row.original_name,
                "original_name": row.original_name,
                "kind": row.kind,
                "mime_type": row.mime_type,
                "size": row.size_bytes,
                "url": f"/api/artifacts/{row.artifact_id}/download",
            }
            if row.artifact_id in merged:
                merged[row.artifact_id] = {**payload, **merged[row.artifact_id]}
            else:
                merged[row.artifact_id] = payload
        return list(merged.values())

    def _build_tool_call_result_payload(
        self,
        *,
        normalized: NormalizedCommandResult,
        lifecycle_outcome: CommandResultLifecycleOutcome,
        operation: Any,
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tool_name = operation.tool_name or normalized.meta_info.get("tool_name") or "tool"
        observations = normalized.data_payload.get("observations")
        result = normalized.data_payload.get("result")
        call_id = (
            normalized.meta_info.get("call_id")
            or normalized.data_payload.get("call_id")
            or normalized.payload.get("meta", {}).get("call_id")
        )
        payload: dict[str, Any] = {
            "type": "tool_call_result",
            "tool_name": tool_name,
            "operation_id": operation.operation_id,
            "call_id": call_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
        }
        if lifecycle_outcome.status == "succeeded":
            payload["status"] = "success"
            payload["summary"] = (
                operation.result_summary
                or normalized.meta_info.get("summary")
                or f"Tool {tool_name} executed successfully"
            )
            if result is not None:
                payload["result"] = result
            if observations is not None:
                payload["observations"] = observations
        elif lifecycle_outcome.status == "failed":
            error_info = normalized.error_info if isinstance(normalized.error_info, dict) else {}
            error_message = error_info.get("message") or operation.error_message or "Unknown error"
            payload["status"] = "error"
            payload["summary"] = f"Tool {tool_name} failed: {error_message}"
            payload["error"] = error_info or {"message": error_message}
            if observations is not None:
                payload["observations"] = observations
        elif lifecycle_outcome.status == "canceled":
            payload["status"] = "canceled"
            payload["summary"] = f"Tool {tool_name} canceled"
        elif lifecycle_outcome.status == "timed_out":
            payload["status"] = "error"
            payload["summary"] = f"Tool {tool_name} timed out"
            payload["error"] = {"code": "timeout", "message": operation.error_message or "Operation timed out"}
        else:
            payload["status"] = lifecycle_outcome.status
            payload["summary"] = operation.result_summary or f"Tool {tool_name} finished with status {lifecycle_outcome.status}"
        return payload

    async def _get_existing_result_event(
        self,
        session: Any,
        *,
        ticket_id: str,
        operation_id: str,
    ) -> Optional[tuple[int, Any]]:
        from sqlalchemy import select

        from app.db.models import TicketEvent

        row = await session.execute(
            select(TicketEvent.id, TicketEvent.created_at)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.operation_id == operation_id,
                TicketEvent.event_type == "tool_call_result",
            )
            .limit(1)
        )
        result = row.first()
        if result is None:
            return None
        return (int(result[0]), result[1])

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
        ui_publisher = getattr(state, "ui_publisher", None)
        if lifecycle_outcome.operation_id:
            try:
                from app.db import get_session
                from app.repos.ticket_events_repo import TicketEventsRepo
                from app.repos.operations_repo import OperationsRepo
                from websocket.ui_handler import push_ticket_event_committed

                async with get_session() as session:
                    op_repo = OperationsRepo(session)
                    operation = await op_repo.get_by_operation_id(lifecycle_outcome.operation_id)
                    result_event: Optional[tuple[int, Any]] = None
                    if (
                        operation
                        and operation.ticket_id
                        and operation.kind == "tool_call"
                        and lifecycle_outcome.status in {"succeeded", "failed", "canceled", "timed_out"}
                    ):
                        ticket_repo = TicketEventsRepo(session)
                        artifacts = await self._load_operation_artifacts(
                            session,
                            operation.operation_id,
                            normalized.data_payload.get("artifacts")
                            if isinstance(normalized.data_payload.get("artifacts"), list)
                            else [],
                        )
                        payload = self._build_tool_call_result_payload(
                            normalized=normalized,
                            lifecycle_outcome=lifecycle_outcome,
                            operation=operation,
                            artifacts=artifacts,
                        )
                        result_event = await ticket_repo.add_event(
                            ticket_id=operation.ticket_id,
                            device_id=operation.device_id,
                            agent_seq=None,
                            event_type="tool_call_result",
                            payload=payload,
                            trace_id=operation.trace_id,
                            operation_id=operation.operation_id,
                        )
                        if result_event is None:
                            result_event = await self._get_existing_result_event(
                                session,
                                ticket_id=operation.ticket_id,
                                operation_id=operation.operation_id,
                            )
                        if result_event and operation.result_event_id != result_event[0]:
                            await op_repo.update_status(
                                operation_id=operation.operation_id,
                                new_status=operation.status,
                                expected_statuses=[operation.status],
                                result_summary=operation.result_summary,
                                result_event_id=result_event[0],
                            )
                        await session.commit()
                        if result_event:
                            await push_ticket_event_committed(
                                state,
                                operation.ticket_id,
                                result_event[0],
                                "tool_call_result",
                                operation.operation_id,
                                None,
                                result_event[1],
                                payload,
                            )
                    if operation and ui_publisher is not None:
                        await ui_publisher.push_operation_updated(operation)
            except Exception as exc:
                logger.warning(
                    f"[command_result] failed to publish operation_updated: operation_id={lifecycle_outcome.operation_id} error={exc}"
                )

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import ServerRuntimeSnapshot
from shared.redaction import redact_sensitive_payload

DEFAULT_RUNTIME_SNAPSHOT_INTERVAL_SEC = 15
DEFAULT_RUNTIME_SNAPSHOT_TTL_SEC = 90
DEFAULT_RUNTIME_SNAPSHOT_RETENTION_SEC = 3600
RUNTIME_METADATA_ALLOWED_KEYS = {
    "agent_version",
    "build_version",
    "client_kind",
    "connection_id",
    "connected_at",
    "hostname",
    "install_id",
    "machine_id",
    "os",
    "protocol_version",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _watchdog_state(app: Any, key: str) -> str:
    runtime = app.get(key) if hasattr(app, "get") else None
    if runtime is None:
        return "missing"
    if bool(getattr(runtime, "_running", False)):
        return "running"
    return "stopped"


def _runtime_status_snapshot(app: Any, key: str) -> dict[str, Any] | None:
    runtime = app.get(key) if hasattr(app, "get") else None
    status_snapshot = getattr(runtime, "status_snapshot", None)
    if not callable(status_snapshot):
        return None
    try:
        return redact_sensitive_payload(status_snapshot())
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _safe_connected_agents(state: Any) -> dict[str, dict[str, Any]]:
    agents: dict[str, dict[str, Any]] = {}
    raw_agents = getattr(state, "connected_agents", {}) or {}
    for device_id, info in raw_agents.items():
        if not isinstance(info, dict):
            continue
        metadata = info.get("metadata") if isinstance(info.get("metadata"), dict) else {}
        safe_metadata = {
            key: metadata.get(key)
            for key in RUNTIME_METADATA_ALLOWED_KEYS
            if metadata.get(key) is not None
        }
        safe = redact_sensitive_payload(
            {
                "device_id": str(device_id),
                "live_ws_state": "online",
                "connected_at": _iso(info.get("connected_at") or metadata.get("connected_at")),
                "metadata": safe_metadata,
                "agent_version": metadata.get("agent_version") or metadata.get("build_version"),
                "protocol_version": metadata.get("protocol_version"),
                "client_kind": metadata.get("client_kind"),
                "connection_id": metadata.get("connection_id"),
            }
        )
        agents[str(device_id)] = {key: value for key, value in safe.items() if value is not None}
    return agents


def build_runtime_snapshot_payload(
    *,
    app: Any,
    process_kind: str = "server",
    git_revision: str | None = None,
    instance_id: str | None = None,
) -> dict[str, Any]:
    state = app.get("state") if hasattr(app, "get") else None
    connected_agents = _safe_connected_agents(state)
    observer_refresh = _runtime_status_snapshot(app, "observer_refresh_runtime")
    collected_at = _now()
    return {
        "process_kind": process_kind,
        "instance_id": instance_id or f"{socket.gethostname()}:{os.getpid()}",
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "git_revision": git_revision or _git_revision(),
        "status": "ok",
        "collected_at": collected_at.isoformat(),
        "service_health": {
            "api": "ok",
            "ui_ws_connections": len(getattr(state, "ui_connections", {}) or {}),
            "agent_ws_connections": len(connected_agents),
            "diagnostic_agent_connections": len(getattr(state, "diagnostic_agent_connections", {}) or {}),
            "operation_watchdog": _watchdog_state(app, "operation_watchdog"),
            "ticket_sla_watchdog": _watchdog_state(app, "ticket_sla_watchdog"),
            "ticket_auto_close_watchdog": _watchdog_state(app, "ticket_auto_close_watchdog"),
            "outbox_sender": "running" if app.get("outbox_sender") else "missing",
        },
        "connected_agents": connected_agents,
        "runtimes": {
            "observer_refresh_runtime": observer_refresh,
        },
        "mcp": {
            "server": "helpdesk-server-debug",
            "mode": "debug_readonly",
            "reload_required_after_deploy": True,
        },
    }


async def persist_runtime_snapshot(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    ttl_seconds: int = DEFAULT_RUNTIME_SNAPSHOT_TTL_SEC,
) -> ServerRuntimeSnapshot:
    collected_at = _now()
    raw_collected = payload.get("collected_at")
    if isinstance(raw_collected, str):
        try:
            collected_at = datetime.fromisoformat(raw_collected.replace("Z", "+00:00"))
        except ValueError:
            collected_at = _now()
    row = ServerRuntimeSnapshot(
        id=str(uuid.uuid4()),
        process_kind=str(payload.get("process_kind") or "server"),
        instance_id=str(payload.get("instance_id") or f"{socket.gethostname()}:{os.getpid()}"),
        pid=int(payload["pid"]) if payload.get("pid") is not None else None,
        git_revision=str(payload.get("git_revision")) if payload.get("git_revision") else None,
        status=str(payload.get("status") or "unknown"),
        collected_at=collected_at,
        expires_at=collected_at + timedelta(seconds=max(1, int(ttl_seconds))),
        snapshot=redact_sensitive_payload(payload),
    )
    session.add(row)
    await session.flush()
    session.expunge(row)
    return row


async def cleanup_old_runtime_snapshots(
    session: AsyncSession,
    *,
    retention_seconds: int = DEFAULT_RUNTIME_SNAPSHOT_RETENTION_SEC,
) -> int:
    cutoff = _now() - timedelta(seconds=max(1, int(retention_seconds)))
    result = await session.execute(
        sa.delete(ServerRuntimeSnapshot).where(ServerRuntimeSnapshot.collected_at < cutoff)
    )
    return int(result.rowcount or 0)


class ServerRuntimeSnapshotWriter:
    def __init__(
        self,
        app: Any,
        *,
        interval_seconds: int = DEFAULT_RUNTIME_SNAPSHOT_INTERVAL_SEC,
        ttl_seconds: int = DEFAULT_RUNTIME_SNAPSHOT_TTL_SEC,
        retention_seconds: int = DEFAULT_RUNTIME_SNAPSHOT_RETENTION_SEC,
    ) -> None:
        self._app = app
        self._interval_seconds = max(1, int(interval_seconds))
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._retention_seconds = max(1, int(retention_seconds))
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.write_once()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def write_once(self) -> ServerRuntimeSnapshot | None:
        try:
            payload = build_runtime_snapshot_payload(app=self._app)
            async with get_session() as session:
                row = await persist_runtime_snapshot(session, payload, ttl_seconds=self._ttl_seconds)
                await cleanup_old_runtime_snapshots(session, retention_seconds=self._retention_seconds)
                await session.commit()
                return row
        except Exception as exc:
            logger.warning(f"[runtime_snapshot_writer] write failed: {exc}")
            return None

    async def _run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval_seconds)
            await self.write_once()

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "running": self._running,
            "interval_seconds": self._interval_seconds,
            "ttl_seconds": self._ttl_seconds,
            "retention_seconds": self._retention_seconds,
        }

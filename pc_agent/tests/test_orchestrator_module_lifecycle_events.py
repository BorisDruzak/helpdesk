from __future__ import annotations

import base64
import io
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.config.config_loader import ConfigLoader, init_config
from pc_agent.core.database import DatabaseManager
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.tool_response import ToolMeta


DEVICE_ID = "11111111-1111-4111-8111-111111111111"


class _FakeIdentityManager:
    device_id = DEVICE_ID


def _reset_config() -> None:
    ConfigLoader._instance = None
    ConfigLoader._config = None


def _meta(command: str) -> ToolMeta:
    return ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command=command,
        module_versions={},
    )


def _module_zip(*, name: str = "diag_lifecycle", version: str = "1.0.0") -> bytes:
    manifest = {
        "module_name": name,
        "module_version": version,
        "entrypoint": "module:register",
        "platforms": ["any"],
    }
    module_py = f"""
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool


class LifecycleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "{name}"

    async def collect(self) -> Dict[str, Any]:
        return {{"ok": True}}

    @exposed_tool(
        name="probe",
        description="Lifecycle probe",
        risk_level="safe_readonly",
    )
    async def probe(self) -> Dict[str, Any]:
        return {{"ok": True}}


def register():
    return LifecycleCollector()
""".strip()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("module.py", module_py)
    return buffer.getvalue()


def _outbox_rows(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in con.execute(
                """
                SELECT outbox_id, ticket_id, kind, payload_json, agent_seq, device_seq, status
                FROM outbox
                WHERE kind IN ('module_state_changed', 'tools_changed')
                ORDER BY outbox_id
                """
            )
        ]


async def _new_orchestrator(tmp_path: Path) -> tuple[AgentOrchestrator, Path]:
    _reset_config()
    init_config(tmp_path)
    DatabaseManager._instance = None
    db_path = tmp_path / "storage.db"
    db = DatabaseManager(str(db_path))
    await db.init_db()
    orchestrator = AgentOrchestrator(
        db_manager=db,
        enabled_modules=[],
        identity_manager=_FakeIdentityManager(),
        data_root=tmp_path,
    )
    return orchestrator, db_path


@pytest.mark.asyncio
async def test_install_module_package_enqueues_module_and_tools_changed_device_events(tmp_path):
    orchestrator, db_path = await _new_orchestrator(tmp_path)
    package_b64 = base64.b64encode(_module_zip()).decode("ascii")

    result = await orchestrator._handle_install_module_package(
        name="diag_lifecycle",
        version="1.0.0",
        package_b64=package_b64,
        download_url=None,
        sha256=None,
        size=None,
        actor_role="admin",
        meta=_meta("install_module_package"),
    )

    assert result.status == "success"
    rows = _outbox_rows(db_path)
    assert [row["kind"] for row in rows] == ["tools_changed", "module_state_changed"]
    assert all(row["agent_seq"] is None for row in rows)
    assert all(row["device_seq"] is not None for row in rows)
    assert all(row["ticket_id"] == DEVICE_ID for row in rows)


@pytest.mark.asyncio
async def test_noop_reinstall_does_not_duplicate_tools_changed(tmp_path):
    orchestrator, db_path = await _new_orchestrator(tmp_path)
    package_b64 = base64.b64encode(_module_zip()).decode("ascii")

    for _ in range(2):
        result = await orchestrator._handle_install_module_package(
            name="diag_lifecycle",
            version="1.0.0",
            package_b64=package_b64,
            download_url=None,
            sha256=None,
            size=None,
            actor_role="admin",
            meta=_meta("install_module_package"),
        )
        assert result.status == "success"

    rows = _outbox_rows(db_path)
    assert [row["kind"] for row in rows].count("tools_changed") == 1
    assert [row["kind"] for row in rows].count("module_state_changed") == 2


@pytest.mark.asyncio
async def test_deactivate_module_enqueues_state_and_tools_changed_on_hash_change(tmp_path):
    orchestrator, db_path = await _new_orchestrator(tmp_path)
    package_b64 = base64.b64encode(_module_zip()).decode("ascii")
    install_result = await orchestrator._handle_install_module_package(
        name="diag_lifecycle",
        version="1.0.0",
        package_b64=package_b64,
        download_url=None,
        sha256=None,
        size=None,
        actor_role="admin",
        meta=_meta("install_module_package"),
    )
    assert install_result.status == "success"

    deactivate_result = await orchestrator._handle_deactivate_module(
        name="diag_lifecycle",
        actor_role="admin",
        meta=_meta("deactivate_module"),
    )

    assert deactivate_result.status == "success"
    rows = _outbox_rows(db_path)
    assert [row["kind"] for row in rows] == [
        "tools_changed",
        "module_state_changed",
        "tools_changed",
        "module_state_changed",
    ]
    last_state_payload = json.loads(rows[-1]["payload_json"])
    assert last_state_payload["reason"] == "deactivate:diag_lifecycle"

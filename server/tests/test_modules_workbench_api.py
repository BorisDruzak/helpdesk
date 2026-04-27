import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceDesiredModule, DeviceModule, Module, ObserverTrace, ServerConfig
from modules.handlers import MODULES_STORAGE_DIR
from tests.conftest import TEST_UI_ADMIN_TOKEN
from utils.module_builder import build_module_package
from utils.module_preflight import preflight_module_zip


ADMIN_HEADERS = {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


@pytest.mark.asyncio
async def test_modules_workbench_groups_versions_and_marks_preferred(test_client, test_engine):
    module_name = f"wb_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        for version in ("1.0.0", "1.2.0"):
            zip_bytes, _summary = build_module_package(
                module_name=module_name,
                version=version,
                tool_name="vendor_x.echo",
                description="Workbench module",
                user_function_body='return {"ok": True}',
                owner_scope="vendor",
            )
            ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
            assert ok is True
            session.add(
                Module(
                    module_name=module_name,
                    version=version,
                    sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                    size=len(zip_bytes),
                    storage_path=f"{module_name}/{version}/module.zip",
                    uploaded_by="admin",
                    manifest_json=manifest_json,
                    validation_json=validation_json,
                    manifest_summary=manifest_summary,
                )
            )
        session.add(
            ServerConfig(
                key=f"module_preferred:{module_name}",
                value=json.dumps({"module_name": module_name, "version": "1.0.0", "updated_by": "admin"}),
            )
        )
        await session.commit()

    response = await test_client.get("/api/modules/workbench")
    assert response.status == 200, await response.text()
    data = await response.json()
    family = next(item for item in data["modules"] if item["module_name"] == module_name)
    assert family["preferred_version"] == "1.0.0"
    assert family["latest_version"] == "1.2.0"
    assert any(version["version"] == "1.0.0" and version["is_preferred"] for version in family["versions"])


@pytest.mark.asyncio
async def test_module_workbench_detail_returns_editable_spec_for_generated_module(test_client, test_engine):
    module_name = f"wb_detail_{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version=version,
        tool_name="vendor_x.inspect",
        description="Generated module",
        user_function_body='value = params.get("value", "x")\nreturn {"echo": value}',
        owner_scope="vendor",
        tools=[
            {
                "tool_name": "vendor_x.inspect",
                "method_name": "inspect_value",
                "description": "Inspect value",
                "params_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "additionalProperties": True,
                },
                "metadata": {"domain": "vendor_x", "platforms": ["any"], "idempotent": True},
                "user_function_body": 'value = params.get("value", "x")\nreturn {"echo": value}',
            }
        ],
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True

    archive_path = MODULES_STORAGE_DIR / module_name / version / "module.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(zip_bytes)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Module(
                module_name=module_name,
                version=version,
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(zip_bytes),
                storage_path=f"{module_name}/{version}/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/modules/workbench/{module_name}/{version}")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    editable = data["editable_spec"]
    assert editable["module_name"] == module_name
    assert editable["tools"][0]["tool_name"] == "vendor_x.inspect"
    assert 'return {"echo": value}' in editable["tools"][0]["user_function_body"]
    assert any(item["path"] == "module.py" for item in editable["source"]["files"])


@pytest.mark.asyncio
async def test_module_workbench_detail_reconstructs_tool_body_via_ast_without_builder_markers(test_client, test_engine):
    module_name = f"wb_ast_{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version=version,
        tool_name="vendor_x.ast_demo",
        description="AST module",
        user_function_body='value = params.get("value", "x")\nreturn {"echo": value}',
        owner_scope="vendor",
        tools=[
            {
                "tool_name": "vendor_x.ast_demo",
                "method_name": "inspect_value",
                "description": "AST inspect value",
                "params_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "additionalProperties": True,
                },
                "metadata": {"domain": "vendor_x", "platforms": ["any"], "idempotent": True},
                "user_function_body": 'value = params.get("value", "x")\nreturn {"echo": value}',
            }
        ],
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True

    module_py = """from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return "wb_ast"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(
        name="vendor_x.ast_demo",
        aliases=["vendor_x.ast_demo_legacy"],
        description="AST inspect value",
        risk_level="safe_readonly",
        params_schema={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": True},
        output_schema={"type": "object", "properties": {"echo": {"type": "string"}}},
        presets=[],
        metadata_risk_level="safe_read",
        metadata_scopes=["vendor_x"],
        metadata_requires_consent=False,
        metadata_allow_roles=["admin"],
        metadata_domain="vendor_x",
        metadata_platforms=["any"],
        metadata_timeout_sec=30,
        metadata_idempotent=True,
        metadata_origin="managed",
        metadata_side_effects=False,
        contract_version="1.0.0",
        dependencies={},
        lifecycle="stable",
        error_codes=["VALIDATION_ERROR"],
        artifact_types=[],
        redaction={"enabled": True, "allow_raw_sensitive_data": False},
        resources={"max_runtime_sec": 30},
    )
    async def inspect_value(self, **kwargs) -> Dict[str, Any]:
        params = {**{}, **kwargs}
        value = params.get("value", "x")
        return {"echo": value}


def register():
    return _Collector()
"""

    archive_path = MODULES_STORAGE_DIR / module_name / version / "module.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest_json, ensure_ascii=False, indent=2))
        zf.writestr("module.py", module_py)
    archive_path.write_bytes(archive_buffer.getvalue())

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Module(
                module_name=module_name,
                version=version,
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(archive_buffer.getvalue()),
                storage_path=f"{module_name}/{version}/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/modules/workbench/{module_name}/{version}")
    assert response.status == 200, await response.text()
    data = await response.json()
    editable = data["editable_spec"]
    assert editable["tools"][0]["reconstruction_strategy"] == "ast"
    assert 'value = params.get("value", "x")' in editable["tools"][0]["user_function_body"]


@pytest.mark.asyncio
async def test_module_workbench_save_creates_module_and_sets_preferred(test_client, test_engine):
    module_name = f"wb_save_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/modules/workbench/save",
        json={
            "module_name": module_name,
            "version": "2.0.0",
            "description": "Saved from workbench",
            "owner_scope": "vendor",
            "module_api_version": "1.0.0",
            "entrypoint": "module:register",
            "platforms": ["any"],
            "requirements": [],
            "optional_requirements": [],
            "set_preferred": True,
            "tools": [
                {
                    "tool_name": "vendor_x.echo",
                    "method_name": "echo_tool",
                    "description": "Echo data",
                    "params_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "additionalProperties": True,
                    },
                    "output_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                    "metadata": {
                        "domain": "vendor_x",
                        "platforms": ["any"],
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "timeout_sec": 30,
                        "idempotent": True,
                        "side_effects": False,
                        "allow_roles": ["admin"],
                        "scopes": ["custom"],
                        "origin": "managed",
                        "tool_kind": "diagnostic",
                    },
                    "contract_version": "1.0.0",
                    "dependencies": {
                        "min_agent_version": "1.0.0",
                        "required_binaries": [],
                        "required_python_packages": [],
                        "required_services": [],
                        "required_permissions": [],
                    },
                    "lifecycle": "stable",
                    "error_codes": ["VALIDATION_ERROR"],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "user_function_body": 'return {"ok": True, "value": params.get("value")}',
                }
            ],
        },
    )
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "success"
    assert data["preferred_version"] == "2.0.0"

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        module = await session.get(Module, {"module_name": module_name, "version": "2.0.0"})
        assert module is not None
        preferred_value = (
            await session.execute(text("SELECT value FROM server_config WHERE key = :key"), {"key": f"module_preferred:{module_name}"})
        ).scalar_one()
        assert '"version": "2.0.0"' in preferred_value


@pytest.mark.asyncio
async def test_module_authoring_catalog_returns_headless_contract(test_client):
    response = await test_client.get("/api/modules/authoring/catalog")

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["endpoints"]["validate"] == "/api/modules/authoring/validate"
    assert data["endpoints"]["publish"] == "/api/modules/authoring/publish"
    assert "network_ping" in {item["key"] for item in data["tool_templates"]}
    assert data["output_contract_template"]["status_values"] == ["ok", "error"]
    assert data["sample_payload"]["tools"][0]["output_contract"]["status_path"] == "result.status"


@pytest.mark.asyncio
async def test_module_authoring_validate_preserves_playbook_output_contract(test_client):
    module_name = f"authoring_validate_{uuid.uuid4().hex[:8]}"
    payload = {
        "module_name": module_name,
        "version": "0.1.0",
        "description": "Headless authoring validate",
        "owner_scope": "vendor",
        "module_api_version": "1.0.0",
        "entrypoint": "module:register",
        "platforms": ["any"],
        "requirements": [],
        "optional_requirements": [],
        "tools": [
            {
                "tool_name": "vendor_x.echo",
                "method_name": "echo_tool",
                "description": "Echo data",
                "params_schema": {
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "string"}},
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "error"]},
                        "value": {"type": "string"},
                    },
                },
                "output_contract": {
                    "status_path": "result.status",
                    "status_values": ["ok", "error"],
                    "success_values": ["ok"],
                    "error_values": ["error"],
                    "summary_path": "result.output.value",
                    "error_code_path": "result.error.code",
                },
                "metadata": {
                    "domain": "vendor_x",
                    "platforms": ["any"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                    "timeout_sec": 30,
                    "idempotent": True,
                    "side_effects": False,
                    "allow_roles": ["admin"],
                    "scopes": ["custom"],
                    "origin": "managed",
                    "tool_kind": "diagnostic",
                },
                "contract_version": "1.0.0",
                "dependencies": {
                    "min_agent_version": "1.0.0",
                    "required_binaries": [],
                    "required_python_packages": [],
                    "required_services": [],
                    "required_permissions": [],
                },
                "lifecycle": "stable",
                "error_codes": ["VALIDATION_ERROR"],
                "artifact_types": [],
                "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "user_function_body": 'return {"status": "ok", "value": params.get("value")}',
            }
        ],
    }

    response = await test_client.post("/api/modules/authoring/validate", json=payload)

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["publish_ready"] is True
    tool = data["manifest_json"]["tools"][0]
    assert tool["output_schema"]["properties"]["status"]["enum"] == ["ok", "error"]
    assert tool["output_contract"]["status_values"] == ["ok", "error"]
    assert data["editable_preview"]["tools"][0]["output_contract"]["summary_path"] == "result.output.value"


@pytest.mark.asyncio
async def test_module_authoring_validate_requires_server_harness_and_warns_for_windows(test_client):
    module_name = f"authoring_win_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/modules/authoring/validate",
        json={
            "module_name": module_name,
            "version": "0.1.0",
            "description": "Windows diagnostic module",
            "owner_scope": "vendor",
            "platforms": ["win32"],
            "tools": [
                {
                    "tool_name": f"{module_name}.check",
                    "method_name": "run_check",
                    "description": "Check returns a predictable status",
                    "params_schema": {"type": "object", "properties": {}, "required": []},
                    "output_schema": {
                        "type": "object",
                        "properties": {"status": {"type": "string", "enum": ["ok", "error"]}},
                    },
                    "output_contract": {
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "success_values": ["ok"],
                        "error_values": ["error"],
                        "summary_path": "result.output.summary",
                        "error_code_path": "result.error.code",
                    },
                    "metadata": {
                        "risk_level": "safe_read",
                        "tool_kind": "diagnostic",
                        "platforms": ["win32"],
                        "idempotent": True,
                        "side_effects": False,
                    },
                    "user_function_body": 'return {"status": "ok", "summary": "server harness"}',
                }
            ],
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["validation_json"]["server_harness"]["status"] == "passed"
    assert data["validation_json"]["server_harness"]["required_before_publish"] is True
    assert "WINDOWS_LIVE_TEST_REQUIRED_BEFORE_PREFERRED" in data["validation_json"]["warnings"]


@pytest.mark.asyncio
async def test_module_authoring_validate_harness_ignores_server_platform_guard(test_client):
    module_name = f"authoring_cross_os_{uuid.uuid4().hex[:8]}"
    current = "win32" if sys.platform.startswith("win") else ("darwin" if sys.platform == "darwin" else "linux")
    target_platform = "linux" if current == "win32" else "win32"
    response = await test_client.post(
        "/api/modules/authoring/validate",
        json={
            "module_name": module_name,
            "version": "0.1.0",
            "description": "Cross-platform server harness check",
            "owner_scope": "vendor",
            "platforms": [target_platform],
            "tools": [
                {
                    "tool_name": f"{module_name}.check",
                    "method_name": "run_check",
                    "description": "Check server harness on non-current target platform",
                    "params_schema": {"type": "object", "properties": {}, "required": []},
                    "output_schema": {
                        "type": "object",
                        "properties": {"status": {"type": "string", "enum": ["ok", "error"]}},
                    },
                    "output_contract": {
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "success_values": ["ok"],
                        "error_values": ["error"],
                        "summary_path": "result.output.summary",
                        "error_code_path": "result.error.code",
                    },
                    "metadata": {
                        "risk_level": "safe_read",
                        "tool_kind": "diagnostic",
                        "platforms": [target_platform],
                        "idempotent": True,
                        "side_effects": False,
                    },
                    "user_function_body": 'return {"status": "ok", "summary": "cross-os harness"}',
                }
            ],
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["validation_json"]["server_harness"]["status"] == "passed"


@pytest.mark.asyncio
async def test_windows_module_preferred_requires_passed_windows_live_test(test_client, test_engine):
    module_name = f"win_gate_{uuid.uuid4().hex[:8]}"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version="1.0.0",
        tool_name=f"{module_name}.check",
        method_name="run_check",
        description="Windows gated diagnostic",
        user_function_body='return {"status": "ok"}',
        platforms=["win32"],
        metadata={"domain": module_name, "platforms": ["win32"], "risk_level": "safe_read"},
        min_agent_version="1.0.0",
        owner_scope="vendor",
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True
    validation_json["server_harness"] = {"status": "passed", "required_before_publish": True}

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Module(
                module_name=module_name,
                version="1.0.0",
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(zip_bytes),
                storage_path=f"{module_name}/1.0.0/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        await session.commit()

    response = await test_client.patch(
        f"/api/modules/{module_name}/preferred",
        json={"version": "1.0.0"},
        headers=ADMIN_HEADERS,
    )

    assert response.status == 409, await response.text()
    data = await response.json()
    assert data["error_code"] == "MODULE_WINDOWS_LIVE_TEST_REQUIRED"
    assert data["observer_trace_id"]

    async with session_maker() as session:
        trace = await session.get(ObserverTrace, data["observer_trace_id"])
        assert trace is not None
        assert trace.root_kind == "module_preferred_gate"
        assert trace.status == "failed"


@pytest.mark.asyncio
async def test_windows_authoring_publish_set_preferred_requires_live_test(test_client, test_engine):
    module_name = f"win_publish_gate_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/modules/authoring/publish",
        json={
            "module_name": module_name,
            "version": "1.0.0",
            "description": "Windows publish preferred gate",
            "owner_scope": "vendor",
            "platforms": ["win32"],
            "set_preferred": True,
            "tools": [
                {
                    "tool_name": f"{module_name}.check",
                    "method_name": "run_check",
                    "description": "Check preferred gate",
                    "params_schema": {"type": "object", "properties": {}, "required": []},
                    "output_schema": {
                        "type": "object",
                        "properties": {"status": {"type": "string", "enum": ["ok", "error"]}},
                    },
                    "output_contract": {
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "success_values": ["ok"],
                        "error_values": ["error"],
                        "summary_path": "result.output.summary",
                        "error_code_path": "result.error.code",
                    },
                    "metadata": {
                        "risk_level": "safe_read",
                        "tool_kind": "diagnostic",
                        "platforms": ["win32"],
                        "idempotent": True,
                        "side_effects": False,
                    },
                    "user_function_body": 'return {"status": "ok", "summary": "preferred gate"}',
                }
            ],
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status == 409, await response.text()
    data = await response.json()
    assert data["error_code"] == "MODULE_WINDOWS_LIVE_TEST_REQUIRED"
    assert data["module_name"] == module_name
    assert data["observer_trace_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        trace = await session.get(ObserverTrace, data["observer_trace_id"])
        assert trace is not None
        assert trace.root_kind == "module_preferred_gate"
        assert trace.status == "failed"


@pytest.mark.asyncio
async def test_module_live_test_candidates_filter_platform_and_version(test_client, test_engine):
    module_name = f"lab_candidates_{uuid.uuid4().hex[:8]}"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version="1.0.0",
        tool_name=f"{module_name}.check",
        method_name="run_check",
        description="Lab candidate diagnostic",
        user_function_body='return {"status": "ok"}',
        platforms=["win32"],
        metadata={"domain": module_name, "platforms": ["win32"], "risk_level": "safe_read"},
        min_agent_version="1.2.0",
        owner_scope="vendor",
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True
    validation_json["server_harness"] = {"status": "passed", "required_before_publish": True}

    now = datetime.now(timezone.utc)
    good_device_id = str(uuid.uuid4())
    old_device_id = str(uuid.uuid4())
    linux_device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                Device(
                    device_id=good_device_id,
                    protocol_version="ws_ticket_v3",
                    agent_version="1.2.3",
                    hostname="win-good",
                    os="Windows",
                    capabilities={},
                    device_metadata={"os_type": "windows"},
                    first_seen_at=now,
                    last_seen_at=now,
                    last_handshake_at=now,
                ),
                Device(
                    device_id=old_device_id,
                    protocol_version="ws_ticket_v3",
                    agent_version="1.0.0",
                    hostname="win-old",
                    os="win32",
                    capabilities={},
                    device_metadata={"os_type": "windows"},
                    first_seen_at=now,
                    last_seen_at=now,
                    last_handshake_at=now,
                ),
                Device(
                    device_id=linux_device_id,
                    protocol_version="ws_ticket_v3",
                    agent_version="1.5.0",
                    hostname="linux-lab",
                    os="linux",
                    capabilities={},
                    device_metadata={"os_type": "linux"},
                    first_seen_at=now,
                    last_seen_at=now,
                    last_handshake_at=now,
                ),
                Module(
                    module_name=module_name,
                    version="1.0.0",
                    sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                    size=len(zip_bytes),
                    storage_path=f"{module_name}/1.0.0/module.zip",
                    uploaded_by="admin",
                    manifest_json=manifest_json,
                    validation_json=validation_json,
                    manifest_summary=manifest_summary,
                ),
            ]
        )
        await session.commit()

    class OpenWs:
        closed = False

    test_client.app["state"].connected_agents[good_device_id] = {
        "ws": OpenWs(),
        "metadata": {"status": "online"},
        "connected_at": now.isoformat(),
    }

    response = await test_client.get(
        f"/api/modules/{module_name}/1.0.0/live_test_candidates?platform=win32",
        headers=ADMIN_HEADERS,
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["module_name"] == module_name
    assert data["version"] == "1.0.0"
    assert data["platform"] == "win32"
    assert data["min_agent_version"] == "1.2.0"
    candidate_ids = [item["device_id"] for item in data["candidates"]]
    assert candidate_ids == [good_device_id, old_device_id]
    good = data["candidates"][0]
    old = data["candidates"][1]
    assert good["compatible"] is True
    assert good["online"] is True
    assert good["platform"] == "win32"
    assert old["compatible"] is False
    assert "AGENT_VERSION_TOO_OLD" in old["reasons"]


@pytest.mark.asyncio
async def test_module_live_test_records_windows_pass_and_unblocks_preferred(test_client, test_engine):
    module_name = f"win_live_{uuid.uuid4().hex[:8]}"
    device_id = str(uuid.uuid4())
    tool_name = f"{module_name}.check"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version="1.0.0",
        tool_name=tool_name,
        method_name="run_check",
        description="Windows live-test diagnostic",
        user_function_body='return {"status": "ok", "summary": "live"}',
        platforms=["win32"],
        metadata={"domain": module_name, "platforms": ["win32"], "risk_level": "safe_read"},
        min_agent_version="1.0.0",
        owner_scope="vendor",
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True
    validation_json["server_harness"] = {"status": "passed", "required_before_publish": True}

    module_path = MODULES_STORAGE_DIR / module_name / "1.0.0" / "module.zip"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_bytes(zip_bytes)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.0",
                hostname="win-lab",
                os="windows",
                capabilities={},
                device_metadata={"os_type": "Windows"},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            Module(
                module_name=module_name,
                version="1.0.0",
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(zip_bytes),
                storage_path=f"{module_name}/1.0.0/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        await session.commit()

    calls: list[str] = []
    run_tool_params: dict | None = None

    async def fake_send_ws_command(**kwargs):
        nonlocal run_tool_params
        calls.append(kwargs["command"])
        if kwargs["command"] == "run_tool":
            run_tool_params = dict(kwargs["params"])
        return {
            "status": "success",
            "payload": {
                "status": "success",
                "data": {"observations": {"status": "ok", "summary": "live"}},
            },
            "operation_id": f"op-{len(calls)}",
            "trace_id": f"trace-{len(calls)}",
        }

    with patch("modules.handlers.send_ws_command", new=fake_send_ws_command):
        live_response = await test_client.post(
            f"/api/modules/{module_name}/1.0.0/live_tests",
            json={"device_id": device_id, "tool_name": tool_name, "params": {}},
            headers=ADMIN_HEADERS,
        )

    assert live_response.status == 200, await live_response.text()
    live_data = await live_response.json()
    assert live_data["live_test"]["status"] == "passed"
    assert live_data["live_test"]["platform"] == "win32"
    assert calls == ["install_module_package", "run_tool"]
    assert run_tool_params is not None
    assert "ticket_id" not in run_tool_params
    assert run_tool_params["tool_name"] == tool_name

    response = await test_client.patch(
        f"/api/modules/{module_name}/preferred",
        json={"version": "1.0.0"},
        headers=ADMIN_HEADERS,
    )

    assert response.status == 200, await response.text()


@pytest.mark.asyncio
async def test_module_live_test_writes_observer_trace_for_selected_agent(test_client, test_engine):
    module_name = f"win_trace_{uuid.uuid4().hex[:8]}"
    device_id = str(uuid.uuid4())
    tool_name = f"{module_name}.check"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version="1.0.0",
        tool_name=tool_name,
        method_name="run_check",
        description="Windows observer live-test diagnostic",
        user_function_body='return {"status": "ok", "summary": "live"}',
        platforms=["win32"],
        metadata={"domain": module_name, "platforms": ["win32"], "risk_level": "safe_read"},
        min_agent_version="1.0.0",
        owner_scope="vendor",
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True
    validation_json["server_harness"] = {"status": "passed", "required_before_publish": True}

    module_path = MODULES_STORAGE_DIR / module_name / "1.0.0" / "module.zip"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_bytes(zip_bytes)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.0",
                hostname="win-lab-traced",
                os="windows",
                capabilities={},
                device_metadata={"os_type": "Windows"},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            Module(
                module_name=module_name,
                version="1.0.0",
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(zip_bytes),
                storage_path=f"{module_name}/1.0.0/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        await session.commit()

    async def fake_send_ws_command(**kwargs):
        return {
            "status": "success",
            "payload": {"status": "success", "data": {"observations": {"status": "ok"}}},
            "operation_id": str(uuid.uuid4()),
        }

    with patch("modules.handlers.send_ws_command", new=fake_send_ws_command):
        live_response = await test_client.post(
            f"/api/modules/{module_name}/1.0.0/live_tests",
            json={"device_id": device_id, "tool_name": tool_name, "params": {}},
            headers=ADMIN_HEADERS,
        )

    assert live_response.status == 200, await live_response.text()
    live_data = await live_response.json()
    trace_id = live_data["live_test"]["trace_id"]

    async with session_maker() as session:
        trace = await session.get(ObserverTrace, trace_id)
        assert trace is not None
        assert trace.root_kind == "module_live_test"
        assert trace.device_id == device_id
        assert trace.status == "succeeded"
        result = await session.execute(
            text("SELECT name, status FROM observer_spans WHERE trace_id = :trace_id ORDER BY started_at ASC"),
            {"trace_id": trace_id},
        )
        spans = result.all()

    span_names = [row[0] for row in spans]
    assert "module.live_test" in span_names
    assert "module.install_module_package" in span_names
    assert "module.run_tool" in span_names
    assert all(row[1] == "ok" for row in spans)


@pytest.mark.asyncio
async def test_delete_module_version_removes_registry_archive_and_preferred_assignment(test_client, test_engine):
    module_name = f"wb_delete_{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    zip_bytes, _summary = build_module_package(
        module_name=module_name,
        version=version,
        tool_name="vendor_x.delete_me",
        description="Delete me",
        user_function_body='return {"ok": True}',
        owner_scope="vendor",
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True

    archive_path = MODULES_STORAGE_DIR / module_name / version / "module.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(zip_bytes)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Module(
                module_name=module_name,
                version=version,
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=len(zip_bytes),
                storage_path=f"{module_name}/{version}/module.zip",
                uploaded_by="admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
        )
        session.add(
            ServerConfig(
                key=f"module_preferred:{module_name}",
                value=json.dumps({"module_name": module_name, "version": version, "updated_by": "admin"}),
            )
        )
        await session.commit()

    response = await test_client.delete(f"/api/modules/{module_name}/{version}", headers=ADMIN_HEADERS)
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["module_name"] == module_name
    assert data["version"] == version
    assert archive_path.exists() is False

    async with session_maker() as session:
        deleted_module = await session.get(Module, {"module_name": module_name, "version": version})
        assert deleted_module is None
        preferred_value = (
            await session.execute(text("SELECT value FROM server_config WHERE key = :key"), {"key": f"module_preferred:{module_name}"})
        ).scalar_one_or_none()
        assert preferred_value is None


@pytest.mark.asyncio
async def test_module_workbench_validate_returns_preview_and_publish_readiness(test_client):
    module_name = f"wb_validate_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/modules/workbench/validate",
        json={
            "module_name": module_name,
            "version": "0.2.0",
            "description": "Validate-only draft",
            "owner_scope": "vendor",
            "module_api_version": "1.0.0",
            "entrypoint": "module:register",
            "platforms": ["any"],
            "requirements": [],
            "optional_requirements": [],
            "tools": [
                {
                    "tool_name": "vendor_x.echo",
                    "method_name": "echo_tool",
                    "description": "Echo data",
                    "params_schema": {
                        "type": "object",
                        "required": ["value"],
                        "properties": {"value": {"type": "string"}},
                        "additionalProperties": False,
                    },
                    "output_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                    "metadata": {
                        "domain": "vendor_x",
                        "platforms": ["any"],
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "timeout_sec": 30,
                        "idempotent": True,
                        "side_effects": False,
                        "allow_roles": ["admin"],
                        "scopes": ["custom"],
                        "origin": "managed",
                        "tool_kind": "diagnostic",
                    },
                    "contract_version": "1.0.0",
                    "dependencies": {
                        "min_agent_version": "1.0.0",
                        "required_binaries": [],
                        "required_python_packages": [],
                        "required_services": [],
                        "required_permissions": [],
                    },
                    "lifecycle": "stable",
                    "error_codes": ["VALIDATION_ERROR"],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "user_function_body": 'return {"ok": True, "value": params.get("value")}',
                }
            ],
        },
    )
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["publish_ready"] is True
    assert data["module_exists"] is False
    assert data["editable_preview"]["module_name"] == module_name
    assert data["editable_preview"]["tools"][0]["tool_name"] == "vendor_x.echo"
    assert any(item["path"] == "module.py" for item in data["editable_preview"]["source"]["files"])


@pytest.mark.asyncio
async def test_module_workbench_validate_marks_existing_version_not_publish_ready(test_client):
    module_name = f"wb_existing_{uuid.uuid4().hex[:8]}"
    payload = {
        "module_name": module_name,
        "version": "0.3.0",
        "description": "Existing version draft",
        "owner_scope": "vendor",
        "module_api_version": "1.0.0",
        "entrypoint": "module:register",
        "platforms": ["any"],
        "requirements": [],
        "optional_requirements": [],
        "tools": [
            {
                "tool_name": "vendor_x.echo",
                "method_name": "echo_tool",
                "description": "Echo data",
                "params_schema": {
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "string"}},
                    "additionalProperties": False,
                },
                "output_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                "metadata": {
                    "domain": "vendor_x",
                    "platforms": ["any"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                    "timeout_sec": 30,
                    "idempotent": True,
                    "side_effects": False,
                    "allow_roles": ["admin"],
                    "scopes": ["custom"],
                    "origin": "managed",
                    "tool_kind": "diagnostic",
                },
                "contract_version": "1.0.0",
                "dependencies": {
                    "min_agent_version": "1.0.0",
                    "required_binaries": [],
                    "required_python_packages": [],
                    "required_services": [],
                    "required_permissions": [],
                },
                "lifecycle": "stable",
                "error_codes": ["VALIDATION_ERROR"],
                "artifact_types": [],
                "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "user_function_body": 'return {"ok": True, "value": params.get("value")}',
            }
        ],
    }

    save_response = await test_client.post("/api/modules/workbench/save", json=payload)
    assert save_response.status == 200, await save_response.text()

    validate_response = await test_client.post("/api/modules/workbench/validate", json=payload)
    assert validate_response.status == 200, await validate_response.text()
    data = await validate_response.json()
    assert data["status"] == "ok"
    assert data["module_exists"] is True
    assert data["publish_ready"] is False


@pytest.mark.asyncio
async def test_module_workbench_exposes_and_updates_rollout_settings(test_client):
    response = await test_client.get("/api/modules/workbench")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["rollout_settings"]["preferred_version_rollout_mode"] == "manual"
    assert data["rollout_settings"]["sync_after_preferred_change"] is True

    patch_response = await test_client.patch(
        "/api/modules/rollout_settings",
        json={
            "preferred_version_rollout_mode": "installed_devices",
            "sync_after_preferred_change": False,
        },
        headers=ADMIN_HEADERS,
    )
    assert patch_response.status == 200, await patch_response.text()
    patched = await patch_response.json()
    assert patched["rollout_settings"]["preferred_version_rollout_mode"] == "installed_devices"
    assert patched["rollout_settings"]["sync_after_preferred_change"] is False

    get_response = await test_client.get("/api/modules/rollout_settings")
    assert get_response.status == 200, await get_response.text()
    loaded = await get_response.json()
    assert loaded["rollout_settings"]["preferred_version_rollout_mode"] == "installed_devices"
    assert loaded["rollout_settings"]["sync_after_preferred_change"] is False


@pytest.mark.asyncio
async def test_preferred_version_change_auto_rolls_installed_devices_when_enabled(test_client, test_engine):
    module_name = f"wb_rollout_{uuid.uuid4().hex[:8]}"
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="wb-rollout",
                os="windows",
                capabilities={},
                device_metadata={"os_type": "Windows"},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        for version in ("1.0.0", "2.0.0"):
            zip_bytes, _summary = build_module_package(
                module_name=module_name,
                version=version,
                tool_name="vendor_x.rollout_echo",
                description=f"Rollout module {version}",
                user_function_body=f'return {{"ok": True, "version": "{version}"}}',
                owner_scope="vendor",
            )
            ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
            assert ok is True
            session.add(
                Module(
                    module_name=module_name,
                    version=version,
                    sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                    size=len(zip_bytes),
                    storage_path=f"{module_name}/{version}/module.zip",
                    uploaded_by="admin",
                    manifest_json=manifest_json,
                    validation_json=validation_json,
                    manifest_summary=manifest_summary,
                )
            )
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name=module_name,
                version="1.0.0",
                installed=True,
                active=True,
                state="active",
                installed_at=datetime.now(timezone.utc),
                activated_at=datetime.now(timezone.utc),
                last_updated_at=datetime.now(timezone.utc),
                source="handshake",
            )
        )
        session.add(
            DeviceDesiredModule(
                device_id=device_id,
                module_name=module_name,
                desired_version="1.0.0",
                desired_sha256=None,
                state="installed",
                reason="manual",
                updated_at=datetime.now(timezone.utc),
                updated_by="admin",
            )
        )
        await session.execute(
            text(
                "INSERT INTO server_config (key, value) VALUES (:key, :value) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {
                "key": "module_rollout_settings",
                "value": json.dumps(
                    {
                        "preferred_version_rollout_mode": "installed_devices",
                        "sync_after_preferred_change": True,
                    }
                ),
            },
        )
        await session.commit()

    reconcile_calls: list[str] = []

    async def fake_reconcile_device(device_id, **_kwargs):
        reconcile_calls.append(device_id)
        return {"installs": 1, "removes": 0, "skipped": 0}

    with patch("modules.reconcile.reconcile_device", new=fake_reconcile_device):
        response = await test_client.patch(
            f"/api/modules/{module_name}/preferred",
            json={"version": "2.0.0"},
            headers=ADMIN_HEADERS,
        )

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["preferred_version"] == "2.0.0"
    assert data["rollout_summary"]["mode"] == "installed_devices"
    assert data["rollout_summary"]["desired_updates"] == 1
    assert data["rollout_summary"]["sync_enqueued"] == 1
    assert data["rollout_summary"]["refresh_enqueued"] == 1
    assert reconcile_calls == [device_id]

    async with session_maker() as session:
        desired = (
            await session.execute(
                text(
                    "SELECT desired_version, reason FROM device_desired_modules "
                    "WHERE device_id = :device_id AND module_name = :module_name"
                ),
                {"device_id": device_id, "module_name": module_name},
            )
        ).one()
        assert desired[0] == "2.0.0"
        assert desired[1] == "preferred_rollout"

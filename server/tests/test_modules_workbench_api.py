import json
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceDesiredModule, DeviceModule, Module, ServerConfig
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
    assert data["rollout_summary"]["refresh_enqueued"] == 0
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

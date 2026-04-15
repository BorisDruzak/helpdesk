import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Module, ServerConfig
from modules.handlers import MODULES_STORAGE_DIR
from utils.module_builder import build_module_package
from utils.module_preflight import preflight_module_zip


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

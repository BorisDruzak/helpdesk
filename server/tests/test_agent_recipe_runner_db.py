from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AgentRecipePrimitive,
    AgentRecipeTestRun,
    AgentRecipeVersion,
    DeviceModule,
    DeviceOutbox,
    DiagnosticCapability,
    DiagnosticCapabilityVersion,
    DiagnosticProvider,
    DeviceDesiredModule,
    Operation,
    OperationDependency,
    Module,
    ServerConfig,
    Ticket,
)
from diagnostics.agent_recipes import AgentRecipeValidationError
from diagnostics.agent_recipes_repo import AgentRecipeRepo
from diagnostics.recipe_execution_service import RecipeExecutionService


def _ticket(ticket_id: str, device_id: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=device_id,
        title="Agent recipe diagnostic",
        description="Ticket for agent recipe runner",
        status="in_progress",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def _seed_recipe(
    session,
    *,
    device_id: str,
    runner_version: str = "1.0.0",
    install_runner: bool = True,
) -> dict[str, str]:
    provider = DiagnosticProvider(
        provider_id="agent_recipe_runner",
        provider_type="agent_recipe_runner",
        title="Agent Recipe Runner",
        source="managed_module",
        status="available",
    )
    capability = DiagnosticCapability(
        capability_id="endpoint.spooler.status",
        provider_id="agent_recipe_runner",
        execution_target="agent_recipe",
        title="Check print spooler",
        status="active",
        latest_version="1.0.0",
        descriptor_json={
            "id": "endpoint.spooler.status",
            "title": "Check print spooler",
            "provider_id": "agent_recipe_runner",
            "provider_type": "agent_recipe_runner",
            "execution_target": "agent_recipe",
            "platforms": ["win32"],
            "evidence": {
                "produces_evidence": True,
                "kind": "endpoint.service",
                "domain": "endpoint",
                "perspective": "endpoint",
                "passport_eligible": True,
            },
        },
    )
    capability_version_id = str(uuid.uuid4())
    capability_version = DiagnosticCapabilityVersion(
        id=capability_version_id,
        capability_id="endpoint.spooler.status",
        version="1.0.0",
        status="published",
        descriptor_json=capability.descriptor_json,
        params_schema_json={"type": "object", "additionalProperties": False},
        output_schema_json={"type": "object"},
        output_contract_json={"status_path": "matches_expected"},
        safety_json={"read_only": True, "side_effects": False},
        evidence_mapping_json=capability.descriptor_json["evidence"],
        deployment_json={"runner_provider_id": "agent_recipe_runner", "min_runner_version": "1.0.0"},
        readiness_json={},
        contract_hash="hash-1",
        is_current=True,
        published_at=datetime.now(timezone.utc),
    )
    recipe_version_id = str(uuid.uuid4())
    recipe = AgentRecipeVersion(
        id=recipe_version_id,
        capability_version_id=capability_version_id,
        recipe_schema_version="1.0",
        runner_provider_id="agent_recipe_runner",
        min_runner_version="1.0.0",
        primitive_id="service.status",
        primitive_version="1.0",
        platforms_json=["win32"],
        platform_variants_json={},
        recipe_json={"params": {"service_name": "Spooler", "expected_state": "running"}},
        parameter_bindings_json={},
        resource_limits_json={"timeout_sec": 10},
        redaction_json={},
        validation_status="passed",
    )
    primitive = AgentRecipePrimitive(
        id=str(uuid.uuid4()),
        runner_provider_id="agent_recipe_runner",
        runner_version="1.0.0",
        primitive_id="service.status",
        primitive_version="1.0",
        title="Service status",
        platforms_json=["win32"],
        params_schema={"type": "object"},
        output_schema={"type": "object"},
        output_contract={"status_path": "matches_expected"},
        safety_json={"read_only": True},
        evidence_defaults_json={"kind": "endpoint.service"},
        resource_limits_json={"timeout_sec": 10},
        redaction_json={},
    )
    session.add(provider)
    await session.flush()
    session.add_all([capability, capability_version])
    await session.flush()
    session.add_all([recipe, primitive])
    if install_runner:
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name="agent_recipe_runner",
                version=runner_version,
                installed=True,
                active=True,
                state="active",
                source="test",
            )
        )
    await session.flush()
    return {"capability_version_id": capability_version_id, "recipe_version_id": recipe_version_id}


async def _seed_preferred_runner_module(session, *, version: str = "1.0.0") -> None:
    session.add(
        Module(
            module_name="agent_recipe_runner",
            version=version,
            sha256="a" * 64,
            size=1234,
            storage_path=f"agent_recipe_runner-{version}.zip",
            uploaded_by="admin",
            manifest_json={
                "module_name": "agent_recipe_runner",
                "module_version": version,
                "owner_scope": "platform",
                "system_module": True,
                "protected": True,
                "platforms": ["win32", "linux"],
            },
            validation_json={"status": "passed"},
        )
    )
    session.add(
        ServerConfig(
            key="module_preferred:agent_recipe_runner",
            value=json.dumps({"module_name": "agent_recipe_runner", "version": version}),
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_agent_recipe_models_persist_and_reject_macos(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = AgentRecipeRepo(session)
        with pytest.raises(AgentRecipeValidationError):
            repo.validate_platforms(["win32", "darwin"])

        ids = await _seed_recipe(session, device_id=str(uuid.uuid4()))
        session.add(
            AgentRecipeTestRun(
                id=str(uuid.uuid4()),
                recipe_version_id=ids["recipe_version_id"],
                platform="win32",
                status="passed",
                result_json={"ok": True},
                artifacts_json=[],
            )
        )
        await session.commit()

    async with session_maker() as session:
        recipe_count = await session.scalar(select(func.count(AgentRecipeVersion.id)))
        primitive_count = await session.scalar(select(func.count(AgentRecipePrimitive.id)))
        test_count = await session.scalar(select(func.count(AgentRecipeTestRun.id)))

    assert recipe_count == 1
    assert primitive_count == 1
    assert test_count == 1


@pytest.mark.asyncio
async def test_recipe_execution_enqueues_run_recipe_not_run_tool(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await _seed_recipe(session, device_id=device_id)
        await session.commit()

    async with session_maker() as session:
        service = RecipeExecutionService(session)
        result = await service.run_recipe_capability(
            ticket_id=ticket_id,
            device_id=device_id,
            capability_id="endpoint.spooler.status",
            params={},
            actor={"actor_role": "support"},
        )
        await session.commit()

    assert result["status"] == "queued", result
    assert result["execution_target"] == "agent_recipe"
    assert result["operation_id"]
    assert result["command"] == "run_recipe"

    async with session_maker() as session:
        operation = await session.scalar(select(Operation).where(Operation.operation_id == result["operation_id"]))
        outbox = await session.scalar(select(DeviceOutbox).where(DeviceOutbox.operation_id == result["operation_id"]))

    assert operation is not None
    assert operation.kind == "agent_recipe"
    assert operation.tool_name == "endpoint.spooler.status"
    assert operation.command_name == "run_recipe"
    assert outbox is not None
    assert outbox.command == "run_recipe"
    assert outbox.params["primitive_id"] == "service.status"
    assert outbox.params["runner_provider_id"] == "agent_recipe_runner"


@pytest.mark.asyncio
async def test_recipe_execution_uses_default_runner_primitives_without_db_seed(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await _seed_recipe(session, device_id=device_id)
        primitive = await session.scalar(
            select(AgentRecipePrimitive).where(AgentRecipePrimitive.primitive_id == "service.status")
        )
        await session.delete(primitive)
        await session.commit()

    async with session_maker() as session:
        service = RecipeExecutionService(session)
        result = await service.run_recipe_capability(
            ticket_id=ticket_id,
            device_id=device_id,
            capability_id="endpoint.spooler.status",
            params={},
            actor={"actor_role": "support"},
        )
        await session.commit()

    assert result["status"] == "queued", result
    assert result["command"] == "run_recipe"


@pytest.mark.asyncio
async def test_recipe_execution_missing_runner_creates_runtime_dependency(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async def fake_install(self, *, parent_operation, plan, actor_role):
        from app.services.operation_service import OperationService
        from modules.reconcile import set_desired_installed

        await set_desired_installed(
            device_id=parent_operation.device_id,
            module_name=plan.module_name,
            desired_version=plan.target_version,
            desired_sha256=plan.module_sha256,
            reason="agent_recipe",
            updated_by=actor_role,
            session=self.session,
        )
        dep_operation_id = str(uuid.uuid4())
        await OperationService(self.session).enqueue_operation(
            operation_id=dep_operation_id,
            device_id=parent_operation.device_id,
            kind="command",
            actor_role="system",
            trace_id=parent_operation.trace_id,
            ticket_id=parent_operation.ticket_id,
            command_name="install_module_package",
        )
        return {"status": "installing", "operation_id": dep_operation_id, "reconcile": {"installs": 1}}

    monkeypatch.setattr(
        "diagnostics.runtime_dependencies.RecipeRunnerDependencyProvider.install_or_upgrade_runner",
        fake_install,
    )

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await _seed_recipe(session, device_id=device_id, install_runner=False)
        await _seed_preferred_runner_module(session, version="1.0.0")
        await session.commit()

    async with session_maker() as session:
        service = RecipeExecutionService(session)
        result = await service.run_recipe_capability(
            ticket_id=ticket_id,
            device_id=device_id,
            capability_id="endpoint.spooler.status",
            params={"sample": True},
            actor={"actor_role": "support"},
        )
        await session.commit()

    assert result["status"] == "waiting_dependency", result
    assert result["phase"] == "installing_runner"
    assert result["dependency"]["action"] == "install_runner"
    assert result["dependency"]["target_version"] == "1.0.0"

    async with session_maker() as session:
        operation = await session.scalar(select(Operation).where(Operation.operation_id == result["operation_id"]))
        dependency = await session.scalar(
            select(OperationDependency).where(OperationDependency.operation_id == result["operation_id"])
        )
        outbox = await session.scalar(select(DeviceOutbox).where(DeviceOutbox.operation_id == result["operation_id"]))
        desired = await session.scalar(
            select(DeviceDesiredModule).where(
                DeviceDesiredModule.device_id == device_id,
                DeviceDesiredModule.module_name == "agent_recipe_runner",
            )
        )

    assert operation is not None
    assert operation.kind == "agent_recipe"
    assert operation.phase == "installing_dependency"
    assert dependency is not None
    assert dependency.status == "installing"
    assert dependency.dependency_operation_id
    assert dependency.metadata_json["runtime_params"] == {"sample": True}
    assert desired is not None
    assert desired.desired_version == "1.0.0"
    assert outbox is None


@pytest.mark.asyncio
async def test_recipe_dependency_resume_is_idempotent(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async def fake_install(self, *, parent_operation, plan, actor_role):
        dep_operation_id = str(uuid.uuid4())
        from app.services.operation_service import OperationService

        await OperationService(self.session).enqueue_operation(
            operation_id=dep_operation_id,
            device_id=parent_operation.device_id,
            kind="command",
            actor_role="system",
            trace_id=parent_operation.trace_id,
            ticket_id=parent_operation.ticket_id,
            command_name="install_module_package",
        )
        return {"status": "installing", "operation_id": dep_operation_id, "reconcile": {"installs": 1}}

    monkeypatch.setattr(
        "diagnostics.runtime_dependencies.RecipeRunnerDependencyProvider.install_or_upgrade_runner",
        fake_install,
    )

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await _seed_recipe(session, device_id=device_id, install_runner=False)
        await _seed_preferred_runner_module(session, version="1.0.0")
        await session.commit()

    async with session_maker() as session:
        service = RecipeExecutionService(session)
        result = await service.run_recipe_capability(
            ticket_id=ticket_id,
            device_id=device_id,
            capability_id="endpoint.spooler.status",
            params={"sample": True},
            actor={"actor_role": "support"},
        )
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name="agent_recipe_runner",
                version="1.0.0",
                installed=True,
                active=True,
                state="active",
                source="test",
            )
        )
        await session.commit()

    async with session_maker() as session:
        service = RecipeExecutionService(session)
        first = await service.resume_after_dependency(result["operation_id"])
        second = await service.resume_after_dependency(result["operation_id"])
        await session.commit()

    assert first["status"] == "resumed"
    assert second["status"] == "ignored"

    async with session_maker() as session:
        outbox_count = await session.scalar(
            select(func.count(DeviceOutbox.id)).where(DeviceOutbox.operation_id == result["operation_id"])
        )
        operation = await session.scalar(select(Operation).where(Operation.operation_id == result["operation_id"]))
        dependency = await session.scalar(
            select(OperationDependency).where(OperationDependency.operation_id == result["operation_id"])
        )

    assert outbox_count == 1
    assert operation.phase == "running_recipe"
    assert dependency.status == "ready"

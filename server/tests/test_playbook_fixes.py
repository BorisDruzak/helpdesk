"""
Тесты для проверки исправлений: capability gate, handshake payload, skipped, metadata validation, list_tools debounce.
Запуск: из директории server: pytest tests/test_playbook_fixes.py -v
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Playbook, PlaybookStep, PlaybookStepRun, PlaybookVersion
from app.services import playbook_engine

# --- Без БД ---


class TestToolMetadataValidation:
    """Контракт metadata: обязательные поля, filter_tools_production_catalog."""

    def test_tool_has_required_metadata_missing_keys(self):
        from utils.tool_metadata_validation import tool_has_required_metadata
        # Нет spec.metadata
        assert tool_has_required_metadata({"tool": "m.t", "spec": {}}) is False
        # Часть ключей
        assert tool_has_required_metadata({
            "tool": "m.t",
            "spec": {"metadata": {"domain": "diag", "platforms": []}}
        }) is False

    def test_tool_has_required_metadata_from_spec(self):
        from utils.tool_metadata_validation import tool_has_required_metadata
        meta = {
            "domain": "diag",
            "platforms": ["linux"],
            "risk_level": "low",
            "requires_consent": False,
            "timeout_sec": 30,
            "idempotent": True,
        }
        assert tool_has_required_metadata({
            "tool": "mod.tool",
            "spec": {"metadata": meta}
        }) is True

    def test_filter_tools_production_catalog(self):
        from utils.tool_metadata_validation import filter_tools_production_catalog
        full_meta = {
            "domain": "diag",
            "platforms": [],
            "risk_level": "low",
            "requires_consent": False,
            "timeout_sec": 10,
            "idempotent": True,
        }
        tools = [
            {"tool": "a.x", "spec": {}},
            {"tool": "b.y", "spec": {"metadata": full_meta}},
        ]
        out = filter_tools_production_catalog(tools)
        assert len(out) == 1
        assert out[0]["tool"] == "b.y"


class TestPlaybookCapabilityMetadataSource:
    """Capability gate читает metadata из tool.spec.metadata."""

    @pytest.mark.no_db
    @pytest.mark.asyncio
    async def test_check_tool_available_async_and_spec_metadata(self):
        from app.services.playbook_capability import check_tool_available
        session = AsyncMock()
        devices_repo = AsyncMock()
        snap_repo = AsyncMock()
        device = MagicMock()
        device.os = "linux"
        devices_repo.get_by_device_id = AsyncMock(return_value=device)
        snapshot = MagicMock()
        snapshot.toolset_json = {
            "tools": [
                {
                    "tool": "ping_check.ping_host",
                    "spec": {"metadata": {"platforms": ["linux"]}},
                }
            ]
        }
        snap_repo.get_latest_snapshot = AsyncMock(return_value=snapshot)
        with patch("app.services.playbook_capability.DevicesRepo", return_value=devices_repo), \
             patch("app.services.playbook_capability.ToolsetSnapshotsRepo", return_value=snap_repo):
            ok, code, msg = await check_tool_available(session, "dev1", "ping_check.ping_host")
        assert ok is True
        assert code is None


class TestOperationsRepoHasPendingListTools:
    """has_pending_list_tools для debounce list_tools."""

    def test_has_pending_list_tools_constants(self):
        from app.repos.operations_repo import OperationsRepo
        assert hasattr(OperationsRepo, "PENDING_STATUSES")
        assert "queued" in OperationsRepo.PENDING_STATUSES
        assert "running" in OperationsRepo.PENDING_STATUSES


class TestPlaybookTypedLocalSteps:
    @pytest.mark.asyncio
    async def test_tool_step_fails_before_enqueue_when_lazy_install_preflight_fails(self, test_engine):
        session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
        device_id = str(uuid.uuid4())

        async with session_maker() as session:
            playbook = Playbook(
                key=f"pb_{uuid.uuid4().hex[:8]}",
                name="Lazy install preflight",
                domain="diag",
                owner="tests",
                archived=False,
            )
            session.add(playbook)
            await session.flush()
            version = PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
            )
            session.add(version)
            await session.flush()
            playbook_version_id = version.id
            session.add(
                PlaybookStep(
                    playbook_version_id=version.id,
                    step_key="get_ip",
                    order_no=10,
                    type="collect",
                    tool="ip_address.get_ip",
                    params_template_json={},
                )
            )
            await session.commit()

        ensure_error = {
            "status": "error",
            "error_code": "MODULE_INSTALL_FAILED",
            "error": "install failed",
        }
        with patch("app.services.playbook_engine.config.CAPABILITY_GATE_STRICT", False), \
             patch("tools.service.ToolExecutionService._ensure_module_installed", AsyncMock(return_value=ensure_error)), \
             patch("app.services.operation_service.OperationService") as operation_service, \
             patch("websocket.protocol.enqueue_command_async", AsyncMock()) as enqueue:
            operation_service.return_value.enqueue_operation = AsyncMock()
            async with session_maker() as session:
                run_id, first_operation_id = await playbook_engine.start_run(
                    session=session,
                    state=MagicMock(),
                    playbook_version_id=playbook_version_id,
                    device_id=device_id,
                    context_json={},
                )
                await session.commit()

        assert first_operation_id is None
        assert operation_service.return_value.enqueue_operation.await_count == 0
        assert enqueue.await_count == 0

        async with session_maker() as session:
            step_run = (
                await session.execute(select(PlaybookStepRun).where(PlaybookStepRun.playbook_run_id == run_id))
            ).scalar_one()
            assert step_run.status == "failed"
            assert step_run.error_json["code"] == "MODULE_INSTALL_FAILED"
            assert step_run.error_json["stage"] == "module_install"

    @pytest.mark.asyncio
    async def test_tool_step_enqueues_after_lazy_install_even_when_snapshot_is_stale(self, test_engine):
        session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
        device_id = str(uuid.uuid4())

        async with session_maker() as session:
            playbook = Playbook(
                key=f"pb_{uuid.uuid4().hex[:8]}",
                name="Lazy install stale snapshot",
                domain="diag",
                owner="tests",
                archived=False,
            )
            session.add(playbook)
            await session.flush()
            version = PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
            )
            session.add(version)
            await session.flush()
            playbook_version_id = version.id
            session.add(
                PlaybookStep(
                    playbook_version_id=version.id,
                    step_key="network_ping",
                    order_no=10,
                    type="collect",
                    tool="network.ping",
                    params_template_json={"target": "127.0.0.1", "count": 1},
                )
            )
            await session.commit()

        operation_service = MagicMock()
        operation_service.return_value.enqueue_operation = AsyncMock()
        enqueue = AsyncMock()
        stale_capability = AsyncMock(return_value=(False, "TOOL_UNAVAILABLE", "No toolset snapshot for device"))

        with patch("app.services.playbook_engine.config.CAPABILITY_GATE_STRICT", True), \
             patch("tools.service.DB_AVAILABLE", True), \
             patch("tools.service.ToolExecutionService._ensure_module_installed", AsyncMock(return_value=None)), \
             patch("app.services.playbook_engine.check_tool_available", stale_capability), \
             patch("app.services.operation_service.OperationService", operation_service), \
             patch("websocket.protocol.enqueue_command_async", enqueue):
            async with session_maker() as session:
                run_id, first_operation_id = await playbook_engine.start_run(
                    session=session,
                    state=MagicMock(),
                    playbook_version_id=playbook_version_id,
                    device_id=device_id,
                    context_json={},
                )
                await session.commit()

        assert first_operation_id
        assert stale_capability.await_count == 0
        assert operation_service.return_value.enqueue_operation.await_count == 1
        assert enqueue.await_count == 1

        async with session_maker() as session:
            step_run = (
                await session.execute(select(PlaybookStepRun).where(PlaybookStepRun.playbook_run_id == run_id))
            ).scalar_one()
            assert step_run.status == "running"
            assert step_run.operation_id == first_operation_id

    @pytest.mark.asyncio
    async def test_start_run_executes_transform_and_decision_steps_without_operations(self, test_engine):
        session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
        playbook_version_id = None

        async with session_maker() as session:
            playbook = Playbook(
                key=f"pb_{uuid.uuid4().hex[:8]}",
                name="Typed local steps",
                domain="diag",
                owner="tests",
                archived=False,
            )
            session.add(playbook)
            await session.flush()
            version = PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
            )
            session.add(version)
            await session.flush()
            playbook_version_id = version.id
            session.add_all(
                [
                    PlaybookStep(
                        playbook_version_id=version.id,
                        step_key="prepare",
                        order_no=10,
                        type="transform",
                        tool=None,
                        params_template_json={"hostname": "{{ context.hostname }}", "mode": "diagnostic"},
                    ),
                    PlaybookStep(
                        playbook_version_id=version.id,
                        step_key="decide",
                        order_no=20,
                        type="decision",
                        tool=None,
                        params_template_json={
                            "rules": [
                                {
                                    "id": "prepared",
                                    "when": "{{ steps.prepare.status == 'success' }}",
                                    "set": "ready",
                                }
                            ],
                            "default": "unknown",
                        },
                    ),
                ]
            )
            await session.commit()

        async with session_maker() as session:
            run_id, first_operation_id = await playbook_engine.start_run(
                session=session,
                state=MagicMock(),
                playbook_version_id=playbook_version_id,
                device_id=str(uuid.uuid4()),
                context_json={"hostname": "site.example"},
            )
            await session.commit()

        assert first_operation_id is None

        async with session_maker() as session:
            step_runs = (
                await session.execute(
                    select(PlaybookStepRun)
                    .where(PlaybookStepRun.playbook_run_id == run_id)
                    .order_by(PlaybookStepRun.id)
                )
            ).scalars().all()
            assert len(step_runs) == 2
            assert step_runs[0].status == "success"
            assert step_runs[0].operation_id is None
            assert step_runs[0].output_json["hostname"] == "site.example"
            assert step_runs[1].status == "success"
            assert step_runs[1].output_json["decision"] == "ready"

    @pytest.mark.asyncio
    async def test_non_agent_capability_step_routes_through_diagnostic_router(self, test_engine):
        session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
        device_id = str(uuid.uuid4())

        async with session_maker() as session:
            playbook = Playbook(
                key=f"pb_{uuid.uuid4().hex[:8]}",
                name="Mixed target playbook",
                domain="diag",
                owner="tests",
                archived=False,
            )
            session.add(playbook)
            await session.flush()
            version = PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={
                    "required_capabilities": [
                        {
                            "capability_id": "observer.ticket.summary",
                            "execution_target": "observer_query",
                        }
                    ]
                },
                status="published",
                created_at=datetime.now(timezone.utc),
            )
            session.add(version)
            await session.flush()
            playbook_version_id = version.id
            session.add(
                PlaybookStep(
                    playbook_version_id=version.id,
                    step_key="observer_summary",
                    order_no=10,
                    type="collect",
                    tool="observer.ticket.summary",
                    params_template_json={"trace_limit": 3},
                )
            )
            await session.commit()

        router_result = {
            "status": "success",
            "capability_id": "observer.ticket.summary",
            "execution_target": "observer_query",
            "execution_kind": "query",
            "summary": "Observer summary: 0 errors",
            "output": {"error_count": 0},
            "evidence_preview": {
                "kind": "observer.summary",
                "domain": "observer",
                "perspective": "observer",
                "title": "Observer summary",
                "summary": "Observer summary: 0 errors",
                "status": "ok",
                "source_type": "observer",
                "source_id": "observer.ticket.summary",
                "artifact_refs": [],
                "trace_id": None,
            },
        }

        with patch("app.services.playbook_engine.CapabilityExecutionRouter", create=True) as router_cls, \
             patch("tools.service.ToolExecutionService._ensure_module_installed", AsyncMock()) as ensure_module, \
             patch("app.services.operation_service.OperationService") as operation_service, \
             patch("websocket.protocol.enqueue_command_async", AsyncMock()) as enqueue:
            router_cls.return_value.run_capability = AsyncMock(return_value=router_result)
            operation_service.return_value.enqueue_operation = AsyncMock()
            async with session_maker() as session:
                run_id, first_operation_id = await playbook_engine.start_run(
                    session=session,
                    state=MagicMock(),
                    playbook_version_id=playbook_version_id,
                    device_id=device_id,
                    context_json={"ticket_id": str(uuid.uuid4())},
                )
                await session.commit()

        assert first_operation_id is None
        assert router_cls.return_value.run_capability.await_count == 1
        assert router_cls.return_value.run_capability.await_args.kwargs["capability_id"] == "observer.ticket.summary"
        assert router_cls.return_value.run_capability.await_args.kwargs["params"] == {"trace_limit": 3}
        assert ensure_module.await_count == 0
        assert operation_service.return_value.enqueue_operation.await_count == 0
        assert enqueue.await_count == 0

        async with session_maker() as session:
            step_run = (
                await session.execute(select(PlaybookStepRun).where(PlaybookStepRun.playbook_run_id == run_id))
            ).scalar_one()
            assert step_run.status == "success"
            assert step_run.operation_id is None
            assert step_run.output_json["execution_target"] == "observer_query"
            run = await playbook_engine.PlaybookRepo(session).get_run_with_step_runs(run_id)
            assert run[0].status == "success"

    @pytest.mark.no_db
    def test_if_expr_supports_steps_alias_and_collections(self):
        from app.utils.playbook_step_eval import evaluate_if_expr

        prev_steps = {
            "http_check": {
                "status": "success",
                "output": {"status_code": 302},
                "error": None,
            }
        }

        assert evaluate_if_expr(
            "{{ steps.http_check.output.status_code in [200, 301, 302] }}",
            context={},
            prev_steps=prev_steps,
        ) is True

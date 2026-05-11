import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from datetime import datetime, timezone
from types import SimpleNamespace

from auth.context import AuthContext, AuthType
from routes import setup_routes
from web_api import admin_handlers
from web_api.dto.admin import (
    AdminBuildIdentity,
    AdminDeviceUpdateAction,
    AdminDeviceUpdateRecommendation,
    AdminDeviceUpdateRunPayload,
    AdminDeviceUpdateSummary,
    AdminDeviceUpdatesPayload,
    AdminFilterOption,
    AdminFormsBuilderCapabilities,
    AdminFormsFieldItem,
    AdminFormsFieldOption,
    AdminFormsFormItem,
    AdminFormsPayload,
    AdminFormsSaveResult,
    AdminFormsSummary,
    AdminFormsVisibleWhen,
    AdminPlaybookBlockCatalogItem,
    AdminPlaybookBuilderCapabilities,
    AdminPlaybookDraftBlock,
    AdminPlaybookDraftRequest,
    AdminPlaybookItem,
    AdminPlaybookPayload,
    AdminPlaybookSaveResult,
    AdminScenarioTemplateItem,
    AdminObserverDangerousFlowItem,
    AdminObserverDegradationItem,
    AdminObserverQuickLinks,
    AdminObserverQuickPayload,
    AdminObserverQuickSummary,
    AdminObserverQuickTrace,
    AdminObserverRuntimeSummary,
    AdminObserverSignatureItem,
    AdminObserverTraceDetailPayload,
    AdminObserverTraceDetailSummary,
    AdminObserverTraceErrorOccurrenceItem,
    AdminObserverTraceItem,
    AdminObserverTraceSpanItem,
    AdminObserverTraceSpanLinkItem,
    AdminObserverTracesFilters,
    AdminObserverTracesLinks,
    AdminObserverTracesPayload,
    AdminObserverTracesQuery,
    AdminObserverTracesSummary,
    AdminModuleFamilyItem,
    AdminModulePreferredRolloutSummary,
    AdminModulePreferredVersionActionPayload,
    AdminModulePreferredVersionRequest,
    AdminModulesPayload,
    AdminModulesRolloutSettings,
    AdminModulesRolloutSettingsUpdateRequest,
    AdminModulesSummary,
    AdminModuleVersionItem,
    AdminRolloutAssignment,
)


@pytest.fixture
async def web_admin_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin1",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_bootstrap_exposes_tech_and_observer_features(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/bootstrap")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["workspace"] == "admin"
    assert "forms_builder" in payload["data"]["features"]
    assert "tech_panel" in payload["data"]["features"]
    assert payload["data"]["observer"]["quick_endpoint"] == "/api/web/admin/observer/quick"
    assert payload["data"]["observer"]["traces_endpoint"] == "/api/web/admin/observer/traces"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_observer_quick_returns_typed_fallback_payload_when_db_is_unavailable(
    web_admin_client,
    monkeypatch,
):
    async def fake_get_quick_diagnosis(self, filters, **_kwargs):
        raise RuntimeError(f"observer unavailable for lookback={filters.lookback_hours}")

    monkeypatch.setattr(admin_handlers.ObserverOverlayService, "get_quick_diagnosis", fake_get_quick_diagnosis)

    response = await web_admin_client.get("/api/web/admin/observer/quick")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["lookback_hours"] == 24
    assert payload["data"]["summary"]["hot_trace_count"] == 0
    assert payload["data"]["runtime"]["health_status"] == "down"
    assert payload["data"]["links"]["quick_endpoint"] == "/api/web/admin/observer/quick"
    assert payload["data"]["links"]["traces_endpoint"] == "/api/web/admin/observer/traces"
    assert payload["data"]["links"]["runtime_endpoint"] == "/api/web/admin/observer/runtime"
    assert payload["data"]["hot_traces"] == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_observer_quick_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_payload(*, request, lookback_hours: int, device_id: str | None):
        assert request.path == "/api/web/admin/observer/quick"
        assert lookback_hours == 72
        assert device_id == "device-1"
        return AdminObserverQuickPayload(
            summary=AdminObserverQuickSummary(
                lookback_hours=lookback_hours,
                recent_trace_count=12,
                hot_trace_count=3,
                signature_count=2,
                degradation_group_count=1,
                dangerous_flow_count=2,
            ),
            runtime=AdminObserverRuntimeSummary(
                enabled=True,
                running=True,
                health_status="ok",
                health_status_label="Норма",
                pending_trace_count=1,
                last_projected_at="2026-04-20T12:00:00+05:00",
                issues=[],
            ),
            hot_traces=[
                AdminObserverQuickTrace(
                    trace_id="trace-1",
                    root_kind="agent_update",
                    root_kind_label="Обновление агента",
                    status="failed",
                    status_label="Ошибка",
                    ticket_id="ticket-1",
                    device_id="device-1",
                    duration_ms=6400,
                    error_count=1,
                    span_count=6,
                    started_at="2026-04-20T11:40:00+05:00",
                    finished_at="2026-04-20T11:40:06+05:00",
                )
            ],
            top_signatures=[
                AdminObserverSignatureItem(
                    error_signature="sig-1",
                    title="Launcher signature mismatch",
                    tool_name="update",
                    component="agent_update",
                    occurrences_count=4,
                    affected_devices_count=2,
                    last_seen_at="2026-04-20T11:45:00+05:00",
                )
            ],
            top_degradations=[
                AdminObserverDegradationItem(
                    operation_kind="tool_call",
                    operation_kind_label="Инструмент",
                    tool_name="network_ping.ping",
                    operations_count=7,
                    timeout_count=2,
                    retried_operations_count=3,
                    slow_operations_count=1,
                    max_duration_ms=9000,
                    latest_operation_at="2026-04-20T11:44:00+05:00",
                )
            ],
            dangerous_flows=[
                AdminObserverDangerousFlowItem(
                    root_kind="agent_update",
                    root_kind_label="Обновление агента",
                    operations_count=5,
                    error_count=2,
                    timeout_count=1,
                    retried_count=1,
                    active_count=0,
                    latest_operation_at="2026-04-20T11:44:00+05:00",
                )
            ],
            links=AdminObserverQuickLinks(
                quick_endpoint="/api/web/admin/observer/quick",
                traces_endpoint="/api/web/admin/observer/traces",
                runtime_endpoint="/api/web/admin/observer/runtime",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_observer_quick_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/observer/quick?lookback_hours=72&device_id=device-1")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["dangerous_flow_count"] == 2
    assert payload["data"]["runtime"]["health_status_label"] == "Норма"
    assert payload["data"]["hot_traces"][0]["root_kind_label"] == "Обновление агента"
    assert payload["data"]["top_signatures"][0]["title"] == "Launcher signature mismatch"
    assert payload["data"]["dangerous_flows"][0]["root_kind"] == "agent_update"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_observer_traces_returns_typed_fallback_payload_when_db_is_unavailable(
    web_admin_client,
    monkeypatch,
):
    async def fake_search(self, filters, *, limit: int):
        raise RuntimeError(f"observer traces unavailable for {filters.device_id}:{limit}")

    monkeypatch.setattr(admin_handlers.ObserverOverlayService, "search_traces", fake_search)

    response = await web_admin_client.get("/api/web/admin/observer/traces?device_id=device-1&lookback_hours=24")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["query"]["device_id"] == "device-1"
    assert payload["data"]["query"]["lookback_hours"] == 24
    assert payload["data"]["summary"]["visible_count"] == 0
    assert payload["data"]["summary"]["selected_trace_id"] is None
    assert payload["data"]["links"]["detail_endpoint_template"] == "/api/web/admin/observer/traces/{trace_id}"
    assert payload["data"]["traces"] == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_observer_traces_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_payload(
        *,
        request,
        device_id: str | None,
        lookback_hours: int,
        status_filter: str,
        root_kind_filter: str,
        limit: int,
        query: str | None,
        trace_id: str | None,
        ticket_id: str | None,
        operation_id: str | None,
        tool_name: str | None,
        module_name: str | None,
        error_signature: str | None,
        min_duration_ms: int | None,
        playbook_run_id: int | None,
        step_run_id: int | None,
        route: str | None,
    ):
        assert request.path == "/api/web/admin/observer/traces"
        assert device_id == "device-1"
        assert lookback_hours == 72
        assert status_filter == "failed"
        assert root_kind_filter == "agent_update"
        assert limit == 25
        assert query == "op-1"
        assert trace_id == "trace-1"
        assert ticket_id == "ticket-1"
        assert operation_id == "op-1"
        assert tool_name == "system.collect"
        assert module_name == "system"
        assert error_signature == "sig-1"
        assert min_duration_ms == 1200
        assert playbook_run_id is None
        assert step_run_id is None
        assert route is None
        return AdminObserverTracesPayload(
            query=AdminObserverTracesQuery(
                device_id=device_id,
                lookback_hours=lookback_hours,
                status_filter=status_filter,
                root_kind_filter=root_kind_filter,
                limit=limit,
                query=query,
                trace_id=trace_id,
                ticket_id=ticket_id,
                operation_id=operation_id,
                tool_name=tool_name,
                module_name=module_name,
                error_signature=error_signature,
                min_duration_ms=min_duration_ms,
            ),
            summary=AdminObserverTracesSummary(
                visible_count=2,
                active_count=0,
                error_count=1,
                selected_trace_id="trace-1",
            ),
            filters=AdminObserverTracesFilters(
                status_options=[
                    AdminFilterOption(value="all", label="Все статусы"),
                    AdminFilterOption(value="failed", label="С ошибкой"),
                ],
                root_kind_options=[
                    AdminFilterOption(value="all", label="Все потоки"),
                    AdminFilterOption(value="agent_update", label="Обновление агента"),
                ],
            ),
            traces=[
                AdminObserverTraceItem(
                    trace_id="trace-1",
                    root_span_id="span-root-1",
                    root_kind="agent_update",
                    root_kind_label="Обновление агента",
                    status="failed",
                    status_label="Ошибка",
                    ticket_id="ticket-1",
                    device_id=device_id,
                    operation_id="op-1",
                    job_id=None,
                    duration_ms=6400,
                    error_count=1,
                    span_count=6,
                    started_at="2026-04-20T11:40:00+05:00",
                    finished_at="2026-04-20T11:40:06+05:00",
                    attrs_json={"flow": "agent_update"},
                ),
                AdminObserverTraceItem(
                    trace_id="trace-2",
                    root_span_id="span-root-2",
                    root_kind="agent_update",
                    root_kind_label="Обновление агента",
                    status="succeeded",
                    status_label="Успешно",
                    ticket_id="ticket-2",
                    device_id=device_id,
                    operation_id="op-2",
                    job_id=None,
                    duration_ms=2900,
                    error_count=0,
                    span_count=4,
                    started_at="2026-04-20T11:35:00+05:00",
                    finished_at="2026-04-20T11:35:02+05:00",
                    attrs_json={},
                ),
            ],
            links=AdminObserverTracesLinks(
                detail_endpoint_template="/api/web/admin/observer/traces/{trace_id}",
                runtime_endpoint="/api/web/admin/observer/runtime",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_observer_traces_payload", fake_build_payload)

    response = await web_admin_client.get(
        "/api/web/admin/observer/traces?device_id=device-1&lookback_hours=72&status=failed&root_kind=agent_update&limit=25"
        "&q=op-1&trace_id=trace-1&ticket_id=ticket-1&operation_id=op-1&tool_name=system.collect"
        "&module_name=system&error_signature=sig-1&min_duration_ms=1200"
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["visible_count"] == 2
    assert payload["data"]["summary"]["selected_trace_id"] == "trace-1"
    assert payload["data"]["traces"][0]["operation_id"] == "op-1"
    assert payload["data"]["traces"][0]["attrs_json"]["flow"] == "agent_update"
    assert payload["data"]["query"]["operation_id"] == "op-1"
    assert payload["data"]["query"]["tool_name"] == "system.collect"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_observer_trace_detail_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_detail(*, request, trace_id: str):
        assert request.path == f"/api/web/admin/observer/traces/{trace_id}"
        assert trace_id == "trace-1"
        return AdminObserverTraceDetailPayload(
            trace=AdminObserverTraceItem(
                trace_id="trace-1",
                root_span_id="span-root-1",
                root_kind="agent_update",
                root_kind_label="Обновление агента",
                status="failed",
                status_label="Ошибка",
                ticket_id="ticket-1",
                device_id="device-1",
                operation_id="op-1",
                job_id=None,
                duration_ms=6400,
                error_count=1,
                span_count=3,
                started_at="2026-04-20T11:40:00+05:00",
                finished_at="2026-04-20T11:40:06+05:00",
                attrs_json={"flow": "agent_update"},
            ),
            summary=AdminObserverTraceDetailSummary(
                span_count=3,
                error_count=1,
                linked_trace_count=1,
            ),
            spans=[
                AdminObserverTraceSpanItem(
                    span_id="span-root-1",
                    trace_id="trace-1",
                    parent_span_id=None,
                    source_type="operation",
                    source_ref="op-1",
                    name="operation.agent_update",
                    kind="internal",
                    component="operation",
                    event_type="agent_update",
                    module_name=None,
                    tool_name=None,
                    status="failed",
                    status_label="Ошибка",
                    started_at="2026-04-20T11:40:00+05:00",
                    finished_at="2026-04-20T11:40:06+05:00",
                    duration_ms=6400,
                    attrs_json={},
                )
            ],
            span_links=[
                AdminObserverTraceSpanLinkItem(
                    id=11,
                    span_id="span-root-1",
                    linked_trace_id="trace-related-1",
                    linked_span_id="span-related-1",
                    reason="child_trace",
                    attrs_json={"edge": "child"},
                    created_at="2026-04-20T11:40:07+05:00",
                )
            ],
            error_occurrences=[
                AdminObserverTraceErrorOccurrenceItem(
                    occurrence_id="occ-1",
                    trace_id="trace-1",
                    span_id="span-root-1",
                    error_signature="sig-1",
                    device_id="device-1",
                    ticket_id="ticket-1",
                    operation_id="op-1",
                    component="agent_update",
                    module_name=None,
                    tool_name=None,
                    error_kind="runtime_error",
                    exception_type="RuntimeError",
                    failure_stage="delivery",
                    severity="error",
                    severity_label="Ошибка",
                    message_norm="update delivery failed",
                    stack_hash="stack-1",
                    attrs_json={"code": "DELIVERY_FAILED"},
                    created_at="2026-04-20T11:40:06+05:00",
                )
            ],
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_observer_trace_detail_payload", fake_build_detail)

    response = await web_admin_client.get("/api/web/admin/observer/traces/trace-1")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["trace"]["trace_id"] == "trace-1"
    assert payload["data"]["summary"]["linked_trace_count"] == 1
    assert payload["data"]["spans"][0]["status_label"] == "Ошибка"
    assert payload["data"]["error_occurrences"][0]["severity_label"] == "Ошибка"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_devices_returns_typed_fallback_payload_when_db_is_unavailable(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/devices")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["query"] == ""
    assert payload["data"]["status_filter"] == "all"
    assert payload["data"]["summary"]["visible_count"] == 0
    assert payload["data"]["summary"]["online_count"] == 0
    assert payload["data"]["summary"]["rollout_targets"] == 0
    assert payload["data"]["summary"]["duplicate_hosts"] == 0
    assert payload["data"]["summary"]["cleanup_candidates"] == 0
    assert payload["data"]["rollout"] == []
    assert payload["data"]["devices"] == []
    assert payload["data"]["filters"]["status_options"][0] == {
        "value": "all",
        "label": "Все устройства",
    }


@pytest.mark.no_db
def test_web_admin_device_item_marks_env_uuid_duplicates():
    stable_device = SimpleNamespace(
        device_id="11111111-1111-1111-1111-111111111111",
        hostname="ADMIN-2",
        os="Windows",
        agent_version="3.1.21",
        last_seen_at=None,
        device_metadata={
            "machine_id_source": "windows_machine_guid",
            "identity_scheme": "machine_id_v1",
            "install_id": "22222222-2222-4222-8222-222222222222",
        },
    )
    env_device = SimpleNamespace(
        device_id="33333333-3333-4333-8333-333333333333",
        hostname="ADMIN-2",
        os="Windows",
        agent_version="3.1.20",
        last_seen_at=None,
        device_metadata={
            "machine_id_source": "env_uuid",
            "identity_scheme": "machine_id_v1",
            "install_id": "44444444-4444-4444-8444-444444444444",
        },
    )
    state = SimpleNamespace(is_agent_online=lambda device_id: device_id == stable_device.device_id)

    duplicate_index = admin_handlers._build_duplicate_index([stable_device, env_device], state=state)
    stable_item = admin_handlers._build_device_item(stable_device, online=True, duplicate_index=duplicate_index)
    env_item = admin_handlers._build_device_item(env_device, online=False, duplicate_index=duplicate_index)

    assert stable_item.identity_summary.source_label == "Windows MachineGuid"
    assert stable_item.identity_summary.is_stable is True
    assert stable_item.duplicate_warning.kind == "hostname_has_env_uuid_duplicates"
    assert stable_item.duplicate_warning.cleanup_available is True

    assert env_item.identity_summary.source_label == "Тестовый ENV UUID"
    assert env_item.identity_summary.is_stable is False
    assert env_item.duplicate_warning.kind == "env_uuid_duplicate"
    assert env_item.duplicate_warning.cleanup_available is True


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_modules_returns_typed_fallback_payload_when_db_is_unavailable(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/modules")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["query"] == ""
    assert payload["data"]["summary"] == {
        "visible_count": 0,
        "preferred_count": 0,
        "invalid_count": 0,
        "missing_files_count": 0,
    }
    assert payload["data"]["rollout_settings"] == {
        "preferred_version_rollout_mode": "manual",
        "preferred_version_rollout_mode_label": "Только вручную",
        "sync_after_preferred_change": True,
    }
    assert payload["data"]["modules"] == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_modules_returns_typed_registry_payload(web_admin_client, monkeypatch):
    async def fake_build_payload(*, query: str):
        assert query == "network"
        return AdminModulesPayload(
            query=query,
            summary=AdminModulesSummary(
                visible_count=1,
                preferred_count=1,
                invalid_count=1,
                missing_files_count=0,
            ),
            rollout_settings=AdminModulesRolloutSettings(
                preferred_version_rollout_mode="installed_devices",
                preferred_version_rollout_mode_label="Обновлять установленные устройства",
                sync_after_preferred_change=False,
            ),
            modules=[
                AdminModuleFamilyItem(
                    module_name="network_ping",
                    preferred_version="1.2.0",
                    preferred_assigned=True,
                    latest_version="1.2.1",
                    owner_scope="vendor",
                    module_api_version="2.0.0",
                    validation_status="warning",
                    validation_status_label="Есть предупреждения",
                    version_count=2,
                    tools_count=2,
                    platforms=["windows_amd64", "linux_alt_x86_64"],
                    tool_ids=["network_ping.ping", "network_ping.trace"],
                    warnings_count=1,
                    has_missing_files=False,
                    versions=[
                        AdminModuleVersionItem(
                            version="1.2.1",
                            created_at="2026-04-20T11:10:00+05:00",
                            uploaded_by="admin",
                            manifest_version=2,
                            module_api_version="2.0.0",
                            owner_scope="vendor",
                            validation_status="warning",
                            validation_status_label="Есть предупреждения",
                            preflight_status="passed",
                            preflight_status_label="Проверен",
                            is_preferred=False,
                            tools_count=2,
                            platforms=["windows_amd64", "linux_alt_x86_64"],
                            tool_ids=["network_ping.ping", "network_ping.trace"],
                            warnings_count=1,
                            file_exists=True,
                        ),
                        AdminModuleVersionItem(
                            version="1.2.0",
                            created_at="2026-04-19T10:00:00+05:00",
                            uploaded_by="admin",
                            manifest_version=2,
                            module_api_version="2.0.0",
                            owner_scope="vendor",
                            validation_status="passed",
                            validation_status_label="Проверен",
                            preflight_status="passed",
                            preflight_status_label="Проверен",
                            is_preferred=True,
                            tools_count=2,
                            platforms=["windows_amd64", "linux_alt_x86_64"],
                            tool_ids=["network_ping.ping", "network_ping.trace"],
                            warnings_count=0,
                            file_exists=True,
                        ),
                    ],
                )
            ],
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_modules_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/modules?query=network")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["visible_count"] == 1
    assert payload["data"]["rollout_settings"]["preferred_version_rollout_mode"] == "installed_devices"
    assert payload["data"]["modules"][0]["module_name"] == "network_ping"
    assert payload["data"]["modules"][0]["versions"][1]["is_preferred"] is True
    assert payload["data"]["modules"][0]["tool_ids"] == ["network_ping.ping", "network_ping.trace"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_current_returns_typed_fallback_payload_when_db_is_unavailable(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/forms/current")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["pack_key"] == "request_forms"
    assert payload["data"]["summary"]["forms_count"] >= 1
    assert payload["data"]["summary"]["last_published_by"] == "builtin_default"
    assert payload["data"]["capabilities"]["current_endpoint"] == "/api/web/admin/forms/current"
    assert payload["data"]["capabilities"]["save_endpoint"] == "/api/web/admin/forms/save"
    assert payload["data"]["capabilities"]["preview_endpoint"] == "/api/web/admin/forms/route-preview"
    role_values = {item["value"] for item in payload["data"]["capabilities"]["field_role_options"]}
    assert {"priority_impact", "priority_urgency", "priority_importance"} <= role_values
    assert payload["data"]["forms"][0]["fields"][0]["type_label"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_current_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_payload():
        return AdminFormsPayload(
            summary=AdminFormsSummary(
                pack_key="request_forms",
                version="1.0.3",
                title="Каталог заявок",
                description="Каталог для операторов",
                forms_count=1,
                fields_count=2,
                required_fields_count=1,
                last_published_at="2026-04-21T10:00:00+05:00",
                last_published_by="admin1",
            ),
            capabilities=AdminFormsBuilderCapabilities(
                current_endpoint="/api/web/admin/forms/current",
                save_endpoint="/api/web/admin/forms/save",
                preview_endpoint="/api/web/admin/forms/route-preview",
                process_preview_endpoint="/api/web/admin/forms/process-preview",
                field_type_options=[
                    AdminFilterOption(value="text", label="Текст"),
                    AdminFilterOption(value="select", label="Список"),
                ],
            ),
            forms=[
                AdminFormsFormItem(
                    key="printer",
                    request_kind="printer",
                    title="Печать / принтер",
                    description="Описывает проблемы печати",
                    fields=[
                        AdminFormsFieldItem(
                            key="room",
                            label="Кабинет",
                            type="text",
                            type_label="Текст",
                            required=True,
                        ),
                        AdminFormsFieldItem(
                            key="printer_model",
                            label="Модель",
                            type="select",
                            type_label="Список",
                            required=False,
                            options=[
                                AdminFormsFieldOption(value="hp", label="HP"),
                                AdminFormsFieldOption(value="canon", label="Canon"),
                            ],
                            visible_when=AdminFormsVisibleWhen(field="room", equals="214"),
                        ),
                    ],
                )
            ],
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_forms_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/forms/current")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["version"] == "1.0.3"
    assert payload["data"]["forms"][0]["key"] == "printer"
    assert payload["data"]["capabilities"]["preview_endpoint"] == "/api/web/admin/forms/route-preview"
    assert payload["data"]["capabilities"]["process_preview_endpoint"] == "/api/web/admin/forms/process-preview"
    assert payload["data"]["forms"][0]["fields"][1]["options"][0]["label"] == "HP"
    assert payload["data"]["forms"][0]["fields"][1]["visible_when"]["field"] == "room"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_save_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_save_pack(*, auth_context, payload):
        assert auth_context.actor_role == "admin"
        assert payload.forms[0].key == "printer"
        assert payload.forms[0].fields[0].key == "room"
        return AdminFormsSaveResult(
            summary=AdminFormsSummary(
                pack_key="request_forms",
                version="1.0.4",
                title="Каталог заявок",
                description="Публикация после правки",
                forms_count=1,
                fields_count=2,
                required_fields_count=1,
                last_published_at="2026-04-21T10:15:00+05:00",
                last_published_by="admin1",
            ),
            forms=[
                AdminFormsFormItem(
                    key="printer",
                    request_kind="printer",
                    title="Печать / принтер",
                    description="Проверка публикации",
                    fields=[
                        AdminFormsFieldItem(
                            key="room",
                            label="Кабинет",
                            type="text",
                            type_label="Текст",
                            required=True,
                        ),
                        AdminFormsFieldItem(
                            key="printer_model",
                            label="Модель",
                            type="text",
                            type_label="Текст",
                            required=False,
                        ),
                    ],
                )
            ],
            message="Каталог опубликован как версия 1.0.4. Изменения уже активны в /help и в интерфейсе агента.",
        )

    monkeypatch.setattr(admin_handlers, "_save_admin_forms_pack", fake_save_pack)

    response = await web_admin_client.post(
        "/api/web/admin/forms/save",
        json={
            "title": "Каталог заявок",
            "description": "Публикация после правки",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "description": "Проверка публикации",
                    "fields": [
                        {
                            "key": "room",
                            "label": "Кабинет",
                            "type": "text",
                            "required": True,
                            "options": [],
                        },
                        {
                            "key": "printer_model",
                            "label": "Модель",
                            "type": "text",
                            "required": False,
                            "options": [],
                        },
                    ],
                }
            ],
        },
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["version"] == "1.0.4"
    assert payload["data"]["summary"]["last_published_by"] == "admin1"
    assert payload["data"]["forms"][0]["fields"][0]["required"] is True
    assert "Каталог опубликован как версия 1.0.4" in payload["data"]["message"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_save_draft_does_not_publish_or_prefer(web_admin_client, monkeypatch):
    async def fake_save_draft(*, auth_context, payload):
        assert auth_context.actor_role == "admin"
        assert payload.forms[0].key == "printer"
        return {
            "draft_id": "draft-1",
            "pack_key": "request_forms",
            "base_version": "1.0.3",
            "status": "draft",
            "summary": {
                "pack_key": "request_forms",
                "version": "draft",
                "title": "Каталог заявок",
                "description": "Черновик",
                "forms_count": 1,
                "fields_count": 1,
                "required_fields_count": 1,
                "last_published_at": None,
                "last_published_by": None,
            },
            "published_version": None,
            "preferred_version": "1.0.3",
            "message": "Черновик сохранён. Активная версия не изменилась.",
        }

    monkeypatch.setattr(admin_handlers, "_save_admin_forms_draft", fake_save_draft, raising=False)

    response = await web_admin_client.post(
        "/api/web/admin/forms/save-draft",
        json={
            "base_version": "1.0.3",
            "title": "Каталог заявок",
            "description": "Черновик",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "fields": [{"key": "room", "label": "Кабинет", "type": "text", "required": True}],
                }
            ],
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["draft_id"] == "draft-1"
    assert payload["data"]["status"] == "draft"
    assert payload["data"]["published_version"] is None
    assert payload["data"]["preferred_version"] == "1.0.3"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_validate_returns_report_without_publishing(web_admin_client, monkeypatch):
    async def fake_validate(*, payload):
        assert payload.base_version == "1.0.3"
        assert payload.draft_id == "draft-1"
        assert payload.forms[0].key == "printer"
        return {
            "status": "validated",
            "summary": {"errors_count": 0, "warnings_count": 1, "can_publish": True},
            "errors": [],
            "warnings": [
                {
                    "code": "REQUIRED_FIELD_WITHOUT_HELP_TEXT",
                    "message": "Обязательное поле не содержит подсказку",
                    "path": "forms[0].fields[0].help_text",
                    "recommendation": "Добавьте help_text для пользователя",
                }
            ],
            "message": "Проверка завершена: публикация разрешена.",
        }

    monkeypatch.setattr(admin_handlers, "_validate_admin_forms_draft", fake_validate, raising=False)

    response = await web_admin_client.post(
        "/api/web/admin/forms/validate",
        json={
            "base_version": "1.0.3",
            "draft_id": "draft-1",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "fields": [{"key": "room", "label": "Кабинет", "type": "text", "required": True}],
                }
            ],
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "validated"
    assert payload["data"]["summary"]["can_publish"] is True
    assert payload["data"]["warnings"][0]["code"] == "REQUIRED_FIELD_WITHOUT_HELP_TEXT"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_publish_can_skip_preferred_switch(web_admin_client, monkeypatch):
    async def fake_publish(*, auth_context, payload):
        assert auth_context.actor_role == "admin"
        assert payload.base_version == "1.0.3"
        assert payload.draft_id == "draft-1"
        assert payload.make_preferred is False
        return {
            "summary": {
                "pack_key": "request_forms",
                "version": "1.0.4",
                "title": "Каталог заявок",
                "description": None,
                "forms_count": 1,
                "fields_count": 1,
                "required_fields_count": 1,
                "last_published_at": "2026-05-11T10:00:00+05:00",
                "last_published_by": "admin1",
            },
            "forms": [],
            "published_version": "1.0.4",
            "preferred_version": "1.0.3",
            "made_preferred": False,
            "message": "Каталог опубликован как версия 1.0.4. Активная версия не изменилась.",
        }

    monkeypatch.setattr(admin_handlers, "_publish_admin_forms_draft", fake_publish, raising=False)

    response = await web_admin_client.post(
        "/api/web/admin/forms/publish",
        json={
            "base_version": "1.0.3",
            "draft_id": "draft-1",
            "make_preferred": False,
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "fields": [{"key": "room", "label": "Кабинет", "type": "text", "required": True}],
                }
            ],
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["published_version"] == "1.0.4"
    assert payload["data"]["preferred_version"] == "1.0.3"
    assert payload["data"]["made_preferred"] is False


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_preferred_switches_existing_version(web_admin_client, monkeypatch):
    async def fake_set_preferred(*, auth_context, payload):
        assert auth_context.actor_role == "admin"
        assert payload.version == "1.0.4"
        return {
            "pack_key": "request_forms",
            "previous_version": "1.0.3",
            "preferred_version": "1.0.4",
            "message": "Активная версия каталога обновлена: 1.0.4.",
        }

    monkeypatch.setattr(admin_handlers, "_set_admin_forms_preferred", fake_set_preferred, raising=False)

    response = await web_admin_client.patch(
        "/api/web/admin/forms/preferred",
        json={"version": "1.0.4"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["previous_version"] == "1.0.3"
    assert payload["data"]["preferred_version"] == "1.0.4"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_save_accepts_request_template_process_context(web_admin_client, monkeypatch):
    async def fake_save_pack(*, auth_context, payload):
        form = payload.forms[0]
        assert form.ticket_type == "incident"
        assert form.category_id == 10
        assert form.service_id == 20
        assert form.subcategory_id == 30
        assert form.default_queue_id == 40
        assert form.sla_policy_id == 50
        assert form.suggested_playbook_id == "diagnose.website"
        assert form.field_roles == {"url": ["routing_field", "diagnostic_input"]}
        assert form.priority_policy == {"impact_field": "affected_scope", "urgency_field": "work_continuity"}
        assert form.routing_policy == {"default_queue_id": 40}
        assert form.approval_policy == {"required": False}
        assert form.closure_policy == {"require_resolution_code": True}
        assert form.visibility_policy == {"operator_fields": ["url"]}
        assert form.notification_policy == {"on_status_changed": {"requester": True}}
        assert form.ola_policy == {"use_queue_targets": True}
        return AdminFormsSaveResult(
            summary=AdminFormsSummary(
                pack_key="request_forms",
                version="1.0.5",
                title="Каталог заявок",
                description="Process template catalog",
                forms_count=1,
                fields_count=1,
                required_fields_count=1,
                last_published_at="2026-04-29T10:15:00+05:00",
                last_published_by="admin1",
            ),
            forms=[
                AdminFormsFormItem(
                    key="website_unavailable",
                    request_kind="website_unavailable",
                    ticket_type="incident",
                    title="Не открывается сайт",
                    description="Website incident",
                    category_id=10,
                    service_id=20,
                    subcategory_id=30,
                    default_queue_id=40,
                    sla_policy_id=50,
                    suggested_playbook_id="diagnose.website",
                    field_roles={"url": ["routing_field", "diagnostic_input"]},
                    priority_policy={"impact_field": "affected_scope", "urgency_field": "work_continuity"},
                    routing_policy={"default_queue_id": 40},
                    approval_policy={"required": False},
                    closure_policy={"require_resolution_code": True},
                    visibility_policy={"operator_fields": ["url"]},
                    notification_policy={"on_status_changed": {"requester": True}},
                    ola_policy={"use_queue_targets": True},
                    fields=[
                        AdminFormsFieldItem(
                            key="url",
                            label="URL",
                            type="text",
                            type_label="Текст",
                            required=True,
                        )
                    ],
                )
            ],
            message="ok",
        )

    monkeypatch.setattr(admin_handlers, "_save_admin_forms_pack", fake_save_pack)

    response = await web_admin_client.post(
        "/api/web/admin/forms/save",
        json={
            "title": "Каталог заявок",
            "description": "Process template catalog",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "ticket_type": "incident",
                    "title": "Не открывается сайт",
                    "description": "Website incident",
                    "category_id": 10,
                    "service_id": 20,
                    "subcategory_id": 30,
                    "default_queue_id": 40,
                    "sla_policy_id": 50,
                    "suggested_playbook_id": "diagnose.website",
                    "field_roles": {"url": ["routing_field", "diagnostic_input"]},
                    "priority_policy": {"impact_field": "affected_scope", "urgency_field": "work_continuity"},
                    "routing_policy": {"default_queue_id": 40},
                    "approval_policy": {"required": False},
                    "closure_policy": {"require_resolution_code": True},
                    "visibility_policy": {"operator_fields": ["url"]},
                    "notification_policy": {"on_status_changed": {"requester": True}},
                    "ola_policy": {"use_queue_targets": True},
                    "fields": [
                        {"key": "url", "label": "URL", "type": "text", "required": True, "options": []},
                    ],
                }
            ],
        },
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    form = payload["data"]["forms"][0]
    assert form["ticket_type"] == "incident"
    assert form["field_roles"]["url"] == ["routing_field", "diagnostic_input"]
    assert form["priority_policy"]["impact_field"] == "affected_scope"
    assert form["notification_policy"]["on_status_changed"]["requester"] is True


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_route_preview_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_preview(*, payload):
        assert payload.form.key == "printer"
        assert payload.form.request_kind == "printer"
        assert payload.form_payload == {"room": "214", "printer_model": "HP LaserJet"}
        return {
            "ticket_type": "printer",
            "request_kind": "printer",
            "target_queue_id": 17,
            "target_queue_name": "Printer 214",
            "fallback_applied": False,
            "matched_rule": {
                "id": 5,
                "priority_order": 10,
                "target_queue_id": 17,
                "target_queue_name": "Printer 214",
                "condition_json": {"field": "request_form_data.room", "op": "eq", "value": "214"},
            },
            "summary_rows": [
                {"key": "room", "label": "Кабинет", "value": "214"},
                {"key": "printer_model", "label": "Модель", "value": "HP LaserJet"},
            ],
        }

    monkeypatch.setattr(admin_handlers, "_preview_admin_forms_route", fake_preview)

    response = await web_admin_client.post(
        "/api/web/admin/forms/route-preview",
        json={
            "form": {
                "key": "printer",
                "request_kind": "printer",
                "title": "Принтер",
                "description": "Preview form",
                "fields": [
                    {
                        "key": "room",
                        "label": "Кабинет",
                        "type": "text",
                        "required": True,
                        "options": [],
                    },
                    {
                        "key": "printer_model",
                        "label": "Модель",
                        "type": "text",
                        "required": False,
                        "options": [],
                    },
                ],
            },
            "form_payload": {
                "room": "214",
                "printer_model": "HP LaserJet",
            },
        },
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_type"] == "printer"
    assert payload["data"]["request_kind"] == "printer"
    assert payload["data"]["target_queue_name"] == "Printer 214"
    assert payload["data"]["fallback_applied"] is False
    assert payload["data"]["matched_rule"]["id"] == 5
    assert payload["data"]["matched_rule"]["condition_json"]["field"] == "request_form_data.room"
    assert payload["data"]["summary_rows"][0]["label"] == "Кабинет"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_process_preview_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_preview(*, payload):
        assert payload.form.key == "printer"
        assert payload.form_payload == {"room": "214", "printer_model": "HP LaserJet"}
        return {
            "ticket_type": "incident",
            "request_kind": "printer",
            "priority": {"priority_class": "P2", "priority_reason": "impact=2"},
            "routing": {
                "source": "ticket_routing_rule",
                "target_queue_id": 17,
                "target_queue_name": "Printer 214",
                "fallback_applied": False,
                "matched_rule": {"id": 5, "priority_order": 10},
            },
            "sla": {"policy_code": "incident_sla", "first_response_min": 60, "resolution_min": 240},
            "ola": {"policy_code": "printer_ola", "ack_min": 15, "processing_min": 120},
            "approval": {"required": False},
            "diagnostics": {"suggested_playbooks": ["diagnose.printer"], "auto_run_enabled": True},
            "closure": {"requires_resolution_code": True},
            "visibility": {"public_status_mapping": {"new": "received"}},
            "notifications": {"events": ["on_ticket_created"]},
            "summary_rows": [{"key": "room", "label": "Кабинет", "value": "214"}],
            "validation_report": {"summary": {"errors_count": 0, "warnings_count": 0, "can_publish": True}, "errors": [], "warnings": []},
            "preview_metadata": {"side_effects": []},
        }

    monkeypatch.setattr(admin_handlers, "_preview_admin_forms_process", fake_preview)

    response = await web_admin_client.post(
        "/api/web/admin/forms/process-preview",
        json={
            "form": {
                "key": "printer",
                "request_kind": "printer",
                "ticket_type": "incident",
                "title": "Принтер",
                "fields": [
                    {"key": "room", "label": "Кабинет", "type": "text", "required": True, "options": []},
                    {"key": "printer_model", "label": "Модель", "type": "text", "required": False, "options": []},
                ],
            },
            "form_payload": {"room": "214", "printer_model": "HP LaserJet"},
        },
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_type"] == "incident"
    assert payload["data"]["routing"]["target_queue_name"] == "Printer 214"
    assert payload["data"]["priority"]["priority_class"] == "P2"
    assert payload["data"]["diagnostics"]["suggested_playbooks"] == ["diagnose.printer"]
    assert payload["data"]["preview_metadata"]["side_effects"] == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_playbooks_catalog_returns_diagnostic_builder_payload(web_admin_client, monkeypatch):
    async def fake_build_payload():
        return AdminPlaybookPayload(
            capabilities=AdminPlaybookBuilderCapabilities(
                catalog_endpoint="/api/web/admin/playbooks/catalog",
                save_endpoint="/api/web/admin/playbooks/save",
                block_types=[
                    AdminFilterOption(value="diagnostic", label="Диагностика"),
                    AdminFilterOption(value="decision", label="Условие"),
                    AdminFilterOption(value="report", label="Пакет фактов"),
                ],
                module_kind_options=[
                    AdminFilterOption(value="diagnostic", label="Диагностика"),
                    AdminFilterOption(value="remediation", label="Исправление"),
                ],
            ),
            block_catalog=[
                AdminPlaybookBlockCatalogItem(
                    id="system.collect",
                    label="Системный снимок",
                    tool="system.collect",
                    block_type="diagnostic",
                    module_kind="diagnostic",
                    description="CPU, память, сеть и платформа",
                    default_params={"preset": "network"},
                    changes_device=False,
                    requires_confirmation=False,
                    output_contract={
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "success_values": ["ok"],
                        "error_values": ["error"],
                        "summary_path": "result.output.summary",
                    },
                    condition_hints={
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "condition_templates": [
                            {"label": "status == ok", "expression": "{step}.output.result.status == 'ok'"}
                        ],
                    },
                )
            ],
            scenario_templates=[
                AdminScenarioTemplateItem(
                    key="site_not_opening",
                    title="Сайт не открывается",
                    problem="site_not_opening",
                    recommended_form_keys=["site_system"],
                    block_ids=["system.collect"],
                )
            ],
            playbooks=[
                AdminPlaybookItem(
                    key="site_not_opening",
                    name="Сайт не открывается",
                    domain="network",
                    version="1.0.0",
                    status="published",
                    blocks_count=1,
                    updated_at=None,
                )
            ],
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_playbooks_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/playbooks/catalog")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["block_catalog"][0]["module_kind"] == "diagnostic"
    assert payload["data"]["block_catalog"][0]["output_contract"]["status_values"] == ["ok", "error"]
    assert payload["data"]["block_catalog"][0]["condition_hints"]["status_path"] == "result.status"
    assert payload["data"]["scenario_templates"][0]["recommended_form_keys"] == ["site_system"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_playbooks_save_returns_published_playbook(web_admin_client, monkeypatch):
    async def fake_save_playbook(*, auth_context, payload):
        assert auth_context.actor_role == "admin"
        assert payload.key == "site_not_opening"
        assert payload.blocks[0].tool == "system.collect"
        return AdminPlaybookSaveResult(
            key="site_not_opening",
            version="1.0.1",
            status="published",
            blocks_count=2,
            message="Плейбук опубликован как версия 1.0.1.",
        )

    monkeypatch.setattr(admin_handlers, "_save_admin_playbook", fake_save_playbook)

    response = await web_admin_client.post(
        "/api/web/admin/playbooks/save",
        json={
            "key": "site_not_opening",
            "name": "Сайт не открывается",
            "domain": "network",
            "blocks": [
                {
                    "id": "collect_network",
                    "type": "diagnostic",
                    "module_kind": "diagnostic",
                    "tool": "system.collect",
                    "params": {"preset": "network"},
                },
                {
                    "id": "facts",
                    "type": "report",
                    "module_kind": "diagnostic",
                    "params": {"title": "Пакет фактов"},
                },
            ],
        },
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["key"] == "site_not_opening"
    assert payload["data"]["blocks_count"] == 2


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_forms_save_rejects_invalid_payload(web_admin_client):
    response = await web_admin_client.post(
        "/api/web/admin/forms/save",
        json={"title": "Каталог заявок", "forms": []},
    )

    assert response.status == 400
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_patch_modules_rollout_settings_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_patch_settings(*, preferred_version_rollout_mode: str | None, sync_after_preferred_change: bool | None):
        assert preferred_version_rollout_mode == "manual"
        assert sync_after_preferred_change is True
        return AdminModulesRolloutSettings(
            preferred_version_rollout_mode="manual",
            preferred_version_rollout_mode_label="Только вручную",
            sync_after_preferred_change=True,
        )

    monkeypatch.setattr(admin_handlers, "_patch_admin_modules_rollout_settings", fake_patch_settings)

    response = await web_admin_client.patch(
        "/api/web/admin/modules/rollout_settings",
        json={"preferred_version_rollout_mode": "manual", "sync_after_preferred_change": True},
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["preferred_version_rollout_mode"] == "manual"
    assert payload["data"]["preferred_version_rollout_mode_label"] == "Только вручную"
    assert payload["data"]["sync_after_preferred_change"] is True


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_set_module_preferred_version_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_set_preferred(*, request, auth_context, module_name: str, version: str | None):
        assert request.path == "/api/web/admin/modules/network_ping/preferred"
        assert auth_context.actor_role == "admin"
        assert module_name == "network_ping"
        assert version == "1.2.1"
        return AdminModulePreferredVersionActionPayload(
            module_name=module_name,
            preferred_version=version,
            updated_at="2026-04-21T10:15:00+05:00",
            updated_by="admin1",
            message="Preferred-версия для network_ping обновлена на 1.2.1.",
            rollout_summary=AdminModulePreferredRolloutSummary(
                mode="installed_devices",
                should_sync=True,
                desired_updates=3,
                sync_enqueued=3,
                refresh_enqueued=3,
            ),
        )

    monkeypatch.setattr(admin_handlers, "_set_admin_module_preferred_version", fake_set_preferred)

    response = await web_admin_client.patch(
        "/api/web/admin/modules/network_ping/preferred",
        json={"version": "1.2.1"},
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["module_name"] == "network_ping"
    assert payload["data"]["preferred_version"] == "1.2.1"
    assert payload["data"]["updated_by"] == "admin1"
    assert payload["data"]["rollout_summary"]["desired_updates"] == 3
    assert payload["data"]["message"] == "Preferred-версия для network_ping обновлена на 1.2.1."


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_set_windows_module_preferred_requires_live_test(web_admin_client, monkeypatch):
    async def fake_set_preferred(*, request, auth_context, module_name: str, version: str | None):
        assert request.path == "/api/web/admin/modules/win_diag/preferred"
        assert auth_context.actor_role == "admin"
        assert module_name == "win_diag"
        assert version == "1.0.0"
        raise ValueError("MODULE_WINDOWS_LIVE_TEST_REQUIRED")

    monkeypatch.setattr(admin_handlers, "_set_admin_module_preferred_version", fake_set_preferred)

    response = await web_admin_client.patch(
        "/api/web/admin/modules/win_diag/preferred",
        json={"version": "1.0.0"},
    )

    assert response.status == 409
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "MODULE_WINDOWS_LIVE_TEST_REQUIRED"
    assert payload["module_name"] == "win_diag"
    assert payload["version"] == "1.0.0"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_updates_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_payload(*, device_id: str, state):
        assert device_id == "device-1"
        assert state is None
        return AdminDeviceUpdatesPayload(
            device_id=device_id,
            device_label="WS-01",
            online=True,
            target="windows_amd64",
            current_version="3.1.18",
            release_channel="stable",
            is_release=True,
            summary=AdminDeviceUpdateSummary(
                status="update_available",
                label="Доступно обновление",
                summary="Серверный rollout рекомендует stable/3.1.19.",
            ),
            recommendation=AdminDeviceUpdateRecommendation(
                update_available=True,
                recommendation_source="assigned_rollout",
                recommendation_source_label="Серверный rollout",
                comparison="newer_release_available",
                comparison_label="Назначена более новая release-версия",
                recommended_reason="assigned_rollout_newer",
                recommended_reason_label="Назначенный rollout новее текущей версии.",
                recommended_build=AdminBuildIdentity(
                    target="windows_amd64",
                    channel="stable",
                    version="3.1.19",
                ),
                assigned_rollout=AdminRolloutAssignment(
                    target="windows_amd64",
                    channel="stable",
                    version="3.1.19",
                    updated_at="2026-04-20T12:00:00+05:00",
                    updated_by="admin",
                ),
            ),
            action=AdminDeviceUpdateAction(
                enabled=True,
                label="Запустить обновление",
                reason_required=True,
                endpoint="/api/web/admin/devices/device-1/updates/run",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_device_updates_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/devices/device-1/updates")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "device-1"
    assert payload["data"]["recommendation"]["recommended_build"]["version"] == "3.1.19"
    assert payload["data"]["action"]["label"] == "Запустить обновление"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_update_run_requires_reason(web_admin_client):
    response = await web_admin_client.post("/api/web/admin/devices/device-1/updates/run", json={})

    assert response.status == 400
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_agent_builds_alias_uses_web_auth_boundary(web_admin_client, monkeypatch):
    async def fake_list_handler(request):
        assert request["auth_context"].actor_role == "admin"
        assert request.query.get("limit") == "10"
        return web.json_response({"status": "ok", "builds": [], "count": 0})

    monkeypatch.setattr(admin_handlers, "_handle_legacy_list_agent_builds", fake_list_handler)

    response = await web_admin_client.get("/api/web/admin/agent-builds?limit=10")

    assert response.status == 200
    payload = await response.json()
    assert payload == {"status": "ok", "builds": [], "count": 0}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_agent_rollout_policy_alias_uses_web_auth_boundary(web_admin_client, monkeypatch):
    async def fake_patch_handler(request):
        assert request["auth_context"].actor_role == "admin"
        data = await request.json()
        assert data["target"] == "windows_amd64"
        return web.json_response(
            {
                "status": "ok",
                "target": "windows_amd64",
                "assignment": {"target": "windows_amd64", "channel": "stable", "version": "3.1.33"},
            }
        )

    monkeypatch.setattr(admin_handlers, "_handle_legacy_patch_agent_rollout_policy", fake_patch_handler)

    response = await web_admin_client.patch(
        "/api/web/admin/agent-updates/rollout-policy",
        json={"target": "windows_amd64", "channel": "stable", "version": "3.1.33"},
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["assignment"]["version"] == "3.1.33"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_update_run_returns_queued_action_payload(web_admin_client, monkeypatch):
    async def fake_run_update(*, state, auth_context, device_id: str, reason: str, restart_delay_sec: int | None):
        assert state is None
        assert auth_context.actor_role == "admin"
        assert device_id == "device-1"
        assert reason == "canary после smoke"
        assert restart_delay_sec == 5
        return AdminDeviceUpdateRunPayload(
            device_id=device_id,
            operation_id="op-admin-1",
            status="queued",
            message="Операция op-admin-1 поставлена в очередь.",
            build_source="assigned_rollout",
            poll_url="/api/operations/op-admin-1",
            build=AdminBuildIdentity(
                target="windows_amd64",
                channel="stable",
                version="3.1.19",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_run_admin_device_update", fake_run_update)

    response = await web_admin_client.post(
        "/api/web/admin/devices/device-1/updates/run",
        json={"reason": "canary после smoke", "restart_delay_sec": 5},
    )

    assert response.status == 202
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["operation_id"] == "op-admin-1"
    assert payload["data"]["build"]["version"] == "3.1.19"


@pytest.mark.no_db
def test_web_admin_device_token_item_serializes_datetimes():
    created_at = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    last_used_at = datetime(2026, 4, 24, 12, 30, tzinfo=timezone.utc)

    item = admin_handlers._device_token_item(
        SimpleNamespace(
            token_hash="hash-1",
            token_prefix="pc1_",
            created_at=created_at,
            expires_at=None,
            revoked_at=None,
            last_used_at=last_used_at,
        )
    )

    assert item.created_at == created_at.isoformat()
    assert item.last_used_at == last_used_at.isoformat()
    assert item.is_active is True

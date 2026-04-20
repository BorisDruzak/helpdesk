import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

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
    assert payload["data"]["links"]["runtime_endpoint"] == "/api/admin/tech/traces/runtime"
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
                runtime_endpoint="/api/admin/tech/traces/runtime",
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
    ):
        assert request.path == "/api/web/admin/observer/traces"
        assert device_id == "device-1"
        assert lookback_hours == 72
        assert status_filter == "failed"
        assert root_kind_filter == "agent_update"
        assert limit == 25
        return AdminObserverTracesPayload(
            query=AdminObserverTracesQuery(
                device_id=device_id,
                lookback_hours=lookback_hours,
                status_filter=status_filter,
                root_kind_filter=root_kind_filter,
                limit=limit,
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
                runtime_endpoint="/api/admin/tech/traces/runtime",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_observer_traces_payload", fake_build_payload)

    response = await web_admin_client.get(
        "/api/web/admin/observer/traces?device_id=device-1&lookback_hours=72&status=failed&root_kind=agent_update&limit=25"
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["visible_count"] == 2
    assert payload["data"]["summary"]["selected_trace_id"] == "trace-1"
    assert payload["data"]["traces"][0]["operation_id"] == "op-1"
    assert payload["data"]["traces"][0]["attrs_json"]["flow"] == "agent_update"


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
    assert payload["data"]["rollout"] == []
    assert payload["data"]["devices"] == []
    assert payload["data"]["filters"]["status_options"][0] == {
        "value": "all",
        "label": "Все устройства",
    }


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

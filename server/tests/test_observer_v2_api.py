from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import AgentRuntimeAudit, Device, DeviceToolsetSnapshot, Operation, Ticket, TicketEvent
from app.repos.ticket_events_repo import TicketEventsRepo


ADMIN_TOKEN = "test-ui-admin-token"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ticket_root_trace_canonicalizes_lifecycle_events_and_groups_ticket_detail(test_client):
    now = datetime.now(timezone.utc)
    ticket_id = "00000000-0000-0000-0000-00000000c201"
    device_id = "00000000-0000-0000-0000-00000000c202"
    trace_id = "00000000-0000-0000-0000-00000000c203"
    operation_id_1 = "00000000-0000-0000-0000-00000000c204"
    operation_id_2 = "00000000-0000-0000-0000-00000000c205"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.16",
                hostname="observer-v2-root-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSROOT01",
                device_id=device_id,
                title="Observer root trace",
                description="Ticket lifecycle should stay inside one canonical trace",
                status="in_progress",
                created_at=now - timedelta(minutes=20),
                updated_at=now,
                observer_root_trace_id=trace_id,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=operation_id_1,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="system.collect",
                    actor_role="support",
                    trace_id=trace_id,
                    status="succeeded",
                    queued_at=now - timedelta(minutes=8),
                    sent_at=now - timedelta(minutes=8) + timedelta(seconds=1),
                    accepted_at=now - timedelta(minutes=8) + timedelta(seconds=2),
                    started_at=now - timedelta(minutes=8) + timedelta(seconds=3),
                    finished_at=now - timedelta(minutes=8) + timedelta(seconds=4),
                    retry_count=0,
                    result_summary="ok",
                ),
                Operation(
                    operation_id=operation_id_2,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=trace_id,
                    status="timed_out",
                    queued_at=now - timedelta(minutes=4),
                    sent_at=now - timedelta(minutes=4) + timedelta(seconds=1),
                    accepted_at=now - timedelta(minutes=4) + timedelta(seconds=2),
                    started_at=now - timedelta(minutes=4) + timedelta(seconds=3),
                    finished_at=now - timedelta(minutes=4) + timedelta(seconds=9),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="timeout while collecting screen snapshot",
                ),
            ]
        )
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"message_id": "msg-root-1", "text": "Первое сообщение"},
            trace_id="11111111-1111-1111-1111-111111111111",
            event_id="msg-root-1",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="status_changed",
            payload={"from_status": "new", "to_status": "in_progress"},
            trace_id="22222222-2222-2222-2222-222222222222",
            event_id="status-root-1",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"tool_name": "screen.collect", "call_id": "call-root-2"},
            trace_id="33333333-3333-3333-3333-333333333333",
            operation_id=operation_id_2,
        )
        await session.commit()

    async with get_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.observer_root_trace_id == trace_id
        rows = (
            await session.execute(
                sa.select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.id.asc())
            )
        ).scalars().all()
        assert rows
        assert {row.trace_id for row in rows} == {trace_id}

    search_resp = await test_client.get(
        f"/api/admin/tech/traces?ticket_id={ticket_id}",
        headers=_auth(),
    )
    assert search_resp.status == 200
    search_payload = await search_resp.json()
    assert search_payload["status"] == "ok"
    assert search_payload["count"] == 1
    assert search_payload["traces"][0]["trace_id"] == trace_id
    assert search_payload["traces"][0]["ticket_id"] == ticket_id
    assert search_payload["traces"][0]["attrs_json"]["ticket_code"] == "T-OBSROOT01"

    web_search_resp = await test_client.get(
        "/api/web/admin/observer/traces?root_kind=ticket&q=T-OBSROOT01&limit=5",
        headers=_auth(),
    )
    assert web_search_resp.status == 200
    web_search_payload = await web_search_resp.json()
    assert web_search_payload["status"] == "success"
    assert web_search_payload["data"]["summary"]["visible_count"] == 1
    web_trace = web_search_payload["data"]["traces"][0]
    assert web_trace["trace_id"] == trace_id
    assert web_trace["ticket_id"] == ticket_id
    assert web_trace["ticket_code"] == "T-OBSROOT01"
    assert web_trace["ticket_title"] == "Observer root trace"
    assert web_trace["device_hostname"] == "observer-v2-root-host"
    assert web_trace["display_title"] == "Тикет T-OBSROOT01"
    assert "Observer root trace" in web_trace["display_subtitle"]

    web_detail_resp = await test_client.get(
        f"/api/web/admin/observer/trace-detail/{trace_id}",
        headers=_auth(),
    )
    assert web_detail_resp.status == 200
    web_detail_payload = await web_detail_resp.json()
    assert web_detail_payload["status"] == "success"
    assert web_detail_payload["data"]["trace"]["ticket_code"] == "T-OBSROOT01"
    assert web_detail_payload["data"]["trace"]["display_title"] == "Тикет T-OBSROOT01"

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    span_names = {span["name"] for span in detail_payload["spans"]}
    assert "ticket.chat_message" in span_names
    assert "ticket.status_changed" in span_names
    assert {span["source_ref"] for span in detail_payload["spans"] if span["source_type"] == "operation"} == {
        operation_id_1,
        operation_id_2,
    }


@pytest.mark.asyncio
async def test_trace_detail_explains_manual_offline_agent_failure_and_stage_semantics(test_client):
    now = datetime.now(timezone.utc)
    ticket_id = "00000000-0000-0000-0000-00000000e201"
    device_id = "00000000-0000-0000-0000-00000000e202"
    trace_id = "00000000-0000-0000-0000-00000000e203"
    operation_id = "00000000-0000-0000-0000-00000000e204"

    async with get_session() as session:
        device = Device(
            device_id=device_id,
            protocol_version="ws_ticket_v3",
            agent_version="3.1.18",
            hostname="observer-offline-host",
            os="windows",
            capabilities=[],
            tools_version="observer-offline",
            device_metadata={},
            last_seen_at=now - timedelta(hours=2),
            last_handshake_at=now - timedelta(hours=2),
            first_seen_at=now - timedelta(days=1),
        )
        session.add(device)
        await session.flush()
        snapshot = DeviceToolsetSnapshot(
            device_id=device_id,
            agent_version="3.1.18",
            toolset_hash="observer-offline-tools",
            toolset_json={
                "tools": [
                    {
                        "tool": "system.collect",
                        "module": "system",
                        "label": "Сбор диагностики",
                        "description": "Сбор базовых параметров устройства",
                        "spec": {
                            "presets": [
                                {
                                    "id": "minimal",
                                    "name": "Minimal",
                                    "description": "CPU and memory only",
                                    "params": {"preset": "minimal"},
                                }
                            ]
                        },
                    }
                ]
            },
            tool_count=1,
        )
        session.add(snapshot)
        await session.flush()
        device.current_toolset_snapshot_id = snapshot.snapshot_id
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSFAIL01",
                device_id=device_id,
                title="Offline agent diagnostics",
                description="Observer should explain an offline agent failure",
                status="in_progress",
                created_at=now - timedelta(minutes=15),
                updated_at=now,
                observer_root_trace_id=trace_id,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="admin",
                trace_id=trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=5),
                finished_at=now - timedelta(minutes=5) + timedelta(milliseconds=7),
                retry_count=0,
                error_code="AGENT_NOT_CONNECTED",
                error_message="Agent is offline",
            )
        )
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={
                "tool_name": "system.collect",
                "call_id": "call-offline-1",
                "actor_id": "admin",
                "actor_role": "admin",
                "actor_display_name": "admin",
                "params": {"preset": "minimal"},
                "preset_id": "minimal",
            },
            trace_id=trace_id,
            operation_id=operation_id,
        )
        await session.commit()

    detail_resp = await test_client.get(
        f"/api/web/admin/observer/trace-detail/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "success"
    data = detail_payload["data"]

    explanation = data["explanation"]
    assert explanation["launch_source"] == "manual"
    assert explanation["launch_source_label"] == "Ручной запуск"
    assert explanation["actor_label"] == "Запустил: admin"
    assert explanation["actor_id"] == "admin"
    assert explanation["tool_label"] == "Сбор диагностики"
    assert explanation["preset_id"] == "minimal"
    assert explanation["preset_label"] == "Minimal"
    assert explanation["preset_description"] == "CPU and memory only"
    assert explanation["error_code"] == "AGENT_NOT_CONNECTED"
    assert explanation["error_diagnosis"] == "Агент на устройстве не подключен. Команда не была отправлена."
    assert "Проверить подключение агента" in explanation["next_actions"]
    assert explanation["launch_path"] == [
        "Тикет T-OBSFAIL01",
        "ручной запуск инструмента",
        "Сбор диагностики",
        "агент offline",
        "failed",
    ]

    queued_stage = next(span for span in data["spans"] if span["name"] == "operation.stage.queued")
    failed_stage = next(span for span in data["spans"] if span["name"] == "operation.stage.failed")
    assert queued_stage["status"] == "ok"
    assert queued_stage["stage_state"] == "passed_before_failure"
    assert queued_stage["is_failure_stage"] is False
    assert failed_stage["status"] == "error"
    assert failed_stage["stage_state"] == "failed"
    assert failed_stage["is_failure_stage"] is True


@pytest.mark.asyncio
async def test_observer_degradation_queries_report_slow_timeout_and_retry_rates(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000d201"
    ticket_id = "00000000-0000-0000-0000-00000000d202"
    trace_ids = [
        "00000000-0000-0000-0000-00000000d211",
        "00000000-0000-0000-0000-00000000d212",
        "00000000-0000-0000-0000-00000000d213",
    ]
    operation_ids = [
        "00000000-0000-0000-0000-00000000d221",
        "00000000-0000-0000-0000-00000000d222",
        "00000000-0000-0000-0000-00000000d223",
    ]

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.16",
                hostname="observer-v2-degradation-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSDEG01",
                device_id=device_id,
                title="Observer degradations",
                description="Slow and retry-heavy operations must be queryable",
                status="in_progress",
                created_at=now - timedelta(minutes=30),
                updated_at=now,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=operation_ids[0],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[0],
                    status="timed_out",
                    queued_at=now - timedelta(minutes=12),
                    started_at=now - timedelta(minutes=12) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=12) + timedelta(seconds=7),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="ping timeout",
                ),
                Operation(
                    operation_id=operation_ids[1],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[1],
                    status="failed",
                    queued_at=now - timedelta(minutes=9),
                    started_at=now - timedelta(minutes=9) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=9) + timedelta(seconds=4),
                    retry_count=1,
                    error_code="UNREACHABLE",
                    error_message="host unreachable",
                ),
                Operation(
                    operation_id=operation_ids[2],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[2],
                    status="succeeded",
                    queued_at=now - timedelta(minutes=6),
                    started_at=now - timedelta(minutes=6) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=6) + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="ok",
                ),
            ]
        )
        await session.commit()

    slow_search = await test_client.get(
        "/api/admin/tech/traces?tool_name=network_ping.ping&min_duration_ms=5000",
        headers=_auth(),
    )
    assert slow_search.status == 200
    slow_payload = await slow_search.json()
    assert slow_payload["status"] == "ok"
    assert {item["trace_id"] for item in slow_payload["traces"]} == {trace_ids[0]}

    retry_search = await test_client.get(
        "/api/admin/tech/traces?tool_name=network_ping.ping&min_retry_count=2",
        headers=_auth(),
    )
    assert retry_search.status == 200
    retry_payload = await retry_search.json()
    assert retry_payload["status"] == "ok"
    assert {item["trace_id"] for item in retry_payload["traces"]} == {trace_ids[0]}

    degradation_resp = await test_client.get(
        "/api/admin/tech/degradations?tool_name=network_ping.ping&lookback_hours=24&min_duration_ms=2500",
        headers=_auth(),
    )
    assert degradation_resp.status == 200
    degradation_payload = await degradation_resp.json()
    assert degradation_payload["status"] == "ok"
    assert degradation_payload["count"] == 1
    item = degradation_payload["items"][0]
    assert item["tool_name"] == "network_ping.ping"
    assert item["operations_count"] == 3
    assert item["timeout_count"] == 1
    assert item["retried_operations_count"] == 2
    assert item["slow_operations_count"] == 2
    assert item["timeout_rate"] == pytest.approx(1 / 3, rel=1e-4)
    assert item["retry_rate"] == pytest.approx(2 / 3, rel=1e-4)
    assert item["slow_rate"] == pytest.approx(2 / 3, rel=1e-4)


@pytest.mark.asyncio
async def test_observer_can_filter_agent_update_traces_and_rate_threshold_degradations(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000e201"
    ticket_id = "00000000-0000-0000-0000-00000000e202"
    update_trace_ids = [
        "00000000-0000-0000-0000-00000000e211",
        "00000000-0000-0000-0000-00000000e212",
    ]
    update_operation_ids = [
        "00000000-0000-0000-0000-00000000e221",
        "00000000-0000-0000-0000-00000000e222",
    ]
    tool_trace_id = "00000000-0000-0000-0000-00000000e213"
    tool_operation_id = "00000000-0000-0000-0000-00000000e223"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.17",
                hostname="observer-v2-update-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSUPD01",
                device_id=device_id,
                title="Observer update traces",
                description="agent_update should be queryable as a dangerous flow",
                status="in_progress",
                created_at=now - timedelta(minutes=30),
                updated_at=now,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=update_operation_ids[0],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="agent_update",
                    tool_name="update",
                    actor_role="admin",
                    trace_id=update_trace_ids[0],
                    status="timed_out",
                    queued_at=now - timedelta(minutes=12),
                    started_at=now - timedelta(minutes=12) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=12) + timedelta(seconds=8),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="launcher update timeout",
                ),
                Operation(
                    operation_id=update_operation_ids[1],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="agent_update",
                    tool_name="update",
                    actor_role="admin",
                    trace_id=update_trace_ids[1],
                    status="succeeded",
                    queued_at=now - timedelta(minutes=8),
                    started_at=now - timedelta(minutes=8) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=8) + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="confirmed_by_handshake:3.1.18",
                ),
                Operation(
                    operation_id=tool_operation_id,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=tool_trace_id,
                    status="failed",
                    queued_at=now - timedelta(minutes=6),
                    started_at=now - timedelta(minutes=6) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=6) + timedelta(seconds=2),
                    retry_count=0,
                    error_code="TOOL_FAILED",
                    error_message="screen collect failed",
                ),
            ]
        )
        await session.commit()

    trace_search = await test_client.get(
        "/api/admin/tech/traces?root_kind=agent_update",
        headers=_auth(),
    )
    assert trace_search.status == 200
    trace_payload = await trace_search.json()
    assert trace_payload["status"] == "ok"
    assert {item["trace_id"] for item in trace_payload["traces"]} == set(update_trace_ids)

    degradation_resp = await test_client.get(
        (
            "/api/admin/tech/degradations"
            "?root_kind=agent_update"
            "&lookback_hours=24"
            "&min_duration_ms=2000"
            "&min_timeout_rate=0.5"
            "&min_retry_rate=0.5"
            "&min_slow_rate=0.5"
        ),
        headers=_auth(),
    )
    assert degradation_resp.status == 200
    degradation_payload = await degradation_resp.json()
    assert degradation_payload["status"] == "ok"
    assert degradation_payload["count"] == 1
    item = degradation_payload["items"][0]
    assert item["tool_name"] == "update"
    assert item["operation_kind"] == "agent_update"
    assert item["operations_count"] == 2
    assert item["timeout_rate"] == pytest.approx(0.5, rel=1e-4)
    assert item["retry_rate"] == pytest.approx(0.5, rel=1e-4)
    assert item["slow_rate"] == pytest.approx(0.5, rel=1e-4)


@pytest.mark.asyncio
async def test_trace_detail_syncs_agent_actions_into_observer_spans(monkeypatch: pytest.MonkeyPatch, test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000e301"
    ticket_id = "00000000-0000-0000-0000-00000000e302"
    trace_id = "00000000-0000-0000-0000-00000000e303"
    operation_id = "00000000-0000-0000-0000-00000000e304"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.18",
                hostname="observer-agent-actions-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSACT01",
                device_id=device_id,
                title="Observer agent actions",
                description="Agent action trace should become persisted spans",
                status="in_progress",
                created_at=now - timedelta(minutes=8),
                updated_at=now,
                observer_root_trace_id=trace_id,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="support",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now - timedelta(minutes=5),
                started_at=now - timedelta(minutes=5) + timedelta(seconds=1),
                finished_at=now - timedelta(minutes=5) + timedelta(seconds=2),
                result_summary="ok",
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                operation_id=operation_id,
                ticket_id=ticket_id,
                event_type="tool_completed",
                severity="info",
                source="agent",
                details_json={"tool_name": "system.collect"},
                created_at=now - timedelta(minutes=5) + timedelta(seconds=2),
            )
        )
        await session.commit()

    async def _fake_send_ws_rpc_request(**_: object) -> dict[str, object]:
        return {
            "payload": {
                "data": {
                    "observations": {
                        "entries": [
                            {
                                "ts": (now - timedelta(seconds=5)).isoformat(),
                                "source": "module",
                                "action": "module.execute",
                                "category": "tool",
                                "action_id": "action-root-1",
                                "parent_action_id": None,
                                "ticket_id": ticket_id,
                                "operation_id": operation_id,
                                "tool_name": "system.collect",
                                "trace_id": trace_id,
                                "request_id": operation_id,
                                "stage": "finish",
                                "status": "ok",
                                "summary": "done",
                                "details": {
                                    "module_name": "system",
                                    "method_name": "collect",
                                    "access_token": "super-secret",
                                },
                            },
                            {
                                "ts": (now - timedelta(seconds=4)).isoformat(),
                                "source": "module",
                                "action": "module.step",
                                "category": "tool",
                                "action_id": "action-step-1",
                                "parent_action_id": "action-root-1",
                                "ticket_id": ticket_id,
                                "operation_id": operation_id,
                                "tool_name": "system.collect",
                                "trace_id": trace_id,
                                "request_id": operation_id,
                                "stage": "finish",
                                "status": "ok",
                                "summary": "cpu collected",
                                "details": {
                                    "step": "collect.cpu",
                                    "module_name": "system",
                                },
                            },
                        ]
                    }
                }
            }
        }

    monkeypatch.setattr("tech.handlers.send_ws_rpc_request", _fake_send_ws_rpc_request)

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}?include_agent_actions=1&sync_agent_actions=1",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    assert len(detail_payload["agent_actions"]) == 2
    assert detail_payload["agent_actions"][0]["details"]["access_token"] == "***REDACTED***"
    assert any(
        span["source_type"] == "agent_action"
        and span["source_ref"] == "action-root-1"
        and span["name"] == "module.execute"
        for span in detail_payload["spans"]
    )
    assert any(
        link["reason"] == "agent_action_parent"
        for link in detail_payload["span_links"]
    )


@pytest.mark.asyncio
async def test_trace_detail_redacts_runtime_audit_attrs_in_occurrences(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000e401"
    trace_id = "00000000-0000-0000-0000-00000000e402"
    operation_id = "00000000-0000-0000-0000-00000000e403"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.18",
                hostname="observer-redaction-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="tool_call",
                tool_name="diag.logs.collect",
                actor_role="support",
                trace_id=trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=2),
                started_at=now - timedelta(minutes=2) + timedelta(seconds=1),
                finished_at=now - timedelta(minutes=2) + timedelta(seconds=2),
                error_code="TOOL_EXEC_FAILED",
                error_message="failed to collect logs",
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                operation_id=operation_id,
                event_type="tool_failed",
                severity="error",
                source="agent",
                details_json={
                    "tool_name": "diag.logs.collect",
                    "message": "boom",
                    "authorization": "Bearer secret-token",
                    "nested": {"password": "pw"},
                    "token_hash_prefix": "safe-prefix",
                },
                created_at=now - timedelta(minutes=2) + timedelta(seconds=2),
            )
        )
        await session.commit()

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    payload = await detail_resp.json()
    assert payload["status"] == "ok"
    runtime_spans = [span for span in payload["spans"] if span["source_type"] == "agent_runtime_audit"]
    assert runtime_spans
    span_details = runtime_spans[0]["attrs_json"]["details_json"]
    assert span_details["authorization"] == "***REDACTED***"
    assert span_details["nested"]["password"] == "***REDACTED***"
    assert span_details["token_hash_prefix"] == "safe-prefix"


@pytest.mark.asyncio
async def test_trace_search_by_operation_id_sees_just_projected_execution_trace(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000e501"
    trace_id = "00000000-0000-0000-0000-00000000e502"
    operation_id = "00000000-0000-0000-0000-00000000e503"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.19",
                hostname="observer-op-search-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_install",
                actor_role="admin",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now - timedelta(seconds=20),
                sent_at=now - timedelta(seconds=18),
                accepted_at=now - timedelta(seconds=16),
                finished_at=now - timedelta(seconds=10),
                retry_count=0,
                result_summary="installed observer canary module",
            )
        )
        await session.commit()

    response = await test_client.get(
        f"/api/admin/tech/traces?operation_id={operation_id}",
        headers=_auth(),
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["traces"][0]["trace_id"] == trace_id
    assert payload["traces"][0]["operation_id"] == operation_id

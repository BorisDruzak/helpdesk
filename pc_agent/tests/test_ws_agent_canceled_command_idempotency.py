import asyncio
import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.database import DatabaseManager
from pc_agent.ws_agent import WSAgent


@pytest.mark.asyncio
async def test_canceled_background_command_is_terminal_and_reported(tmp_path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    command_id = "00000000-0000-0000-0000-00000000c001"
    sent = []

    async def fake_execute_command(*_args, **_kwargs):
        raise asyncio.CancelledError()

    async def fake_send_envelope(
        _ws,
        msg_type,
        request_id,
        payload,
        *,
        trace_id=None,
        ticket_id=None,
        job_id=None,
        actor_role=None,
    ):
        sent.append(
            {
                "msg_type": msg_type,
                "request_id": request_id,
                "payload": payload,
                "trace_id": trace_id,
                "ticket_id": ticket_id,
                "job_id": job_id,
                "actor_role": actor_role,
            }
        )

    agent.execute_command = fake_execute_command
    agent.send_envelope = fake_send_envelope
    await db.mark_command_started(command_id, owner_instance_id="test-session")

    await agent._execute_command_and_send_result(
        None,
        command="run_tool",
        params={"tool": "screen.record", "params": {}},
        request_id=command_id,
        command_id=command_id,
        device_id="device-1",
        actor_role="support",
        trace_id="trace-cancel",
        ticket_id_ctx="ticket-1",
        job_id_ctx=None,
        actor_role_meta="agent",
    )

    cached = await db.get_command_result(command_id)
    assert cached is not None
    assert cached["status"] == "canceled"
    cached_payload = json.loads(cached["result_json"])
    assert cached_payload["status"] == "canceled"
    assert cached_payload["error"]["code"] == "OPERATION_CANCELED"

    assert sent == [
        {
            "msg_type": "command_result",
            "request_id": command_id,
            "payload": cached_payload,
            "trace_id": "trace-cancel",
            "ticket_id": "ticket-1",
            "job_id": None,
            "actor_role": "agent",
        }
    ]


@pytest.mark.asyncio
async def test_duplicate_canceled_command_returns_cached_terminal_result(tmp_path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    agent.device_id = "device-1"
    command_id = "00000000-0000-0000-0000-00000000c002"
    cached_payload = {
        "status": "canceled",
        "data": {"observations": {"cancel_status": "canceled"}},
        "error": {"code": "OPERATION_CANCELED", "message": "Command was canceled"},
        "meta": {"request_id": command_id},
    }
    await db.mark_command_seen(
        command_id=command_id,
        status="canceled",
        result_json=json.dumps(cached_payload),
    )
    sent = []

    async def should_not_execute(*_args, **_kwargs):
        raise AssertionError("duplicate canceled command must not re-execute")

    async def fake_send_envelope(
        _ws,
        msg_type,
        request_id,
        payload,
        *,
        trace_id=None,
        ticket_id=None,
        job_id=None,
        actor_role=None,
    ):
        sent.append(
            {
                "msg_type": msg_type,
                "request_id": request_id,
                "payload": payload,
                "trace_id": trace_id,
                "ticket_id": ticket_id,
                "job_id": job_id,
                "actor_role": actor_role,
            }
        )

    agent.execute_command = should_not_execute
    agent.send_envelope = fake_send_envelope

    await agent.handle_message(
        None,
        json.dumps(
            {
                "type": "command",
                "protocol_version": "ws_ticket_v3",
                "request_id": command_id,
                "device_id": "device-1",
                "trace_id": "trace-cached-cancel",
                "ticket_id": "ticket-1",
                "payload": {
                    "command": "run_tool",
                    "params": {"tool": "screen.record", "params": {}},
                    "actor_role": "support",
                },
                "meta": {"actor_role": "support"},
            }
        ),
    )

    assert len(sent) == 1
    assert sent[0]["msg_type"] == "command_result"
    assert sent[0]["request_id"] == command_id
    assert sent[0]["payload"]["status"] == "canceled"
    assert sent[0]["payload"]["meta"]["cached"] is True

import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.database import DatabaseManager
from pc_agent.ws_agent import WSAgent


@pytest.mark.asyncio
async def test_recover_stale_in_progress_commands_marks_terminal_and_pending(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    stale_command = "00000000-0000-0000-0000-00000000d001"
    current_command = "00000000-0000-0000-0000-00000000d002"
    await db.mark_command_started(stale_command, owner_instance_id="old-runtime")
    await db.mark_command_started(current_command, owner_instance_id="current-runtime")

    recovered = await db.recover_in_progress_commands_on_startup(
        current_owner_instance_id="current-runtime",
        reason_code="AGENT_RESTARTED",
    )

    assert [item["command_id"] for item in recovered] == [stale_command]

    stale_state = await db.get_command_result(stale_command)
    assert stale_state is not None
    assert stale_state["status"] == "error"
    stale_payload = json.loads(stale_state["result_json"])
    assert stale_payload["status"] == "error"
    assert stale_payload["error"]["code"] == "AGENT_RESTARTED"
    assert stale_payload["meta"]["recovery"] is True
    assert stale_payload["meta"]["previous_owner_instance_id"] == "old-runtime"

    current_state = await db.get_command_result(current_command)
    assert current_state is not None
    assert current_state["status"] == "in_progress"

    pending = await db.list_pending_command_results()
    assert len(pending) == 1
    assert pending[0]["command_id"] == stale_command
    assert json.loads(pending[0]["payload_json"])["error"]["code"] == "AGENT_RESTARTED"


@pytest.mark.asyncio
async def test_ws_agent_replays_startup_recovery_command_result(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-00000000d003"
    await db.mark_command_started(command_id, owner_instance_id="old-runtime")

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    agent._session_id = "new-runtime"

    sent = []

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

    agent.send_envelope = fake_send_envelope

    await agent.recover_in_progress_commands_on_startup(None)

    assert sent == [
        {
            "msg_type": "command_result",
            "request_id": command_id,
            "payload": {
                "status": "error",
                "data": {
                    "observations": {
                        "interrupted": True,
                        "reason": "AGENT_RESTARTED",
                        "target_operation_id": command_id,
                    }
                },
                "error": {
                    "code": "AGENT_RESTARTED",
                    "message": "Command was interrupted because the agent process restarted",
                    "retryable": True,
                },
                "meta": {
                    "request_id": command_id,
                    "command_id": command_id,
                    "recovery": True,
                    "previous_owner_instance_id": "old-runtime",
                    "current_owner_instance_id": "new-runtime",
                },
            },
            "trace_id": None,
            "ticket_id": None,
            "job_id": None,
            "actor_role": "agent",
        }
    ]

    cached = await db.get_command_result(command_id)
    assert cached is not None
    assert cached["status"] == "error"


@pytest.mark.asyncio
async def test_previous_runtime_in_progress_command_recovers_without_ack_or_rerun(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-00000000d006"
    await db.mark_command_started(command_id, owner_instance_id="old-runtime")

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    agent.device_id = "device-1"
    agent._session_id = "new-runtime"

    async def should_not_execute(*_args, **_kwargs):
        raise AssertionError("previous-runtime in_progress command must not execute again")

    sent = []

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
                "trace_id": "trace-previous-runtime",
                "ticket_id": "ticket-1",
                "payload": {
                    "command": "run_tool",
                    "params": {"tool": "screen.record", "params": {}},
                },
                "meta": {"actor_role": "support"},
            }
        ),
    )

    assert [item["msg_type"] for item in sent] == ["command_result"]
    assert sent[0]["request_id"] == command_id
    assert sent[0]["payload"]["status"] == "error"
    assert sent[0]["payload"]["error"]["code"] == "AGENT_RESTARTED"
    assert sent[0]["payload"]["meta"]["recovery"] is True
    assert sent[0]["payload"]["meta"]["previous_owner_instance_id"] == "old-runtime"
    assert sent[0]["trace_id"] == "trace-previous-runtime"
    assert sent[0]["ticket_id"] == "ticket-1"
    assert sent[0]["actor_role"] == "support"

    cached = await db.get_command_result(command_id)
    assert cached is not None
    assert cached["status"] == "error"

    pending = await db.list_pending_command_results()
    assert [item["command_id"] for item in pending] == [command_id]
    assert json.loads(pending[0]["payload_json"])["error"]["code"] == "AGENT_RESTARTED"


@pytest.mark.asyncio
async def test_command_result_ack_clears_pending_result(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-00000000d004"
    payload = {"status": "success", "data": {}, "error": {}, "meta": {"request_id": command_id}}
    await db.enqueue_pending_command_result(command_id=command_id, payload=payload)

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    agent.device_id = "device-1"

    await agent.handle_message(
        None,
        json.dumps(
            {
                "type": "command_result_ack",
                "request_id": command_id,
                "device_id": "device-1",
                "payload": {"status": "accepted"},
            }
        ),
    )

    assert await db.list_pending_command_results() == []


@pytest.mark.asyncio
async def test_duplicate_after_restart_recovery_returns_cached_error(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-00000000d005"
    recovery_payload = {
        "status": "error",
        "data": {
            "observations": {
                "interrupted": True,
                "reason": "AGENT_RESTARTED",
                "target_operation_id": command_id,
            }
        },
        "error": {
            "code": "AGENT_RESTARTED",
            "message": "Command was interrupted because the agent process restarted",
            "retryable": True,
        },
        "meta": {
            "request_id": command_id,
            "command_id": command_id,
            "recovery": True,
        },
    }
    await db.mark_command_seen(
        command_id=command_id,
        status="error",
        result_json=json.dumps(recovery_payload),
    )

    agent = WSAgent(data_root=tmp_path)
    agent.db_manager = db
    agent.device_id = "device-1"

    async def fail_execute_command(*_args, **_kwargs):
        raise AssertionError("Recovered command must not execute again")

    sent = []

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

    agent.execute_command = fail_execute_command
    agent.send_envelope = fake_send_envelope

    await agent.handle_message(
        None,
        json.dumps(
            {
                "type": "command",
                "request_id": command_id,
                "device_id": "device-1",
                "trace_id": "trace-recovery-duplicate",
                "ticket_id": "ticket-1",
                "payload": {
                    "command": "run_tool",
                    "params": {},
                },
                "meta": {"actor_role": "agent"},
            }
        ),
    )

    assert len(sent) == 1
    assert sent[0]["msg_type"] == "command_result"
    assert sent[0]["request_id"] == command_id
    assert sent[0]["payload"]["status"] == "error"
    assert sent[0]["payload"]["error"]["code"] == "AGENT_RESTARTED"
    assert sent[0]["payload"]["meta"]["cached"] is True
    assert sent[0]["trace_id"] == "trace-recovery-duplicate"
    assert sent[0]["ticket_id"] == "ticket-1"

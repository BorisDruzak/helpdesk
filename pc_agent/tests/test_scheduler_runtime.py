import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.core.database import DatabaseManager
from pc_agent.ws_agent import WSAgent


@pytest.mark.asyncio
async def test_scheduled_tasks_crud_and_validation(tmp_path):
    db_path = tmp_path / "storage.db"
    db = DatabaseManager(str(db_path))
    await db.init_db()

    task_id = str(uuid.uuid4())
    await db.create_scheduled_task(
        task_id=task_id,
        kind="run_tool",
        schedule="minutely",
        params={"tool_name": "diag.hello", "params": {"x": 1}},
        enabled=True,
    )

    listed = await db.list_scheduled_tasks()
    assert len(listed) == 1
    assert listed[0]["task_id"] == task_id
    assert listed[0]["enabled"] == 1

    run_now_ok = await db.request_scheduled_task_run_now(task_id)
    assert run_now_ok is True

    cancel_ok = await db.disable_scheduled_task(task_id)
    assert cancel_ok is True
    task = await db.get_scheduled_task(task_id)
    assert task is not None
    assert task["enabled"] == 0

    with pytest.raises(ValueError, match="Unsupported schedule"):
        await db.create_scheduled_task(
            task_id=str(uuid.uuid4()),
            kind="run_tool",
            schedule="cron",
            params={"tool_name": "diag.hello"},
            enabled=True,
        )

    await db.close()


@pytest.mark.asyncio
async def test_scheduler_executes_due_task_via_run_tool_path(tmp_path):
    db_path = tmp_path / "storage.db"
    db = DatabaseManager(str(db_path))
    await db.init_db()

    task_id = str(uuid.uuid4())
    await db.create_scheduled_task(
        task_id=task_id,
        kind="run_tool",
        schedule="minutely",
        params={
            "tool_name": "diag.hello",
            "params": {"message": "from scheduler"},
            "ticket_id": "t-scheduler-1",
        },
        enabled=True,
    )
    await db.request_scheduled_task_run_now(task_id)

    due = await db.get_due_scheduled_tasks(now=time.time())
    assert due, "Expected at least one due task after run_now"

    agent = WSAgent(data_root=tmp_path, install_root=tmp_path / "install")
    agent.db_manager = db
    agent.device_id = "device-test-1"

    captured = {}

    async def _fake_execute_command(command, params, request_id=None, device_id=None, actor_role=None):
        captured["command"] = command
        captured["params"] = params
        captured["request_id"] = request_id
        captured["device_id"] = device_id
        captured["actor_role"] = actor_role
        return {"status": "success", "data": {"observations": {}}}

    agent.execute_command = _fake_execute_command  # type: ignore[assignment]

    await agent._execute_scheduled_task(due[0])
    await db.update_scheduled_task_after_run(task_id)

    assert captured["command"] == "run_tool"
    assert captured["params"]["tool_name"] == "diag.hello"
    assert captured["params"]["params"] == {"message": "from scheduler"}
    assert captured["params"]["ticket_id"] == "t-scheduler-1"
    assert captured["device_id"] == "device-test-1"
    assert captured["actor_role"] == "agent"
    assert str(captured["request_id"]).startswith(f"scheduler-{task_id}-")

    task = await db.get_scheduled_task(task_id)
    assert task is not None
    assert task["last_run_at"] is not None
    assert task["next_run_at"] > task["last_run_at"]

    await db.close()

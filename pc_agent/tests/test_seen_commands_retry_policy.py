from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DatabaseManager


@pytest.mark.asyncio
async def test_mark_command_started_tracks_owner_and_stale_retry_count(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-000000000001"

    await db.mark_command_started(command_id, owner_instance_id="agent-A")
    first = await db.get_command_result(command_id)
    assert first is not None
    assert first["status"] == "in_progress"
    assert first["stale_retry_count"] == 0
    assert first["owner_instance_id"] == "agent-A"

    await db.mark_command_started(
        command_id,
        owner_instance_id="agent-B",
        stale_retry=True,
    )
    second = await db.get_command_result(command_id)
    assert second is not None
    assert second["status"] == "in_progress"
    assert second["stale_retry_count"] == 1
    assert second["owner_instance_id"] == "agent-B"
    assert second["started_at"] >= first["started_at"]


@pytest.mark.asyncio
async def test_mark_command_seen_resets_controlled_retry_metadata(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_path))
    await db.init_db()

    command_id = "00000000-0000-0000-0000-000000000002"
    await db.mark_command_started(command_id, owner_instance_id="agent-A", stale_retry=True)
    await db.mark_command_seen(
        command_id=command_id,
        status="success",
        result_json='{"status":"success"}',
    )
    final_state = await db.get_command_result(command_id)
    assert final_state is not None
    assert final_state["status"] == "success"
    assert final_state["stale_retry_count"] == 0
    assert final_state["owner_instance_id"] is None

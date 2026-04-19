from __future__ import annotations

import time
from pathlib import Path

import pytest

from pc_agent.core.database import DatabaseManager
from pc_agent.core.job_manager import JobManager
from loguru import logger


@pytest.fixture
async def db(tmp_path: Path):
    test_db_path = tmp_path / "test_storage.db"
    database = DatabaseManager(str(test_db_path))
    await database.init_db()
    try:
        yield database
    finally:
        await database.close()
        DatabaseManager._instance = None
        for _ in range(5):
            if not test_db_path.exists():
                break
            try:
                test_db_path.unlink()
                break
            except PermissionError:
                time.sleep(0.05)


@pytest.fixture
async def job_manager(db: DatabaseManager):
    manager = JobManager(
        db_manager=db,
        outbox_enqueue_func=db.enqueue_job_event,
        logger_instance=logger,
    )
    try:
        yield manager
    finally:
        for job_id in list(manager.tasks.keys()):
            try:
                await manager.stop_job(job_id)
            except Exception:
                pass

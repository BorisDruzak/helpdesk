from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import Playbook, PlaybookRun, PlaybookStep, PlaybookStepRun, PlaybookVersion
from observer.service import ObserverOverlayService, TraceOverlayFilters


@pytest.mark.asyncio
async def test_playbook_run_projects_local_steps_and_failed_preflight_signature() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000fb01"

    async with get_session() as session:
        playbook = Playbook(key="observer_playbook_projection", name="Observer projection", domain="diagnostics")
        session.add(playbook)
        await session.flush()
        version = PlaybookVersion(playbook_id=playbook.id, version="1.0.0", status="published")
        session.add(version)
        await session.flush()
        skipped_step = PlaybookStep(
            playbook_version_id=version.id,
            step_key="branch",
            order_no=1,
            type="decision",
        )
        failed_step = PlaybookStep(
            playbook_version_id=version.id,
            step_key="install_missing_module",
            order_no=2,
            type="run_tool",
            tool="missing.module_tool",
        )
        session.add_all([skipped_step, failed_step])
        await session.flush()
        run = PlaybookRun(
            playbook_version_id=version.id,
            device_id=device_id,
            status="failed",
            scheduled_at=now - timedelta(seconds=4),
            started_at=now - timedelta(seconds=4),
            finished_at=now,
            trigger_type="test",
            context_json={"ticket": "T-PLAYBOOK"},
            error_code="STEP_FAILED",
            error_message="Step install_missing_module failed",
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                PlaybookStepRun(
                    playbook_run_id=run.id,
                    playbook_step_id=skipped_step.id,
                    attempt=1,
                    status="skipped",
                    started_at=now - timedelta(seconds=3),
                    finished_at=now - timedelta(seconds=3),
                    input_json={"reason": "if_expr=false"},
                ),
                PlaybookStepRun(
                    playbook_run_id=run.id,
                    playbook_step_id=failed_step.id,
                    attempt=1,
                    status="failed",
                    started_at=now - timedelta(seconds=2),
                    finished_at=now - timedelta(seconds=1),
                    input_json={"target": "device"},
                    error_json={
                        "code": "MODULE_PRECHECK_FAILED",
                        "message": "module package unavailable",
                        "stage": "module_install",
                    },
                ),
            ]
        )
        await session.commit()
        playbook_run_id = run.id

    async with get_session() as session:
        service = ObserverOverlayService(session)
        candidates = await service._candidate_trace_ids(
            TraceOverlayFilters(root_kind="playbook_run", playbook_run_id=playbook_run_id),
            limit=5,
        )
        assert candidates
        trace = await service.project_trace(candidates[0], force=True)
        await session.commit()

    assert trace is not None
    assert trace.root_kind == "playbook_run"
    assert trace.device_id == device_id
    assert trace.status == "error"

    async with get_session() as session:
        spans = (
            await session.execute(
                sa.text(
                    "SELECT source_type, name, status, attrs_json "
                    "FROM observer_spans WHERE trace_id = :trace_id ORDER BY started_at"
                ),
                {"trace_id": trace.trace_id},
            )
        ).mappings().all()
        assert any(row["source_type"] == "playbook_run" for row in spans)
        assert any(row["source_type"] == "playbook_step_run" and row["name"] == "playbook.step.branch" and row["status"] == "skipped" for row in spans)
        assert any(row["source_type"] == "playbook_step_run" and row["name"] == "playbook.step.install_missing_module" and row["status"] == "error" for row in spans)

        occurrences = (
            await session.execute(
                sa.text(
                    "SELECT component, error_kind, failure_stage, severity "
                    "FROM observer_error_occurrences WHERE trace_id = :trace_id"
                ),
                {"trace_id": trace.trace_id},
            )
        ).mappings().all()
        assert any(row["component"] == "playbook" and row["error_kind"] == "MODULE_PRECHECK_FAILED" for row in occurrences)
        assert any(row["failure_stage"] == "module_install" and row["severity"] == "error" for row in occurrences)


@pytest.mark.asyncio
async def test_playbook_run_filter_searches_projected_trace() -> None:
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        playbook = Playbook(key="observer_playbook_filter", name="Observer filter")
        session.add(playbook)
        await session.flush()
        version = PlaybookVersion(playbook_id=playbook.id, version="1.0.0", status="published")
        session.add(version)
        await session.flush()
        run = PlaybookRun(
            playbook_version_id=version.id,
            device_id="00000000-0000-0000-0000-00000000fb02",
            status="success",
            scheduled_at=now,
            started_at=now,
            finished_at=now,
            trigger_type="test",
        )
        session.add(run)
        await session.commit()
        playbook_run_id = run.id

    async with get_session() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(root_kind="playbook_run", playbook_run_id=playbook_run_id),
            limit=10,
        )

    assert len(traces) == 1
    assert traces[0]["attrs_json"]["playbook_run_id"] == playbook_run_id

import asyncio

import pytest

from app.services.problem_candidate_scheduler import ProblemCandidateScheduler

pytestmark = pytest.mark.no_db


async def checkpoint():
    event = asyncio.Event()
    asyncio.get_running_loop().call_soon(event.set)
    await event.wait()


@pytest.mark.asyncio
async def test_stop_without_task_is_noop():
    scheduler = ProblemCandidateScheduler(session_maker=object(), enabled=False)
    await scheduler.stop()
    await scheduler.stop()
    assert not scheduler.is_running


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_cancellations", [0, 1, 2])
async def test_stop_preserves_cancellation_and_finishes_cleanup(parent_cancellations):
    scheduler = ProblemCandidateScheduler(session_maker=object(), enabled=False)
    started, cleanup_started, release, cleaned = (asyncio.Event() for _ in range(4))

    async def child():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup_started.set()
            await release.wait()
            cleaned.set()

    task = asyncio.create_task(child())
    scheduler._task = task
    await started.wait()
    stopper = asyncio.create_task(scheduler.stop())
    try:
        await asyncio.wait_for(cleanup_started.wait(), 2)
        for _ in range(parent_cancellations):
            stopper.cancel()
            await checkpoint()
        release.set()
        if parent_cancellations:
            with pytest.raises(asyncio.CancelledError):
                await stopper
        else:
            await stopper
        assert cleaned.is_set()
        assert task.done()
        assert scheduler._task is None
        await scheduler.stop()
    finally:
        release.set()
        await asyncio.gather(stopper, task, return_exceptions=True)


@pytest.mark.asyncio
async def test_parent_cancellation_survives_child_cleanup_failure():
    scheduler = ProblemCandidateScheduler(session_maker=object(), enabled=False)
    started, cleanup, release = (asyncio.Event() for _ in range(3))

    async def child():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
            raise RuntimeError("cleanup failed")

    task = asyncio.create_task(child())
    scheduler._task = task
    await started.wait()
    stopper = asyncio.create_task(scheduler.stop())
    try:
        await cleanup.wait()
        stopper.cancel()
        await checkpoint()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await stopper
        assert task.done()
        assert scheduler._task is None
    finally:
        release.set()
        await asyncio.gather(stopper, task, return_exceptions=True)

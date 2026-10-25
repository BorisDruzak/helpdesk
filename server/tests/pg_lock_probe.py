"""Observe real PostgreSQL lock contention from an independent connection."""
import asyncio

from sqlalchemy import text


async def wait_for_backend_blocker(engine, *, blocked_pid: int, blocker_pid: int, task, timeout: float = 5) -> None:
    """Require PostgreSQL to report the expected blocker before releasing it."""
    try:
        async with asyncio.timeout(timeout):
            async with engine.connect() as observer:
                while True:
                    blockers = (await observer.execute(
                        text("SELECT pg_blocking_pids(:blocked_pid)"), {"blocked_pid": blocked_pid}
                    )).scalar_one()
                    if blocker_pid in blockers:
                        return
                    if task.done():
                        raise AssertionError("Competing operation completed without the required PostgreSQL lock wait")
                    # Polling cadence only; elapsed time never proves contention.
                    await asyncio.sleep(.01)
    except TimeoutError as exc:
        raise AssertionError(f"Backend {blocked_pid} never waited on backend {blocker_pid}") from exc

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db.models import EndpointOperationLink, Operation


pytestmark = pytest.mark.db_cleanup("full")


def _operation() -> Operation:
    return Operation(
        operation_id=str(uuid.uuid4()),
        device_id="legacy-device-1",
        ticket_id=None,
        kind="endpoint_diagnostic",
        actor_role="system",
        trace_id=str(uuid.uuid4()),
        status="queued",
        queued_at=datetime.now(timezone.utc),
    )


class _NoDatabaseSession:
    async def execute(self, *args, **kwargs):
        raise AssertionError("invalid safe identifiers must not reach database persistence")


class _Result:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _AsyncpgShapedUniqueViolation(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class _ConflictSession:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = iter(outcomes)

    def begin_nested(self):
        return _Savepoint()

    async def execute(self, *_args, **_kwargs):
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return _Result(outcome)


def _link(*, operation_id: str = "operation-1", key: str = "endpoint-create-key-1", device: str = "endpoint-device-1"):
    return type(
        "Link",
        (),
        {
            "operation_id": operation_id,
            "create_idempotency_key": key,
            "endpoint_device_ref": device,
            "capability_code": "context.diagnostic.collect",
        },
    )()


def _integrity(constraint_name: str) -> IntegrityError:
    return IntegrityError("INSERT", {}, _AsyncpgShapedUniqueViolation(constraint_name))


@pytest.mark.asyncio
async def test_repo_creates_idempotent_pending_link_for_local_operation(test_engine):
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    operation = _operation()
    next_attempt_at = datetime(2026, 8, 17, tzinfo=timezone.utc)

    async with session_maker() as session:
        session.add(operation)
        await session.flush()
        repo = EndpointOperationLinksRepo(session)
        created = await repo.create_pending(
            operation_id=operation.operation_id,
            endpoint_device_ref="endpoint-device-1",
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=next_attempt_at,
        )
        replayed = await repo.create_pending(
            operation_id=operation.operation_id,
            endpoint_device_ref="endpoint-device-1",
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=next_attempt_at,
        )

        assert created.link_id == replayed.link_id
        assert created.operation_id == operation.operation_id
        assert created.endpoint_operation_ref is None
        assert created.remote_status == "create_pending"
        assert created.attempt_count == 0
        assert created.endpoint_device_ref == "endpoint-device-1"
        assert created.capability_code == "context.diagnostic.collect"
        assert await repo.get_by_operation_id(operation.operation_id) is created
        assert not {"service_token", "authorization", "raw_response", "parameters"} & set(
            EndpointOperationLink.__table__.columns.keys()
        )


@pytest.mark.asyncio
async def test_repo_concurrently_creates_one_link_for_the_same_immutable_identity(test_engine):
    """A retry race must return one persisted link instead of an IntegrityError."""

    from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    operation = _operation()
    next_attempt_at = datetime(2026, 8, 17, tzinfo=timezone.utc)
    async with session_maker() as session:
        session.add(operation)
        await session.commit()

    start = asyncio.Barrier(2)

    async def create_from_separate_session() -> str:
        async with session_maker() as session:
            await start.wait()
            link = await EndpointOperationLinksRepo(session).create_pending(
                operation_id=operation.operation_id,
                endpoint_device_ref="endpoint-device-1",
                create_idempotency_key="endpoint-create-key-race-1",
                next_attempt_at=next_attempt_at,
            )
            await session.commit()
            return link.link_id

    first_id, second_id = await asyncio.gather(
        create_from_separate_session(),
        create_from_separate_session(),
    )

    assert first_id == second_id
    async with session_maker() as session:
        count = await session.scalar(
            select(func.count()).select_from(EndpointOperationLink).where(
                EndpointOperationLink.operation_id == operation.operation_id
            )
        )
    assert count == 1


@pytest.mark.no_db
def test_endpoint_operation_link_model_uses_only_safe_external_operation_fields():
    columns = EndpointOperationLink.__table__.columns

    assert columns["operation_id"].unique is True
    assert columns["endpoint_operation_ref"].unique is True
    assert columns["create_idempotency_key"].unique is True
    assert columns["endpoint_device_ref"].nullable is False
    assert columns["next_attempt_at"].nullable is False
    assert columns["safe_result_snapshot_json"].nullable is True
    constraints = {constraint.name for constraint in EndpointOperationLink.__table__.constraints}
    assert {"ck_endpoint_operation_links_remote_status", "ck_endpoint_operation_links_attempt_count"} <= constraints


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_repo_rejects_oversized_external_ref_before_any_database_write():
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo

    repo = EndpointOperationLinksRepo(_NoDatabaseSession())
    with pytest.raises(ValidationError):
        await repo.create_pending(
            operation_id="operation-1",
            endpoint_device_ref="x" * 129,
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_repo_conflicts_when_operation_id_is_reused_with_another_idempotency_key():
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinkConflict, EndpointOperationLinksRepo

    repo = EndpointOperationLinksRepo(
        _ConflictSession(
            [
                _integrity("uq_endpoint_operation_links_operation_id"),
                _link(key="other-key"),
                None,
            ]
        )
    )

    with pytest.raises(EndpointOperationLinkConflict):
        await repo.create_pending(
            operation_id="operation-1",
            endpoint_device_ref="endpoint-device-1",
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_repo_conflicts_when_idempotency_key_is_reused_for_another_operation():
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinkConflict, EndpointOperationLinksRepo

    repo = EndpointOperationLinksRepo(_ConflictSession([None, None, _link(operation_id="operation-2")]))

    with pytest.raises(EndpointOperationLinkConflict):
        await repo.create_pending(
            operation_id="operation-1",
            endpoint_device_ref="endpoint-device-1",
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_repo_rethrows_unrelated_integrity_error():
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo

    error = _integrity("fk_endpoint_operation_links_operation_id")
    repo = EndpointOperationLinksRepo(_ConflictSession([error]))

    with pytest.raises(IntegrityError) as raised:
        await repo.create_pending(
            operation_id="operation-1",
            endpoint_device_ref="endpoint-device-1",
            create_idempotency_key="endpoint-create-key-1",
            next_attempt_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )
    assert raised.value is error


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_repo_re_reads_asyncpg_operation_id_conflict_for_matching_identity():
    from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo

    existing = _link()
    repo = EndpointOperationLinksRepo(
        _ConflictSession(
            [
                _integrity("uq_endpoint_operation_links_operation_id"),
                existing,
                existing,
            ]
        )
    )

    result = await repo.create_pending(
        operation_id="operation-1",
        endpoint_device_ref="endpoint-device-1",
        create_idempotency_key="endpoint-create-key-1",
        next_attempt_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    assert result is existing

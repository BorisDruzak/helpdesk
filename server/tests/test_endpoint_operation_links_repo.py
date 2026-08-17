from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

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

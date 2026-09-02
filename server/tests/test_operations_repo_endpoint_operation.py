from __future__ import annotations

import pytest

from app.repos.operations_repo import OperationsRepo


pytestmark = pytest.mark.no_db


class _Session:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_endpoint_operation_can_be_created_without_legacy_device_id():
    session = _Session()

    operation = await OperationsRepo(session).create_operation(
        operation_id="00000000-0000-0000-0000-000000000138",
        device_id=None,
        ticket_id="ticket-1",
        kind="endpoint_operation",
        actor_role="support",
        trace_id="00000000-0000-0000-0000-000000000139",
    )

    assert operation.device_id is None
    assert session.added == [operation]


@pytest.mark.asyncio
async def test_non_endpoint_operation_cannot_omit_legacy_device_id():
    with pytest.raises(ValueError, match="only Endpoint facade operations"):
        await OperationsRepo(_Session()).create_operation(
            operation_id="00000000-0000-0000-0000-000000000140",
            device_id=None,
            kind="tool_call",
            actor_role="support",
            trace_id="00000000-0000-0000-0000-000000000141",
        )

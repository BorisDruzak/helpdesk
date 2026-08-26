from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.no_db


class _NoDatabaseSession:
    async def execute(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("invalid module identity must not reach persistence")


@pytest.mark.asyncio
async def test_module_link_repo_rejects_invalid_module_identity_before_persistence() -> None:
    from app.repos.endpoint_module_operation_links_repo import EndpointModuleOperationLinksRepo

    repo = EndpointModuleOperationLinksRepo(_NoDatabaseSession())

    with pytest.raises(ValueError):
        await repo.create_pending(
            operation_id="operation-1", endpoint_device_ref="endpoint-device-1",
            module_key="INVALID", module_version="1.0.0", inputs={"target": "example.test"},
            create_idempotency_key="endpoint-module-create-1", next_attempt_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )

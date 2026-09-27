from unittest.mock import AsyncMock, Mock

import pytest

from app.db.models import DeviceInventoryBulkOperationItem
from inventory.service import DeviceInventoryService


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_bulk_operation_counts_offline_devices_before_insert():
    session = Mock()
    session.flush = AsyncMock()
    operation = await DeviceInventoryService(session).create_bulk_refresh_operation(
        preview={
            "selected_count": 3,
            "items": [
                {"device_id": "online", "status": "ready"},
                {"device_id": "offline-1", "status": "offline"},
                {"device_id": "offline-2", "status": "offline"},
            ],
        },
        mode="stale", filters=None, wave={"batch_size": 2},
    )
    assert operation.total_count == 3
    assert operation.skipped_count == 2
    items = [call.args[0] for call in session.add.call_args_list
             if isinstance(call.args[0], DeviceInventoryBulkOperationItem)]
    assert [(item.status, item.wave_index) for item in items] == [
        ("pending", 0), ("skipped_offline", 0), ("skipped_offline", 1),
    ]
    session.flush.assert_awaited_once()

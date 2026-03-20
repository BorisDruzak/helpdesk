import asyncio
import sys
from pathlib import Path

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_bridge.api_server import UiApiServer
from ui_bridge.event_bus import EventBus


@pytest.mark.asyncio
async def test_ui_api_server_stop_does_not_hang_with_active_sse_client():
    server = UiApiServer(EventBus(), host="127.0.0.1", port=0)
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    response = await session.get(
        f"http://127.0.0.1:{port}/ui/events",
        headers={"Accept": "text/event-stream"},
    )

    try:
        assert response.status == 200
        await asyncio.wait_for(response.content.readline(), timeout=1.0)
        await asyncio.wait_for(server.stop(), timeout=1.5)
        assert server.runner is None
        assert server.site is None
    finally:
        response.close()
        await session.close()

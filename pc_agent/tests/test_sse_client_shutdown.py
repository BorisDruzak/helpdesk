import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_gui.sse_client import SseClient


class FakeResponse:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_stop_async_closes_active_response_and_session():
    client = SseClient("http://127.0.0.1:8765")
    response = FakeResponse()
    session = FakeSession()

    client._running = True
    client._response = response
    client._session = session

    await client.stop_async()

    assert client._running is False
    assert response.closed is True
    assert session.closed is True
    assert client._response is None
    assert client._session is None

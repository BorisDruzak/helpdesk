import aiohttp
import pytest
from aiohttp import WSMsgType

from scripts.run_https_reverse_proxy import _bridge_ws_to_client, _bridge_ws_to_target


class _Message:
    def __init__(self, msg_type, data=None, extra=""):
        self.type = msg_type
        self.data = data
        self.extra = extra


class _AsyncMessages:
    def __init__(self, *messages):
        self._messages = list(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


class _FakeEndpoint(_AsyncMessages):
    def __init__(self, *messages):
        super().__init__(*messages)
        self.closed_with = None
        self.close_code = None

    async def send_str(self, _data):
        return None

    async def send_bytes(self, _data):
        return None

    async def ping(self):
        return None

    async def pong(self):
        return None

    async def close(self, code=None, message=b""):
        self.closed_with = (code, message)
        self.close_code = code


@pytest.mark.asyncio
async def test_websocket_proxy_preserves_upstream_close_code_to_client():
    upstream = _FakeEndpoint(_Message(aiohttp.WSMsgType.CLOSE, 4003, "Token required"))
    client = _FakeEndpoint()

    await _bridge_ws_to_client(upstream, client)

    assert client.closed_with == (4003, b"Token required")


@pytest.mark.asyncio
async def test_websocket_proxy_preserves_client_close_code_to_upstream():
    client = _FakeEndpoint(_Message(WSMsgType.CLOSE, 4002, "Superseded"))
    upstream = _FakeEndpoint()

    await _bridge_ws_to_target(client, upstream)

    assert upstream.closed_with == (4002, b"Superseded")

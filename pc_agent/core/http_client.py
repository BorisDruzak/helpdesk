import json
import aiohttp
from aiohttp import ClientTimeout
from loguru import logger

class AioHttpClient:
    def __init__(self, base_url: str, default_timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def post_json(self, path: str, payload: dict, timeout: int | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        session = await self._get_session()
        t = ClientTimeout(total=timeout or self.default_timeout)

        logger.debug(f"[HTTP] POST {url} payload={payload}")
        async with session.post(url, json=payload, timeout=t) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {text}")
            try:
                return json.loads(text)
            except Exception:
                raise RuntimeError(f"Invalid JSON response: {text}")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


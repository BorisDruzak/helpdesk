#!/usr/bin/env python3
"""Small TLS reverse proxy for the pc_client stand.

This is intentionally narrow: it terminates HTTPS/WSS for a test stand and
forwards traffic to the existing aiohttp server. Production should use a real
reverse proxy with managed certificates.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import ssl
from collections.abc import Iterable
from contextlib import suppress
from typing import Final
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from aiohttp import WSMsgType, web


LOG = logging.getLogger("pc_client_https_proxy")

HOP_BY_HOP_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def _filtered_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {key: value for key, value in headers if key.lower() not in HOP_BY_HOP_HEADERS}


def _target_url(target_base: str, request: web.Request, *, websocket: bool = False) -> str:
    base = urlsplit(target_base.rstrip("/"))
    scheme = "ws" if websocket else base.scheme
    if websocket and base.scheme == "https":
        scheme = "wss"
    path = request.raw_path
    if path.startswith("/"):
        path = path[1:]
    return urlunsplit((scheme, base.netloc, f"{base.path.rstrip('/')}/{path}", "", ""))


async def _bridge_ws_to_target(
    source: web.WebSocketResponse,
    target: aiohttp.ClientWebSocketResponse,
) -> None:
    async for msg in source:
        if msg.type == WSMsgType.TEXT:
            await target.send_str(msg.data)
        elif msg.type == WSMsgType.BINARY:
            await target.send_bytes(msg.data)
        elif msg.type == WSMsgType.PING:
            await target.ping()
        elif msg.type == WSMsgType.PONG:
            await target.pong()
        elif msg.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR}:
            close_code = msg.data or source.close_code
            close_reason = msg.extra or ""
            if close_code:
                await target.close(code=close_code, message=str(close_reason).encode("utf-8"))
            break


async def _bridge_ws_to_client(
    target: aiohttp.ClientWebSocketResponse,
    source: web.WebSocketResponse,
) -> None:
    async for msg in target:
        if msg.type == aiohttp.WSMsgType.TEXT:
            await source.send_str(msg.data)
        elif msg.type == aiohttp.WSMsgType.BINARY:
            await source.send_bytes(msg.data)
        elif msg.type == aiohttp.WSMsgType.PING:
            await source.ping()
        elif msg.type == aiohttp.WSMsgType.PONG:
            await source.pong()
        elif msg.type in {
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.ERROR,
        }:
            close_code = msg.data or target.close_code
            close_reason = msg.extra or ""
            if close_code:
                await source.close(code=close_code, message=str(close_reason).encode("utf-8"))
            break


async def handle_websocket(request: web.Request) -> web.StreamResponse:
    session: aiohttp.ClientSession = request.app["client_session"]
    target_base: str = request.app["target_base"]
    target_url = _target_url(target_base, request, websocket=True)

    headers = _filtered_headers(request.headers.items())
    headers["X-Forwarded-Proto"] = "https"
    headers["X-Forwarded-Host"] = request.host

    try:
        async with session.ws_connect(
            target_url,
            headers=headers,
            max_msg_size=request.app["max_ws_msg_size"],
            heartbeat=request.app["ws_heartbeat"],
        ) as upstream_ws:
            client_ws = web.WebSocketResponse(max_msg_size=request.app["max_ws_msg_size"])
            await client_ws.prepare(request)
            to_target = asyncio.create_task(_bridge_ws_to_target(client_ws, upstream_ws))
            to_client = asyncio.create_task(_bridge_ws_to_client(upstream_ws, client_ws))
            done, pending = await asyncio.wait(
                {to_target, to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
            if not client_ws.closed:
                close_code = upstream_ws.close_code
                with suppress(Exception):
                    if close_code:
                        await client_ws.close(code=close_code)
                    else:
                        await client_ws.close()
            return client_ws
    except aiohttp.WSServerHandshakeError as exc:
        LOG.info(
            "upstream websocket rejected: status=%s path=%s",
            exc.status,
            request.rel_url,
        )
        return web.Response(status=exc.status, text=exc.message)
    except Exception:
        LOG.exception("websocket proxy failed: %s", request.rel_url)
        return web.Response(status=502, text="upstream websocket failed")


async def handle_http(request: web.Request) -> web.StreamResponse:
    session: aiohttp.ClientSession = request.app["client_session"]
    target_base: str = request.app["target_base"]
    target_url = _target_url(target_base, request)

    body = await request.read()
    headers = _filtered_headers(request.headers.items())
    headers["X-Forwarded-Proto"] = "https"
    headers["X-Forwarded-Host"] = request.host

    try:
        async with session.request(
            request.method,
            target_url,
            headers=headers,
            data=body if body else None,
            allow_redirects=False,
        ) as upstream:
            proxy_response = web.StreamResponse(
                status=upstream.status,
                reason=upstream.reason,
                headers=_filtered_headers(upstream.headers.items()),
            )
            await proxy_response.prepare(request)
            async for chunk in upstream.content.iter_chunked(1024 * 64):
                await proxy_response.write(chunk)
            await proxy_response.write_eof()
            return proxy_response
    except asyncio.CancelledError:
        raise
    except Exception:
        LOG.exception("http proxy failed: %s %s", request.method, request.rel_url)
        return web.json_response(
            {"status": "error", "error": "HTTPS proxy upstream request failed"},
            status=502,
        )


async def dispatch(request: web.Request) -> web.StreamResponse:
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await handle_websocket(request)
    return await handle_http(request)


async def _cleanup_client_session(app: web.Application) -> None:
    await app["client_session"].close()


async def _startup_client_session(app: web.Application) -> None:
    timeout = aiohttp.ClientTimeout(total=app["http_timeout_sec"])
    app["client_session"] = aiohttp.ClientSession(timeout=timeout)


def create_app(args: argparse.Namespace) -> web.Application:
    app = web.Application(client_max_size=args.client_max_size)
    app["target_base"] = args.target.rstrip("/")
    app["http_timeout_sec"] = args.http_timeout_sec
    app["max_ws_msg_size"] = args.max_ws_msg_size
    app["ws_heartbeat"] = args.ws_heartbeat_sec
    app.router.add_route("*", "/{tail:.*}", dispatch)
    app.on_startup.append(_startup_client_session)
    app.on_cleanup.append(_cleanup_client_session)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pc_client stand HTTPS reverse proxy.")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=9443)
    parser.add_argument("--target", default="http://127.0.0.1:8666")
    parser.add_argument("--cert-file", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--http-timeout-sec", type=float, default=300.0)
    parser.add_argument("--client-max-size", type=int, default=1024 * 1024 * 1024)
    parser.add_argument("--max-ws-msg-size", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--ws-heartbeat-sec", type=float, default=30.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(args.cert_file, args.key_file)
    LOG.info(
        "starting HTTPS proxy on %s:%s -> %s",
        args.listen_host,
        args.listen_port,
        args.target,
    )
    web.run_app(
        create_app(args),
        host=args.listen_host,
        port=args.listen_port,
        ssl_context=ssl_context,
    )


if __name__ == "__main__":
    main()


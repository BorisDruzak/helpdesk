"""aiohttp AppKey helpers for server application state."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from state_manager import StateManager


STATE_APP_KEY = web.AppKey("state", StateManager)
OBSERVER_REFRESH_RUNTIME_APP_KEY = web.AppKey("observer_refresh_runtime", Any)


def bind_app_value(
    app: web.Application,
    *,
    key: web.AppKey[Any],
    legacy_name: str,
    value: Any,
) -> None:
    """Bind an aiohttp AppKey and keep the legacy string alias for existing reads."""
    app[key] = value
    app._state[legacy_name] = value


def replace_bound_app_value(
    app: web.Application,
    *,
    key: web.AppKey[Any],
    legacy_name: str,
    value: Any,
) -> None:
    """Replace an already bound app value without triggering aiohttp started-app warnings."""
    app._state[key] = value
    app._state[legacy_name] = value

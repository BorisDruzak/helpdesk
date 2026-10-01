"""Optional Sentry process bootstrap. No SDK import or initialization at import."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from .privacy import EventSanitizer

DEFAULT_IDENTITY_PATH = Path(__file__).resolve().parents[2] / "release-identity.json"
_SHA = re.compile(r"[a-fA-F0-9]{40}")
_ENVIRONMENT = re.compile(r"[A-Za-z0-9_.-]{1,64}")


@dataclass(frozen=True)
class SentrySettings:
    dsn: str = field(repr=False)
    environment: str
    traces_sample_rate: float
    release_override: str = field(repr=False)

    @classmethod
    def from_config(cls, config: Any) -> SentrySettings:
        fallback = "production" if config.APP_ENV == "prod" else config.APP_ENV
        if not _ENVIRONMENT.fullmatch(fallback):
            fallback = "development"
        environment = str(config.SENTRY_ENVIRONMENT or "").strip()
        if not _ENVIRONMENT.fullmatch(environment):
            environment = fallback
        try:
            rate = float(config.SENTRY_TRACES_SAMPLE_RATE)
        except (TypeError, ValueError, OverflowError):
            rate = .10
        if not math.isfinite(rate):
            rate = .10
        return cls(str(config.SENTRY_DSN or "").strip(), environment,
                   max(0., min(rate, 1.)), str(config.SENTRY_RELEASE or "").strip())


def resolve_release(override: str, identity_path: Path = DEFAULT_IDENTITY_PATH) -> str | None:
    if _SHA.fullmatch(override):
        return override.lower()
    try:
        # Fixed immutable release path, bounded read; no cwd/Git lookup.
        with identity_path.open("rb") as handle:
            raw = handle.read(4097)
        if len(raw) > 4096:
            return None
        identity = json.loads(raw)
        value = identity.get("helpdesk_git_sha") if isinstance(identity, dict) else None
        return value.lower() if isinstance(value, str) and _SHA.fullmatch(value) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _load_sdk():
    import sentry_sdk
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration
    return sentry_sdk, AioHttpIntegration


class SentryRuntime:
    def __init__(self, client: Any = None):
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                # Standard SDK HTTP transport queues on a background worker.
                # Called after run_app returns, never on the serving event loop.
                client.close(timeout=1.0)
            except Exception:
                logger.warning("Sentry shutdown incomplete; Helpdesk shutdown continues")


_runtime: SentryRuntime | None = None


def configure_sentry(app: Any, *, config: Any = None,
                     identity_path: Path = DEFAULT_IDENTITY_PATH) -> SentryRuntime:
    """Initialize at most once per process, before aiohttp starts serving."""
    global _runtime
    if _runtime is not None:
        return _runtime
    _runtime = SentryRuntime()
    try:
        if config is None:
            import config as runtime_config
            config = runtime_config
        settings = SentrySettings.from_config(config)
        if not settings.dsn:
            return _runtime
        sdk, integration = _load_sdk()
        release = resolve_release(settings.release_override, identity_path)
        sanitizer = EventSanitizer({resource.canonical for resource in app.router.resources()},
                                   release, settings.environment)
        sdk.init(
            dsn=settings.dsn, environment=settings.environment, release=release or "",
            server_name="", integrations=[integration(transaction_style="method_and_path_pattern")],
            default_integrations=False, auto_enabling_integrations=False,
            send_default_pii=False, data_collection={"user_info": False, "http_bodies": []},
            max_request_body_size="never", include_local_variables=False, include_source_context=False,
            before_send=sanitizer, before_send_transaction=sanitizer,
            max_breadcrumbs=0, auto_session_tracking=False, send_client_reports=False,
            enable_logs=False, enable_metrics=False, profiles_sample_rate=0., profile_session_sample_rate=0.,
            trace_lifecycle="static", traces_sample_rate=settings.traces_sample_rate,
            trace_propagation_targets=[], enable_backpressure_handling=False,
            transport_queue_size=32, shutdown_timeout=1., debug=False, spotlight=False,
        )
        _runtime = SentryRuntime(sdk.get_client())
    except Exception:
        # Do not interpolate config, SDK errors, traceback or event contents.
        logger.warning("Sentry observability unavailable; Helpdesk continues without it")
    return _runtime

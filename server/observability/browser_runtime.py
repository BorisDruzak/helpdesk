"""Allowlisted public browser configuration; independent of immutable assets."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .sentry import DEFAULT_IDENTITY_PATH, SentrySettings, resolve_release


def _valid_dsn(value: Any, *, production: bool) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    if re.search(r'[\s\\<>"\x00-\x1f\x7f]', value):
        return False
    if not re.match(r'^https?://[A-Za-z0-9_]+@(?:[A-Za-z0-9.-]+|\[[a-fA-F0-9:.]+\])(?::[0-9]+)?/', value):
        return False
    try:
        url = urlsplit(value)
        return bool(
            url.scheme in ({'https'} if production else {'https', 'http'})
            and url.hostname and url.port != 0
            and url.username and re.fullmatch(r'[A-Za-z0-9_]+', url.username)
            and url.password is None and not url.query and not url.fragment
            and re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*/[0-9]+', url.path)
            and '?' not in value and '#' not in value
        )
    except (ValueError, TypeError):
        return False


def browser_runtime_config(config: Any, *, identity_path: Path | None = None) -> dict:
    settings = SentrySettings.from_config(config)
    dsn = getattr(config, 'SENTRY_BROWSER_DSN', '')
    if not _valid_dsn(dsn, production=config.APP_ENV in {'prod', 'production'} or settings.environment == 'production'):
        return {'sentry': None}
    raw_rate = getattr(config, 'SENTRY_BROWSER_TRACES_SAMPLE_RATE', .05)
    try:
        rate = float(raw_rate) if not isinstance(raw_rate, bool) else math.nan
    except (ValueError, TypeError, OverflowError):
        rate = math.nan
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        rate = .05
    public = {'dsn': dsn, 'environment': settings.environment, 'tracesSampleRate': rate}
    release = resolve_release(settings.release_override, identity_path or DEFAULT_IDENTITY_PATH)
    if release is not None:
        public['release'] = release
    return {'sentry': public}


def serialize_browser_runtime_config(payload: dict) -> str:
    value = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for char in ('<', '>', '&', '\u2028', '\u2029'):
        value = value.replace(char, f'\\u{ord(char):04x}')
    return value

from __future__ import annotations

from typing import Iterable


AGENT_RECIPE_RUNNER_PROVIDER_ID = "agent_recipe_runner"
AGENT_RECIPE_SUPPORTED_PLATFORMS = {"win32", "linux"}
DEFAULT_AGENT_RECIPE_PRIMITIVES = [
    {"primitive_id": "file.exists", "primitive_version": "1.0", "title": "File exists", "platforms": ["win32", "linux"], "risk_level": "low"},
    {"primitive_id": "process.exists", "primitive_version": "1.0", "title": "Process exists", "platforms": ["win32", "linux"], "risk_level": "low"},
    {"primitive_id": "dns.resolve", "primitive_version": "1.0", "title": "DNS resolve", "platforms": ["win32", "linux"], "risk_level": "low"},
    {"primitive_id": "tcp.connect", "primitive_version": "1.0", "title": "TCP connect", "platforms": ["win32", "linux"], "risk_level": "low"},
    {"primitive_id": "http.request", "primitive_version": "1.0", "title": "HTTP request", "platforms": ["win32", "linux"], "risk_level": "low"},
    {"primitive_id": "service.status", "primitive_version": "1.0", "title": "Windows service status", "platforms": ["win32"], "risk_level": "low"},
    {"primitive_id": "systemd.service.status", "primitive_version": "1.0", "title": "systemd service status", "platforms": ["linux"], "risk_level": "low"},
]


class AgentRecipeValidationError(ValueError):
    """Raised when a declarative agent recipe contract is invalid."""


def normalize_recipe_platforms(platforms: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for item in platforms or []:
        value = str(item or "").strip().lower()
        if value in {"windows", "win"}:
            value = "win32"
        if value in {"mac", "macos", "darwin"}:
            raise AgentRecipeValidationError("agent_recipe does not support macOS platforms")
        if value not in AGENT_RECIPE_SUPPORTED_PLATFORMS:
            raise AgentRecipeValidationError("agent_recipe platforms must be win32 and/or linux")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise AgentRecipeValidationError("agent_recipe requires at least one supported platform")
    return normalized

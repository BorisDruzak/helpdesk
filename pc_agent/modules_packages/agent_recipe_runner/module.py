from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import http.client
import os
from pathlib import Path
import platform
import socket
import ssl
import time
from typing import Any
from urllib.parse import urlparse

from pc_agent.modules.base_module import BaseCollector


MODULE_VERSION = "1.0.0"
SUPPORTED_PLATFORMS = {"win32", "linux"}
DEFAULT_TIMEOUT_SEC = 10
MAX_TIMEOUT_SEC = 60
MAX_OUTPUT_BYTES = 64 * 1024
MAX_ITEMS = 200


def _current_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "win32"
    if system == "linux":
        return "linux"
    return system


def _bounded_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except Exception:
        timeout = DEFAULT_TIMEOUT_SEC
    return min(max(timeout, 0.1), MAX_TIMEOUT_SEC)


def _primitive_catalog() -> list[dict[str, Any]]:
    return [
        {
            "primitive_id": "file.exists",
            "primitive_version": "1.0",
            "title": "File exists",
            "platforms": ["win32", "linux"],
            "params_schema": {"required": ["path"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "process.exists",
            "primitive_version": "1.0",
            "title": "Process exists",
            "platforms": ["win32", "linux"],
            "params_schema": {"required": ["process_name"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "dns.resolve",
            "primitive_version": "1.0",
            "title": "DNS resolve",
            "platforms": ["win32", "linux"],
            "params_schema": {"required": ["hostname"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "tcp.connect",
            "primitive_version": "1.0",
            "title": "TCP connect",
            "platforms": ["win32", "linux"],
            "params_schema": {"required": ["host", "port"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "http.request",
            "primitive_version": "1.0",
            "title": "HTTP request",
            "platforms": ["win32", "linux"],
            "params_schema": {"required": ["url"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "service.status",
            "primitive_version": "1.0",
            "title": "Windows service status",
            "platforms": ["win32"],
            "params_schema": {"required": ["service_name"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
        {
            "primitive_id": "systemd.service.status",
            "primitive_version": "1.0",
            "title": "systemd service status",
            "platforms": ["linux"],
            "params_schema": {"required": ["service_name"]},
            "output_schema": {"type": "object"},
            "safety": {"read_only": True, "side_effects": False},
        },
    ]


class AgentRecipeRunnerModule(BaseCollector):
    @property
    def name(self) -> str:
        return "agent_recipe_runner"

    def version(self) -> str:
        return MODULE_VERSION

    async def collect(self) -> dict[str, Any]:
        return {
            "runner_provider_id": self.name,
            "runner_version": MODULE_VERSION,
            "primitive_count": len(_primitive_catalog()),
        }

    def describe_primitives(self) -> list[dict[str, Any]]:
        return _primitive_catalog()

    def validate_recipe(self, recipe_payload: dict[str, Any], platform_context: dict[str, Any]) -> dict[str, Any]:
        primitive_id = str(recipe_payload.get("primitive_id") or "").strip()
        primitive = self._primitive(primitive_id)
        if primitive is None:
            return {"status": "error", "code": "PRIMITIVE_NOT_SUPPORTED", "message": f"Primitive '{primitive_id}' is not supported"}
        platform_name = str(platform_context.get("platform") or _current_platform()).strip().lower()
        if platform_name not in SUPPORTED_PLATFORMS:
            return {"status": "error", "code": "UNSUPPORTED_PLATFORM", "message": f"Platform '{platform_name}' is not supported"}
        recipe_platforms = recipe_payload.get("recipe", {}).get("platforms") or primitive.get("platforms") or []
        if platform_name not in recipe_platforms:
            return {"status": "error", "code": "UNSUPPORTED_PLATFORM", "message": f"Recipe does not support '{platform_name}'"}
        params = self._merged_params(recipe_payload, platform_name)
        for required in primitive.get("params_schema", {}).get("required", []):
            if required not in params or params.get(required) in (None, ""):
                return {"status": "error", "code": "INVALID_PARAMS", "message": f"Missing required parameter '{required}'"}
        return {"status": "passed"}

    async def run_recipe(self, recipe_payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        platform_name = str(runtime_context.get("platform") or _current_platform()).strip().lower()
        params = self._merged_params(recipe_payload, platform_name)
        primitive_id = str(recipe_payload.get("primitive_id") or "").strip()
        try:
            output = await self._run_primitive(primitive_id, params)
            status = "success"
            error = None
        except Exception as exc:
            output = {"error": str(exc), "primitive_id": primitive_id}
            status = "error"
            error = {"code": "PRIMITIVE_FAILED", "message": str(exc), "retriable": False}
        duration_ms = int((time.perf_counter() - started) * 1000)
        changed = False
        return {
            "status": status,
            "data": {
                "observations": output,
                "result": output,
                "artifacts": [],
                "changed": changed,
            },
            "error": error,
            "meta": {
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "command": "run_recipe",
                "request_id": runtime_context.get("request_id"),
                "module_versions": {"agent_recipe_runner": MODULE_VERSION},
            },
        }

    def _primitive(self, primitive_id: str) -> dict[str, Any] | None:
        return next((item for item in _primitive_catalog() if item["primitive_id"] == primitive_id), None)

    def _merged_params(self, recipe_payload: dict[str, Any], platform_name: str) -> dict[str, Any]:
        recipe = recipe_payload.get("recipe") if isinstance(recipe_payload.get("recipe"), dict) else {}
        params = dict(recipe.get("params") or {})
        variants = recipe.get("platform_variants") if isinstance(recipe.get("platform_variants"), dict) else {}
        variant = variants.get(platform_name) if isinstance(variants.get(platform_name), dict) else {}
        params.update(variant.get("params") or {})
        params.update(recipe_payload.get("runtime_params") or {})
        return params

    async def _run_primitive(self, primitive_id: str, params: dict[str, Any]) -> dict[str, Any]:
        if primitive_id == "file.exists":
            return self._file_exists(params)
        if primitive_id == "process.exists":
            return self._process_exists(params)
        if primitive_id == "dns.resolve":
            return await asyncio.to_thread(self._dns_resolve, params)
        if primitive_id == "tcp.connect":
            return await asyncio.to_thread(self._tcp_connect, params)
        if primitive_id == "http.request":
            return await asyncio.to_thread(self._http_request, params)
        if primitive_id == "service.status":
            return self._windows_service_status(params)
        if primitive_id == "systemd.service.status":
            return await asyncio.to_thread(self._systemd_service_status, params)
        raise ValueError(f"Unsupported primitive: {primitive_id}")

    def _file_exists(self, params: dict[str, Any]) -> dict[str, Any]:
        path = str(params.get("path") or "")
        if len(path) > 4096:
            raise ValueError("path is too long")
        item = Path(path).expanduser()
        exists = item.exists()
        return {"path": path, "exists": exists, "is_file": item.is_file() if exists else False, "is_dir": item.is_dir() if exists else False}

    def _process_exists(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("process_name") or "").strip().lower()
        if not name or len(name) > 260 or any(ch in name for ch in "\\/:*?\"<>|"):
            raise ValueError("invalid process_name")
        matches: list[dict[str, Any]] = []
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name"]):
                proc_name = str((proc.info or {}).get("name") or "").lower()
                if proc_name == name:
                    matches.append({"pid": proc.info.get("pid"), "name": proc.info.get("name")})
                    if len(matches) >= MAX_ITEMS:
                        break
        except Exception:
            matches = []
        return {"process_name": name, "exists": bool(matches), "matches": matches[:MAX_ITEMS]}

    def _dns_resolve(self, params: dict[str, Any]) -> dict[str, Any]:
        hostname = str(params.get("hostname") or "").strip()
        if not hostname or len(hostname) > 255:
            raise ValueError("invalid hostname")
        infos = socket.getaddrinfo(hostname, None)
        addresses = sorted({item[4][0] for item in infos})[:MAX_ITEMS]
        return {"hostname": hostname, "resolved": bool(addresses), "addresses": addresses}

    def _tcp_connect(self, params: dict[str, Any]) -> dict[str, Any]:
        host = str(params.get("host") or "").strip()
        port = int(params.get("port"))
        timeout = _bounded_timeout(params.get("timeout_sec"))
        if not host or len(host) > 255 or port < 1 or port > 65535:
            raise ValueError("invalid tcp target")
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                connected = True
                error = None
        except OSError as exc:
            connected = False
            error = str(exc)
        return {"host": host, "port": port, "connected": connected, "duration_ms": int((time.perf_counter() - started) * 1000), "error": error}

    def _http_request(self, params: dict[str, Any]) -> dict[str, Any]:
        url = str(params.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url must be http or https")
        method = str(params.get("method") or "GET").upper()
        if method not in {"GET", "HEAD"}:
            raise ValueError("only GET/HEAD are supported")
        timeout = _bounded_timeout(params.get("timeout_sec"))
        headers = {str(k): str(v) for k, v in (params.get("headers") or {}).items() if str(k).lower() not in {"authorization", "cookie"}}
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        context = ssl.create_default_context() if parsed.scheme == "https" else None
        conn = conn_cls(parsed.hostname, parsed.port, timeout=timeout, context=context) if context else conn_cls(parsed.hostname, parsed.port, timeout=timeout)
        try:
            conn.request(method, path, headers=headers)
            response = conn.getresponse()
            response.read(min(MAX_OUTPUT_BYTES, 1024))
            return {"url": url, "method": method, "status_code": response.status, "reason": response.reason, "ok": 200 <= response.status < 400}
        finally:
            conn.close()

    def _windows_service_status(self, params: dict[str, Any]) -> dict[str, Any]:
        if _current_platform() != "win32":
            raise ValueError("service.status is supported only on Windows")
        service_name = str(params.get("service_name") or "").strip()
        if not service_name or len(service_name) > 256:
            raise ValueError("invalid service_name")
        try:
            import psutil

            service = psutil.win_service_get(service_name)
            info = service.as_dict()
            state = str(info.get("status") or "unknown")
            exists = True
        except Exception as exc:
            state = "missing"
            exists = False
            info = {"error": str(exc)}
        expected = params.get("expected_state")
        return {"service_name": service_name, "exists": exists, "state": state, "matches_expected": expected is None or state == expected, "details": info}

    def _systemd_service_status(self, params: dict[str, Any]) -> dict[str, Any]:
        if _current_platform() != "linux":
            raise ValueError("systemd.service.status is supported only on Linux")
        service_name = str(params.get("service_name") or "").strip()
        if not service_name or len(service_name) > 256 or any(ch in service_name for ch in ";&|`$<>"):
            raise ValueError("invalid service_name")
        # Bounded, argument-vector call to a fixed binary. This is not a generic shell runner.
        import subprocess

        completed = subprocess.run(
            ["systemctl", "show", service_name, "--property=ActiveState,SubState,LoadState", "--no-page"],
            capture_output=True,
            text=True,
            timeout=_bounded_timeout(params.get("timeout_sec")),
            check=False,
        )
        output = completed.stdout[:MAX_OUTPUT_BYTES]
        values = {}
        for line in output.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        state = values.get("ActiveState") or "unknown"
        expected = params.get("expected_state")
        return {"service_name": service_name, "exists": values.get("LoadState") != "not-found", "state": state, "matches_expected": expected is None or state == expected, "details": values}


def register() -> AgentRecipeRunnerModule:
    return AgentRecipeRunnerModule()

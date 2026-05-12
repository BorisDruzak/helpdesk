#!/usr/bin/env python3
"""Run live observer canaries against a pc_client server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys
import textwrap
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp

WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.manage_remote_stack import (  # noqa: E402
    DEFAULT_KEY,
    DEFAULT_REMOTE,
    REMOTE_ROOT,
    REMOTE_SERVER_PYTHON,
)


DEFAULT_BASE_URL = "https://192.168.100.17:9443"
DEFAULT_WS_URL = "wss://192.168.100.17:9443/ws"
DEFAULT_UI_WS_URL = "wss://192.168.100.17:9443/ws_ui"
INSTANCE_ROOT = WORKSPACE / ".local-agent" / "instances"
ARTIFACTS_DIR = WORKSPACE / "artifacts" / "observer_canaries"
DEFAULT_COVERAGE_ROOT_KINDS = (
    "module_install",
    "module_update",
    "module_remove",
    "consent",
    "retry_exhausted",
    "ws_delivery",
    "module_reconcile",
    "playbook_run",
    "web_auth",
    "observer_runtime",
    "capability_run",
    "server_connector_query",
    "observer_query",
    "manual_evidence",
    "remote_assist",
)
SOURCE_COVERAGE_ROOT_KINDS = (
    "module_reconcile",
    "playbook_run",
    "web_auth",
    "observer_runtime",
    "capability_run",
    "server_connector_query",
    "observer_query",
    "manual_evidence",
    "remote_assist",
)
DEFAULT_AGENT_BUILD_TARGETS = ("windows_amd64", "linux_alt_x86_64")


@dataclass
class ScenarioResult:
    name: str
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_step(message: str) -> None:
    print(f"[observer-canary] {message}")


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _scenario_to_dict(result: ScenarioResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, ScenarioResult):
        return asdict(result)
    return dict(result)


def build_observer_coverage_summary(
    results: list[ScenarioResult | dict[str, Any]],
    *,
    required_root_kinds: list[str] | tuple[str, ...] = DEFAULT_COVERAGE_ROOT_KINDS,
) -> dict[str, Any]:
    observed: dict[str, list[dict[str, str]]] = {}
    trace_refs: list[dict[str, str]] = []
    for raw in results:
        item = _scenario_to_dict(raw)
        if not item.get("ok"):
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        root_kind = str(details.get("root_kind") or "").strip()
        trace_id = str(details.get("trace_id") or "").strip()
        if not root_kind or not trace_id:
            continue
        ref = {
            "scenario": str(item.get("name") or ""),
            "root_kind": root_kind,
            "trace_id": trace_id,
        }
        observed.setdefault(root_kind, []).append(ref)
        trace_refs.append(ref)

    required = [str(item).strip() for item in required_root_kinds if str(item).strip()]
    observed_root_kinds = sorted(root_kind for root_kind in observed if root_kind in required)
    missing_root_kinds = [root_kind for root_kind in required if root_kind not in observed]
    return {
        "ok": not missing_root_kinds,
        "required_root_kinds": required,
        "observed_root_kinds": observed_root_kinds,
        "missing_root_kinds": missing_root_kinds,
        "trace_refs": trace_refs,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
    coverage_ok = bool(coverage.get("ok"))
    missing = [f"`{item}`" for item in coverage.get("missing_root_kinds") or []]
    observed = [f"`{item}`" for item in coverage.get("observed_root_kinds") or []]
    lines = [
        "# Observer Canary Report",
        "",
        f"- Generated: `{report.get('generated_at') or ''}`",
        f"- Base URL: `{report.get('base_url') or ''}`",
        f"- Device: `{report.get('device_id') or 'n/a'}`",
        f"- Coverage: **{'passed' if coverage_ok else 'failed'}**",
        f"- Observed root kinds: {', '.join(observed) if observed else 'none'}",
        f"- Missing root kinds: {', '.join(missing) if missing else 'none'}",
        "",
        "## Results",
        "",
        "| Status | Scenario | Summary |",
        "| --- | --- | --- |",
    ]
    for item in report.get("results") or []:
        if not isinstance(item, dict):
            continue
        marker = "OK" if item.get("ok") else "FAIL"
        name = str(item.get("name") or "").replace("|", "\\|")
        summary = str(item.get("summary") or "").replace("|", "\\|")
        lines.append(f"| {marker} | {name} | {summary} |")
    lines.append("")
    return "\n".join(lines)


def extract_tool_result_version(tool_result: Any) -> Optional[str]:
    if not isinstance(tool_result, dict):
        return None
    top_level = tool_result.get("version")
    if isinstance(top_level, str) and top_level.strip():
        return top_level.strip()
    observations = tool_result.get("observations")
    if isinstance(observations, dict):
        observed = observations.get("version")
        if isinstance(observed, str) and observed.strip():
            return observed.strip()
    nested_result = tool_result.get("result")
    if isinstance(nested_result, dict):
        nested_top_level = nested_result.get("version")
        if isinstance(nested_top_level, str) and nested_top_level.strip():
            return nested_top_level.strip()
        output = nested_result.get("output")
        if isinstance(output, dict):
            output_version = output.get("version")
            if isinstance(output_version, str) and output_version.strip():
                return output_version.strip()
    return None


def build_ws_chat_outbox_item(
    *,
    device_id: str,
    ticket_id: str,
    outbox_id: str,
    agent_seq: int,
    trace_id: str,
    text: str,
    actor_role: str = "agent",
) -> dict[str, Any]:
    return {
        "type": "outbox_item",
        "request_id": str(uuid.uuid4()),
        "device_id": device_id,
        "protocol_version": "ws_ticket_v3",
        "trace_id": trace_id,
        "ticket_id": ticket_id,
        "meta": {"actor_role": actor_role},
        "payload": {
            "outbox_id": outbox_id,
            "item_type": "job_event",
            "agent_seq": agent_seq,
            "event": {
                "event": "chat_message",
                "from": actor_role,
                "text": text,
                "ticket_id": ticket_id,
            },
        },
    }


def find_ws_message(messages: list[dict[str, Any]], message_type: str) -> Optional[dict[str, Any]]:
    for item in reversed(messages):
        if item.get("type") == message_type:
            return item
    return None


def build_remote_python_shell(*, remote_root: str = REMOTE_ROOT, remote_python: str = REMOTE_SERVER_PYTHON) -> str:
    server_root = f"{remote_root.rstrip('/')}/server"
    pythonpath = f"{server_root}:{remote_root.rstrip('/')}"
    return (
        f"cd {shlex.quote(server_root)} && "
        f"PYTHONPATH={shlex.quote(pythonpath)} "
        f"{shlex.quote(remote_python)} -"
    )


def build_canary_module_payload(module_name: str, version: str) -> dict[str, Any]:
    shared_dependencies = {
        "min_agent_version": "3.1.19",
        "required_binaries": [],
        "required_python_packages": [],
        "required_services": [],
        "required_permissions": [],
    }

    shared_redaction = {"enabled": True, "allow_raw_sensitive_data": False}
    shared_metadata = {
        "domain": module_name,
        "platforms": ["any"],
        "risk_level": "safe_read",
        "requires_consent": False,
        "timeout_sec": 300,
        "idempotent": True,
        "side_effects": False,
        "allow_roles": ["admin", "support"],
        "scopes": ["observer_canary"],
        "origin": "managed",
        "tool_kind": "diagnostic",
    }
    return {
        "module_name": module_name,
        "version": version,
        "description": f"Observer canary module {version}",
        "owner_scope": "vendor",
        "module_api_version": "1.0.0",
        "entrypoint": "module:register",
        "platforms": ["any"],
        "requirements": [],
        "optional_requirements": [],
        "set_preferred": False,
        "tools": [
            {
                "tool_name": f"{module_name}.echo",
                "method_name": "echo_tool",
                "description": "Return the published canary module version.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "version": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
                "metadata": dict(shared_metadata),
                "contract_version": "1.0.0",
                "dependencies": dict(shared_dependencies),
                "lifecycle": "stable",
                "error_codes": ["VALIDATION_ERROR"],
                "artifact_types": [],
                "redaction": dict(shared_redaction),
                "resources": {"max_runtime_sec": 30, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "user_function_body": (
                    f'return {{"ok": True, "version": "{version}", "value": params.get("value")}}'
                ),
            },
            {
                "tool_name": f"{module_name}.sleep",
                "method_name": "sleep_tool",
                "description": "Sleep for a requested time to exercise disconnect/timeout flows.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "delay_sec": {"type": "integer", "minimum": 1, "maximum": 300},
                    },
                    "required": ["delay_sec"],
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "version": {"type": "string"},
                        "delay_sec": {"type": "integer"},
                    },
                },
                "metadata": dict(shared_metadata),
                "contract_version": "1.0.0",
                "dependencies": dict(shared_dependencies),
                "lifecycle": "stable",
                "error_codes": ["VALIDATION_ERROR"],
                "artifact_types": [],
                "redaction": dict(shared_redaction),
                "resources": {"max_runtime_sec": 300, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "user_function_body": textwrap.dedent(
                    f"""
                    import asyncio

                    delay_sec = int(params.get("delay_sec", 1))
                    await asyncio.sleep(delay_sec)
                    return {{"ok": True, "version": "{version}", "delay_sec": delay_sec}}
                    """
                ).strip(),
            },
            {
                "tool_name": f"{module_name}.consent_probe",
                "method_name": "consent_probe_tool",
                "description": "Simple consent-gated tool for approve/deny/timeout canaries.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "version": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
                "metadata": {
                    **dict(shared_metadata),
                    "risk_level": "sensitive_read",
                    "requires_consent": True,
                },
                "contract_version": "1.0.0",
                "dependencies": dict(shared_dependencies),
                "lifecycle": "stable",
                "error_codes": ["VALIDATION_ERROR"],
                "artifact_types": [],
                "redaction": dict(shared_redaction),
                "resources": {"max_runtime_sec": 30, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "user_function_body": (
                    f'return {{"ok": True, "version": "{version}", "label": params.get("label", "consent")}}'
                ),
            },
        ],
    }


def read_local_agent_version() -> str:
    version_py = (WORKSPACE / "pc_agent" / "version.py").read_text(encoding="utf-8")
    marker = 'AGENT_VERSION = "'
    start = version_py.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = version_py.find('"', start)
    return version_py[start:end] if end > start else ""


def parse_csv_items(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def parse_expected_agent_versions_by_target(raw: str | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in parse_csv_items(raw):
        if "=" not in item:
            raise ValueError(
                "Expected target-specific agent versions as TARGET=VERSION pairs, "
                f"got {item!r}"
            )
        target, version = (part.strip() for part in item.split("=", 1))
        if not target or not version:
            raise ValueError(
                "Expected target-specific agent versions as non-empty TARGET=VERSION pairs, "
                f"got {item!r}"
            )
        mapping[target] = version
    return mapping


def resolve_agent_build_expectations(
    *,
    expected_agent_version: str | None,
    expected_agent_version_by_target: str | None,
) -> dict[str, str]:
    expected = parse_expected_agent_versions_by_target(expected_agent_version_by_target)
    local_windows_version = str(expected_agent_version or "").strip()
    if local_windows_version:
        expected.setdefault("windows_amd64", local_windows_version)
    return expected


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "ApiClient":
        timeout = aiohttp.ClientTimeout(total=120)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("ApiClient session is not open")
        return self._session

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        expected_statuses: tuple[int, ...] = (200,),
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with self.session.request(method.upper(), url, headers=headers, json=json_body) as response:
            raw = await response.text()
            payload = json.loads(raw) if raw else {}
            if response.status not in expected_statuses:
                raise RuntimeError(
                    f"{method.upper()} {path} -> HTTP {response.status}\n{_json_dump(payload)}"
                )
            if not isinstance(payload, dict):
                raise RuntimeError(f"{method.upper()} {path} returned non-object payload")
            return response.status, payload

    async def login_ui(self, login: str, password: str, *, expected_role: str | None = None) -> str:
        body: dict[str, Any] = {"login": login, "password": password}
        if expected_role:
            body["expected_role"] = expected_role
        _, payload = await self.request_json(
            "POST",
            "/api/ui_login",
            json_body=body,
            expected_statuses=(200,),
        )
        token = str(payload.get("token") or "").strip()
        if not token:
            raise RuntimeError(f"UI login did not return token for {login}")
        return token

    async def issue_agent_token(self, device_id: str) -> str:
        _, payload = await self.request_json(
            "POST",
            "/api/login",
            json_body={"uuid": device_id},
            expected_statuses=(200,),
        )
        token = str(payload.get("token") or "").strip()
        if not token:
            raise RuntimeError(f"API login did not return agent token for {device_id}")
        return token


async def wait_until(
    predicate,
    *,
    timeout_sec: float,
    interval_sec: float = 1.0,
    description: str,
):
    started = asyncio.get_running_loop().time()
    last_error: Exception | None = None
    while (asyncio.get_running_loop().time() - started) < timeout_sec:
        try:
            value = await predicate()
        except Exception as exc:  # pragma: no cover - live polling helper
            last_error = exc
        else:
            if value:
                return value
        await asyncio.sleep(interval_sec)
    if last_error is not None:
        raise RuntimeError(f"Timed out waiting for {description}: {last_error}") from last_error
    raise RuntimeError(f"Timed out waiting for {description}")


def instance_file(name: str) -> Path:
    return INSTANCE_ROOT / name / "instance.json"


def load_instance(name: str) -> dict[str, Any]:
    path = instance_file(name)
    if not path.exists():
        raise RuntimeError(f"Local agent instance file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_subprocess(command: list[str], cwd: Path = WORKSPACE, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def build_local_agent_start_command(name: str, *, ui_port: int, ws_url: str, api_url: str) -> list[str]:
    return [
        sys.executable,
        str(WORKSPACE / "scripts" / "manage_local_agent.py"),
        "start",
        name,
        "--launcher",
        "--issue-token",
        "--ui-port",
        str(ui_port),
        "--ws-url",
        ws_url,
        "--api-url",
        api_url,
    ]


def build_local_agent_stop_command(name: str) -> list[str]:
    return [
        sys.executable,
        str(WORKSPACE / "scripts" / "manage_local_agent.py"),
        "stop",
        name,
    ]


def build_remote_python_command(*, remote: str, code: str) -> tuple[list[str], str]:
    command = ["ssh"]
    if DEFAULT_KEY.exists():
        command.extend(["-i", str(DEFAULT_KEY)])
    command.extend([remote, build_remote_python_shell()])
    return command, code


def remote_force_operation_timeout_code(operation_id: str, *, mode: str) -> str:
    timeout_seconds = 1900 if mode == "consent" else 240
    return textwrap.dedent(
        f"""
        import asyncio
        from datetime import datetime, timezone, timedelta
        from dotenv import load_dotenv
        from app.db import get_session, init_db
        from app.db.models import Operation

        async def main() -> None:
            load_dotenv(".env")
            await init_db()
            async with get_session() as session:
                operation = await session.get(Operation, {operation_id!r})
                if operation is None:
                    raise SystemExit("operation not found")
                operation.started_at = datetime.now(timezone.utc) - timedelta(seconds={timeout_seconds})
                operation.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=5)
                await session.commit()
                print(operation.operation_id)

        asyncio.run(main())
        """
    ).strip()


def remote_inject_retry_exhausted_code(device_id: str) -> str:
    return textwrap.dedent(
        f"""
        import asyncio
        import json
        import uuid
        from dotenv import load_dotenv
        from app.db import get_session, init_db
        from app.repos.device_outbox_repo import DeviceOutboxRepo
        from app.services.operation_service import OperationService
        from websocket.device_outbox_sender import _sync_operation_delivery_state

        class _StateStub:
            ui_publisher = None

        async def main() -> None:
            load_dotenv(".env")
            await init_db()
            operation_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            async with get_session() as session:
                op_service = OperationService(session, publisher=None)
                await op_service.enqueue_operation(
                    operation_id=operation_id,
                    device_id={device_id!r},
                    kind="tool_call",
                    tool_name="observer.canary.retry",
                    actor_role="admin",
                    trace_id=trace_id,
                    max_retries=1,
                )
                repo = DeviceOutboxRepo(session)
                outbox_id = await repo.enqueue_command(
                    device_id={device_id!r},
                    command_id=operation_id,
                    command="run_tool",
                    params={{"tool_name": "observer.canary.retry"}},
                    trace_id=trace_id,
                    actor_role="admin",
                    max_retries=1,
                    operation_id=operation_id,
                )
                await repo.mark_as_failed(
                    outbox_id=outbox_id,
                    error_code="SEND_ERROR",
                    error_message="observer canary retry 1",
                    should_retry=True,
                )
                first = await repo.get_by_id(outbox_id)
                await _sync_operation_delivery_state(
                    state_manager=_StateStub(),
                    repo=repo,
                    outbox_entry=first,
                    error_code="SEND_ERROR",
                    error_message="observer canary retry 1",
                )
                await session.commit()
            async with get_session() as session:
                repo = DeviceOutboxRepo(session)
                await repo.mark_as_failed(
                    outbox_id=outbox_id,
                    error_code="SEND_ERROR",
                    error_message="observer canary retry exhausted",
                    should_retry=True,
                )
                second = await repo.get_by_id(outbox_id)
                await _sync_operation_delivery_state(
                    state_manager=_StateStub(),
                    repo=repo,
                    outbox_entry=second,
                    error_code="SEND_ERROR",
                    error_message="observer canary retry exhausted",
                )
                await session.commit()
            print(json.dumps({{"operation_id": operation_id, "trace_id": trace_id}}, ensure_ascii=False))

        asyncio.run(main())
        """
    ).strip()


def remote_create_waiting_consent_operation_code(*, device_id: str, ticket_id: str, tool_name: str) -> str:
    return textwrap.dedent(
        f"""
        import asyncio
        import json
        import uuid
        from dotenv import load_dotenv
        from app.db import get_session, init_db
        from app.services.operation_service import OperationService
        from app.repos.ticket_events_repo import TicketEventsRepo

        async def main() -> None:
            load_dotenv(".env")
            await init_db()
            operation_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            async with get_session() as session:
                op_service = OperationService(session, publisher=None)
                await op_service.enqueue_operation(
                    operation_id=operation_id,
                    device_id={device_id!r},
                    ticket_id={ticket_id!r},
                    kind="tool_call",
                    tool_name={tool_name!r},
                    actor_role="support",
                    trace_id=trace_id,
                    initial_status="waiting_consent",
                )
                events_repo = TicketEventsRepo(session)
                await events_repo.add_event(
                    ticket_id={ticket_id!r},
                    device_id={device_id!r},
                    agent_seq=None,
                    event_type="tool_call_started",
                    payload={{
                        "tool_name": {tool_name!r},
                        "params": {{}},
                        "call_id": operation_id,
                    }},
                    trace_id=trace_id,
                    operation_id=operation_id,
                )
                await session.commit()
            print(json.dumps({{"operation_id": operation_id, "trace_id": trace_id}}, ensure_ascii=False))

        asyncio.run(main())
        """
    ).strip()


def remote_trigger_ws_rate_limit_code(
    *,
    device_id: str,
    agent_token: str,
    ticket_id: str,
    ws_url: str = "ws://127.0.0.1:8666/ws",
    burst_size: int = 600,
) -> str:
    return textwrap.dedent(
        f"""
        import asyncio
        import json
        import uuid

        import aiohttp

        async def main() -> None:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.ws_connect({ws_url!r}, timeout=20) as ws:
                    await ws.send_json(
                        {{
                            "type": "handshake",
                            "request_id": str(uuid.uuid4()),
                            "device_id": {device_id!r},
                            "protocol_version": "ws_ticket_v3",
                            "trace_id": str(uuid.uuid4()),
                            "token": {agent_token!r},
                            "meta": {{"actor_role": "agent", "capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]}},
                            "payload": {{
                                "device_id": {device_id!r},
                                "machine_id": {device_id!r},
                                "hostname": "observer-canary-rate-remote",
                                "agent_version": "3.1.19",
                                "os": "Windows",
                                "os_type": "windows",
                                "modules": [],
                                "modules_inventory": [],
                            }},
                        }}
                    )
                    while True:
                        message = await ws.receive(timeout=10)
                        if message.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(message.data)
                            if payload.get("type") == "handshake_ack":
                                break
                        elif message.type in {{aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}}:
                            raise RuntimeError(f"ws closed during handshake: {{message.type}}")

                    for index in range({burst_size}):
                        await ws.send_json(
                            {{
                                "type": "outbox_item",
                                "request_id": str(uuid.uuid4()),
                                "device_id": {device_id!r},
                                "protocol_version": "ws_ticket_v3",
                                "trace_id": str(uuid.uuid4()),
                                "ticket_id": {ticket_id!r},
                                "meta": {{"actor_role": "agent"}},
                                "payload": {{
                                    "outbox_id": f"observer-rate-remote-{{index}}",
                                    "item_type": "job_event",
                                    "agent_seq": 1000 + index,
                                    "event": {{
                                        "event": "chat_message",
                                        "from": "agent",
                                        "text": f"rate remote {{index}}",
                                        "ticket_id": {ticket_id!r},
                                    }},
                                }},
                            }}
                        )

                    observed = []
                    deadline = asyncio.get_running_loop().time() + 12.0
                    while asyncio.get_running_loop().time() < deadline:
                        try:
                            message = await ws.receive(timeout=1.0)
                        except TimeoutError:
                            continue
                        if message.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(message.data)
                            observed.append(payload)
                            if payload.get("type") == "outbox_nack":
                                print(json.dumps({{"nack": payload, "observed_tail": observed[-10:]}}, ensure_ascii=False))
                                return
                        elif message.type in {{aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}}:
                            break
                    print(json.dumps({{"nack": None, "observed_tail": observed[-10:]}}, ensure_ascii=False))

        asyncio.run(main())
        """
    ).strip()


def remote_seed_observer_source_coverage_code(device_id: str) -> str:
    return textwrap.dedent(
        f"""
        import asyncio
        import json
        import uuid
        from datetime import datetime, timezone, timedelta
        from types import SimpleNamespace

        from dotenv import load_dotenv
        from app.db import get_session, init_db
        from app.db.models import (
            AgentRuntimeAudit,
            Device,
            DeviceDesiredModule,
            Playbook,
            PlaybookRun,
            PlaybookStep,
            PlaybookStepRun,
            PlaybookVersion,
        )
        from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
        from modules.reconcile import reconcile_device
        from observer.service import ObserverOverlayService, TraceOverlayFilters, _playbook_run_trace_id, _runtime_audit_trace_id

        async def _project_runtime_audit(session, audit):
            service = ObserverOverlayService(session)
            trace_id = _runtime_audit_trace_id(audit.id)
            trace = await service.project_trace(trace_id, force=True)
            return trace.trace_id if trace else trace_id

        async def main() -> None:
            load_dotenv(".env")
            await init_db()
            device_id = {device_id!r}
            suffix = uuid.uuid4().hex[:8]
            now = datetime.now(timezone.utc)
            output = {{"expected_event_types": ["module_reconcile_failed", "web_auth_failed", "observer_runtime_degraded"]}}

            async with get_session() as session:
                device = await session.get(Device, device_id)
                if device is None:
                    session.add(
                        Device(
                            device_id=device_id,
                            protocol_version="ws_ticket_v3",
                            agent_version="observer-canary",
                            hostname="observer-canary-coverage",
                            os="Windows",
                            capabilities=[],
                            tools_version="observer-canary",
                            device_metadata={{}},
                            last_seen_at=now,
                            last_handshake_at=now,
                            first_seen_at=now,
                        )
                    )
                session.add(
                    DeviceDesiredModule(
                        device_id=device_id,
                        module_name=f"observer_canary_missing_{{suffix}}",
                        desired_version="9.9.9",
                        desired_sha256=None,
                        state="installed",
                        reason="observer_canary",
                        updated_by="observer_canary",
                    )
                )
                await session.commit()

            async with get_session() as session:
                await reconcile_device(device_id, state=SimpleNamespace(), session=session, reason="observer_canary")
                service = ObserverOverlayService(session)
                module_trace_ids = await service._candidate_trace_ids(
                    TraceOverlayFilters(root_kind="module_reconcile", device_id=device_id, query="observer_canary_missing"),
                    limit=5,
                )
                if module_trace_ids:
                    trace = await service.project_trace(module_trace_ids[0], force=True)
                    output["module_reconcile"] = {{"trace_id": trace.trace_id if trace else module_trace_ids[0]}}
                await session.commit()

            async with get_session() as session:
                playbook = Playbook(key=f"observer_canary_{{suffix}}", name="Observer canary coverage", domain="diagnostics")
                session.add(playbook)
                await session.flush()
                version = PlaybookVersion(playbook_id=playbook.id, version="1.0.0", status="published")
                session.add(version)
                await session.flush()
                skipped_step = PlaybookStep(
                    playbook_version_id=version.id,
                    step_key="branch",
                    order_no=1,
                    type="decision",
                )
                failed_step = PlaybookStep(
                    playbook_version_id=version.id,
                    step_key="install_missing_module",
                    order_no=2,
                    type="run_tool",
                    tool="missing.module_tool",
                )
                session.add_all([skipped_step, failed_step])
                await session.flush()
                run = PlaybookRun(
                    playbook_version_id=version.id,
                    device_id=device_id,
                    status="failed",
                    scheduled_at=now - timedelta(seconds=4),
                    started_at=now - timedelta(seconds=4),
                    finished_at=now,
                    trigger_type="observer_canary",
                    context_json={{"canary": "observer_coverage"}},
                    error_code="STEP_FAILED",
                    error_message="Canary playbook failed on missing module step",
                )
                session.add(run)
                await session.flush()
                session.add_all(
                    [
                        PlaybookStepRun(
                            playbook_run_id=run.id,
                            playbook_step_id=skipped_step.id,
                            attempt=1,
                            status="skipped",
                            started_at=now - timedelta(seconds=3),
                            finished_at=now - timedelta(seconds=3),
                            input_json={{"reason": "if_expr=false"}},
                        ),
                        PlaybookStepRun(
                            playbook_run_id=run.id,
                            playbook_step_id=failed_step.id,
                            attempt=1,
                            status="failed",
                            started_at=now - timedelta(seconds=2),
                            finished_at=now - timedelta(seconds=1),
                            input_json={{"target": "device"}},
                            error_json={{"code": "MODULE_PRECHECK_FAILED", "stage": "module_install"}},
                        ),
                    ]
                )
                await session.flush()
                trace_id = _playbook_run_trace_id(run.id)
                trace = await ObserverOverlayService(session).project_trace(trace_id, force=True)
                output["playbook_run"] = {{"trace_id": trace.trace_id if trace else trace_id, "playbook_run_id": run.id}}
                await session.commit()

            async with get_session() as session:
                audit_repo = AgentRuntimeAuditRepo(session)
                web_auth = await audit_repo.add(
                    device_id=device_id,
                    event_type="web_auth_failed",
                    severity="warning",
                    source="web_auth",
                    actor_role="anonymous",
                    details_json={{
                        "route": "/api/tickets",
                        "method": "GET",
                        "error_code": "AUTH_REQUIRED",
                        "canary": "observer_coverage",
                    }},
                )
                output["web_auth"] = {{"trace_id": await _project_runtime_audit(session, web_auth)}}
                observer_runtime = await audit_repo.add(
                    device_id="observer-runtime",
                    event_type="observer_runtime_degraded",
                    severity="warning",
                    source="observer_runtime",
                    actor_role="system",
                    details_json={{
                        "issues": ["observer_canary"],
                        "pending_trace_count": 1,
                        "last_error": None,
                        "canary": "observer_coverage",
                    }},
                )
                output["observer_runtime"] = {{"trace_id": await _project_runtime_audit(session, observer_runtime)}}
                diagnostic_runtime_audits = {{
                    "capability_run": await audit_repo.add(
                        device_id=device_id,
                        event_type="capability_run_succeeded",
                        severity="info",
                        source="diagnostic_capability",
                        actor_role="support",
                        details_json={{
                            "stage": "finished",
                            "capability_id": "diag.logs.collect",
                            "provider_id": "diag_logs",
                            "execution_target": "agent_builtin",
                            "metrics": {{
                                "duration_ms": 12,
                                "result_status": "success",
                                "readiness_failure_count": 0,
                                "provider_error_count": 0,
                                "evidence_linked_count": 0,
                            }},
                            "canary": "observer_coverage",
                        }},
                    ),
                    "server_connector_query": await audit_repo.add(
                        device_id="server",
                        event_type="capability_run_blocked",
                        severity="warning",
                        source="diagnostic_server_connector",
                        actor_role="support",
                        details_json={{
                            "stage": "finished",
                            "capability_id": "zabbix.problems.lookup",
                            "provider_id": "zabbix_connector",
                            "execution_target": "server_connector",
                            "readiness": {{"readiness": "integration_not_configured", "reason_code": "INTEGRATION_NOT_CONFIGURED"}},
                            "metrics": {{
                                "duration_ms": 3,
                                "result_status": "error",
                                "readiness_failure_count": 1,
                                "provider_error_count": 0,
                                "evidence_linked_count": 0,
                            }},
                            "canary": "observer_coverage",
                        }},
                    ),
                    "observer_query": await audit_repo.add(
                        device_id="server",
                        event_type="capability_run_succeeded",
                        severity="info",
                        source="diagnostic_observer_query",
                        actor_role="support",
                        details_json={{
                            "stage": "finished",
                            "capability_id": "observer.ticket.summary",
                            "provider_id": "observer",
                            "execution_target": "observer_query",
                            "metrics": {{
                                "duration_ms": 8,
                                "result_status": "success",
                                "readiness_failure_count": 0,
                                "provider_error_count": 0,
                                "evidence_linked_count": 1,
                            }},
                            "canary": "observer_coverage",
                        }},
                    ),
                    "manual_evidence": await audit_repo.add(
                        device_id="server",
                        event_type="capability_evidence_linked",
                        severity="info",
                        source="diagnostic_manual",
                        actor_role="support",
                        details_json={{
                            "stage": "evidence_linked",
                            "capability_id": "manual.visual_check",
                            "provider_id": "manual",
                            "execution_target": "manual",
                            "diagnostic_evidence_id": f"canary-manual-{{suffix}}",
                            "metrics": {{
                                "duration_ms": 0,
                                "result_status": "created",
                                "readiness_failure_count": 0,
                                "provider_error_count": 0,
                                "evidence_linked_count": 1,
                            }},
                            "canary": "observer_coverage",
                        }},
                    ),
                    "remote_assist": await audit_repo.add(
                        device_id=device_id,
                        event_type="capability_run_succeeded",
                        severity="info",
                        source="diagnostic_remote_assist",
                        actor_role="support",
                        details_json={{
                            "stage": "finished",
                            "capability_id": "remote_assist.session.summary",
                            "provider_id": "remote_assist",
                            "execution_target": "remote_assist",
                            "metrics": {{
                                "duration_ms": 6,
                                "result_status": "success",
                                "readiness_failure_count": 0,
                                "provider_error_count": 0,
                                "evidence_linked_count": 1,
                            }},
                            "canary": "observer_coverage",
                        }},
                    ),
                }}
                for root_kind, audit in diagnostic_runtime_audits.items():
                    output[root_kind] = {{"trace_id": await _project_runtime_audit(session, audit)}}
                await session.commit()

            print(json.dumps(output, ensure_ascii=False, sort_keys=True))

        asyncio.run(main())
        """
    ).strip()


async def ensure_support_user(
    api: ApiClient,
    *,
    admin_token: str,
    login: str,
    password: str,
) -> None:
    try:
        await api.request_json("POST", "/api/admin/users", token=admin_token, json_body={
            "login": login,
            "password": password,
            "actor_role": "support",
        }, expected_statuses=(201, 409))
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to ensure support user {login}: {exc}") from exc
    await api.request_json(
        "POST",
        f"/api/admin/users/{login}/password",
        token=admin_token,
        json_body={"password": password},
        expected_statuses=(200,),
    )
    await api.request_json(
        "PATCH",
        f"/api/admin/users/{login}",
        token=admin_token,
        json_body={"actor_role": "support", "is_active": True},
        expected_statuses=(200,),
    )


async def wait_device_online(api: ApiClient, *, admin_token: str, device_id: str, expected_online: bool, timeout_sec: float = 60.0) -> dict[str, Any]:
    async def _poll() -> dict[str, Any] | None:
        _, payload = await api.request_json("GET", "/api/devices", token=admin_token, expected_statuses=(200,))
        for item in payload.get("devices") or []:
            if item.get("device_id") == device_id and bool(item.get("online")) is expected_online:
                return item
        return None

    state = "online" if expected_online else "offline"
    return await wait_until(_poll, timeout_sec=timeout_sec, interval_sec=2.0, description=f"device {device_id} {state}")


async def create_ticket(api: ApiClient, *, token: str, device_id: str, title: str, description: str, user_display_name: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        "/api/tickets/create",
        token=token,
        json_body={
            "title": title,
            "description": description,
            "device_id": device_id,
            "user_display_name": user_display_name,
        },
        expected_statuses=(200,),
    )
    ticket = payload.get("ticket") or {}
    if not ticket.get("ticket_id"):
        raise RuntimeError(f"Ticket create did not return ticket_id: {_json_dump(payload)}")
    return ticket


async def send_ticket_message(api: ApiClient, *, token: str, ticket_id: str, text: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        f"/api/tickets/{ticket_id}/message",
        token=token,
        json_body={"message_id": str(uuid.uuid4()), "text": text},
        expected_statuses=(200,),
    )
    return payload


async def run_ticket_tool(
    api: ApiClient,
    *,
    token: str,
    device_id: str,
    ticket_id: str,
    tool_name: str,
    params: dict[str, Any],
    wait_for_result: bool = False,
) -> dict[str, Any]:
    wait_suffix = "?wait=1" if wait_for_result else ""
    _, payload = await api.request_json(
        "POST",
        f"/api/tools/run{wait_suffix}",
        token=token,
        json_body={
            "device_id": device_id,
            "ticket_id": ticket_id,
            "tool_name": tool_name,
            "params": params,
        },
        expected_statuses=(200, 202),
    )
    return payload


async def get_operation(api: ApiClient, *, admin_token: str, operation_id: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "GET",
        f"/api/operations/{operation_id}",
        token=admin_token,
        expected_statuses=(200,),
    )
    operation = payload.get("operation") or {}
    if not operation.get("operation_id"):
        raise RuntimeError(f"Operation payload missing operation_id: {_json_dump(payload)}")
    return operation


async def wait_operation_status(
    api: ApiClient,
    *,
    admin_token: str,
    operation_id: str,
    statuses: set[str],
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    async def _poll() -> dict[str, Any] | None:
        operation = await get_operation(api, admin_token=admin_token, operation_id=operation_id)
        if str(operation.get("status") or "") in statuses:
            return operation
        return None

    return await wait_until(_poll, timeout_sec=timeout_sec, interval_sec=2.0, description=f"operation {operation_id} statuses={sorted(statuses)}")


async def approve_consent(api: ApiClient, *, token: str, operation_id: str, reason: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        f"/api/operations/{operation_id}/approve",
        token=token,
        json_body={"reason": reason},
        expected_statuses=(200,),
    )
    return payload


async def deny_consent(api: ApiClient, *, token: str, operation_id: str, reason: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        f"/api/operations/{operation_id}/deny",
        token=token,
        json_body={"reason": reason},
        expected_statuses=(200,),
    )
    return payload


async def save_module_version(api: ApiClient, *, admin_token: str, module_name: str, version: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        "/api/modules/workbench/save",
        token=admin_token,
        json_body=build_canary_module_payload(module_name, version),
        expected_statuses=(200,),
    )
    return payload


async def module_action(
    api: ApiClient,
    *,
    admin_token: str,
    device_id: str,
    action: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    _, payload = await api.request_json(
        "POST",
        f"/api/devices/{device_id}/modules/{action}",
        token=admin_token,
        json_body=body,
        expected_statuses=(200, 202),
    )
    return payload


async def search_trace_by_operation(api: ApiClient, *, admin_token: str, operation_id: str) -> dict[str, Any]:
    _, payload = await api.request_json(
        "GET",
        f"/api/admin/tech/traces?operation_id={operation_id}",
        token=admin_token,
        expected_statuses=(200,),
    )
    return payload


async def wait_trace_for_operation(api: ApiClient, *, admin_token: str, operation_id: str, timeout_sec: float = 90.0) -> dict[str, Any]:
    async def _poll() -> dict[str, Any] | None:
        operation = await get_operation(api, admin_token=admin_token, operation_id=operation_id)
        trace_id = str(operation.get("trace_id") or "").strip()
        if not trace_id:
            return None
        payload = await api.request_json(
            "GET",
            f"/api/admin/tech/traces?trace_id={trace_id}",
            token=admin_token,
            expected_statuses=(200,),
        )
        payload = payload[1]
        traces = payload.get("traces") or []
        if traces:
            return traces[0]
        return None

    return await wait_until(_poll, timeout_sec=timeout_sec, interval_sec=3.0, description=f"trace for operation {operation_id}")


async def get_trace_detail(api: ApiClient, *, admin_token: str, trace_id: str, include_agent_actions: bool = False) -> dict[str, Any]:
    suffix = "?include_agent_actions=1" if include_agent_actions else ""
    _, payload = await api.request_json(
        "GET",
        f"/api/admin/tech/traces/{trace_id}{suffix}",
        token=admin_token,
        expected_statuses=(200,),
    )
    return payload


async def search_observer_traces(
    api: ApiClient,
    *,
    admin_token: str,
    trace_id: str | None = None,
    root_kind: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    params = {"limit": str(limit)}
    if trace_id:
        params["trace_id"] = trace_id
    if root_kind:
        params["root_kind"] = root_kind
    if query:
        params["q"] = query
    _, payload = await api.request_json(
        "GET",
        f"/api/admin/tech/traces?{urlencode(params)}",
        token=admin_token,
        expected_statuses=(200,),
    )
    return payload


async def scenario_observer_source_coverage(
    api: ApiClient,
    *,
    admin_token: str,
    device_id: str,
    remote: str,
) -> list[ScenarioResult]:
    raw = await run_remote_python(remote=remote, code=remote_seed_observer_source_coverage_code(device_id))
    payload = json.loads(raw.splitlines()[-1])
    results: list[ScenarioResult] = []
    for root_kind in SOURCE_COVERAGE_ROOT_KINDS:
        item = payload.get(root_kind) if isinstance(payload, dict) else None
        trace_id = str((item or {}).get("trace_id") or "").strip()
        if not trace_id:
            results.append(
                ScenarioResult(
                    name=f"coverage_{root_kind}",
                    ok=False,
                    summary=f"Coverage source probe did not return a trace for {root_kind}.",
                    details={"root_kind": root_kind},
                )
            )
            continue
        detail = await get_trace_detail(api, admin_token=admin_token, trace_id=trace_id, include_agent_actions=True)
        trace = detail.get("trace") if isinstance(detail.get("trace"), dict) else {}
        spans = detail.get("spans") if isinstance(detail.get("spans"), list) else []
        errors = detail.get("error_occurrences") if isinstance(detail.get("error_occurrences"), list) else []
        actual_root_kind = str(trace.get("root_kind") or "")
        results.append(
            ScenarioResult(
                name=f"coverage_{root_kind}",
                ok=actual_root_kind == root_kind and bool(spans),
                summary=f"Seeded {root_kind} source row and verified observer trace detail.",
                details={
                    "root_kind": root_kind,
                    "trace_id": trace_id,
                    "actual_root_kind": actual_root_kind,
                    "span_count": len(spans),
                    "error_count": len(errors),
                    **({"playbook_run_id": item.get("playbook_run_id")} if isinstance(item, dict) and item.get("playbook_run_id") else {}),
                },
            )
        )
    return results


async def scenario_agent_build_registry(
    api: ApiClient,
    *,
    admin_token: str,
    expected_versions_by_target: dict[str, str],
    targets: tuple[str, ...] = DEFAULT_AGENT_BUILD_TARGETS,
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for target in targets:
        _, payload = await api.request_json(
            "GET",
            f"/api/agent_builds?{urlencode({'target': target, 'channel': 'stable', 'limit': '10'})}",
            token=admin_token,
            expected_statuses=(200,),
        )
        builds = payload.get("builds") if isinstance(payload.get("builds"), list) else []
        target_builds = [build for build in builds if str(build.get("target") or "") == target]
        expected_version = str(expected_versions_by_target.get(target) or "").strip()
        if expected_version:
            match = next(
                (
                    build
                    for build in target_builds
                    if str(build.get("version") or "") == expected_version
                ),
                None,
            )
            ok = bool(match)
            summary = f"Stable agent build registry contains {expected_version} for {target}."
        else:
            match = target_builds[0] if target_builds else None
            ok = bool(match)
            summary = f"Stable agent build registry contains at least one build for {target}."
        results.append(
            ScenarioResult(
                name=f"agent_build_registry_{target}",
                ok=ok,
                summary=summary,
                details={
                    "target": target,
                    "root_kind": "agent_update",
                    "expected_version": expected_version or None,
                    "available_versions": [str(build.get("version") or "") for build in target_builds],
                    "sha256": match.get("sha256") if match else None,
                    "download_path": match.get("download_path") if match else None,
                },
            )
        )
    return results


async def ws_expect_messages(
    ws: aiohttp.ClientWebSocketResponse,
    *,
    expected_types: set[str],
    limit: int = 100,
    timeout_sec: float = 10.0,
    allow_timeout: bool = False,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    async def _read() -> list[dict[str, Any]] | None:
        try:
            while len(messages) < limit:
                msg = await ws.receive(timeout=timeout_sec)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(msg.data)
                    messages.append(payload)
                    if payload.get("type") in expected_types:
                        return messages
                elif msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                    raise RuntimeError(f"WebSocket closed while waiting for {expected_types}: {msg.type}")
        except TimeoutError:
            if allow_timeout:
                return messages
            raise
        return messages
    return await _read() or messages


async def ws_collect_until_types(
    ws: aiohttp.ClientWebSocketResponse,
    *,
    required_types: set[str],
    limit: int = 100,
    timeout_sec: float = 10.0,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(messages) < limit and not required_types.issubset(seen):
        msg = await ws.receive(timeout=timeout_sec)
        if msg.type == aiohttp.WSMsgType.TEXT:
            payload = json.loads(msg.data)
            messages.append(payload)
            message_type = str(payload.get("type") or "")
            if message_type:
                seen.add(message_type)
        elif msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
            raise RuntimeError(f"WebSocket closed while waiting for {required_types}: {msg.type}")
    return messages


async def run_remote_python(*, remote: str, code: str) -> str:
    command, input_text = build_remote_python_command(remote=remote, code=code)
    completed = await asyncio.to_thread(run_subprocess, command, WORKSPACE, input_text)
    return completed.stdout.strip()


async def scenario_consent(
    api: ApiClient,
    *,
    admin_token: str,
    support_token: str,
    device_id: str,
    remote: str,
    tool_name: str,
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    params = {"label": "observer-consent"}

    ticket = await create_ticket(
        api,
        token=support_token,
        device_id=device_id,
        title="Observer canary consent flows",
        description="Consent canary baseline",
        user_display_name="Observer Canary",
    )
    ticket_id = str(ticket["ticket_id"])

    approve_payload = await run_ticket_tool(
        api,
        token=support_token,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=tool_name,
        params=params,
    )
    approve_operation_id = str(approve_payload.get("operation_id") or "")
    approve_precheck_operation = await get_operation(api, admin_token=admin_token, operation_id=approve_operation_id)
    use_remote_consent_seed = str(approve_precheck_operation.get("status") or "") != "waiting_consent"
    if use_remote_consent_seed:
        results.append(
            ScenarioResult(
                name="consent_waiting_consent_precheck",
                ok=False,
                summary="Support run_tool for a consent-gated managed-module tool did not stop in waiting_consent.",
                details={
                    "ticket_id": ticket_id,
                    "tool_name": tool_name,
                    "operation_id": approve_operation_id,
                    "status": approve_precheck_operation.get("status"),
                    "trace_id": approve_precheck_operation.get("trace_id"),
                    "root_kind": "consent",
                },
            )
        )
        raw = await run_remote_python(
            remote=remote,
            code=remote_create_waiting_consent_operation_code(
                device_id=device_id,
                ticket_id=ticket_id,
                tool_name=tool_name,
            ),
        )
        approve_seed = json.loads(raw.splitlines()[-1])
        approve_operation_id = str(approve_seed["operation_id"])
    await approve_consent(api, token=admin_token, operation_id=approve_operation_id, reason="observer canary approve")
    approve_operation = await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=approve_operation_id,
        statuses={"succeeded"},
        timeout_sec=180.0,
    )
    approve_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=approve_operation_id)
    results.append(
        ScenarioResult(
            name="consent_approve",
            ok=True,
            summary="Support-triggered consent flow reached succeeded after explicit approve.",
            details={
                "ticket_id": ticket_id,
                "operation_id": approve_operation_id,
                "trace_id": approve_trace["trace_id"],
                "root_kind": "consent",
                "status": approve_operation["status"],
            },
        )
    )

    deny_operation_id = ""
    if use_remote_consent_seed:
        raw = await run_remote_python(
            remote=remote,
            code=remote_create_waiting_consent_operation_code(
                device_id=device_id,
                ticket_id=ticket_id,
                tool_name=tool_name,
            ),
        )
        deny_seed = json.loads(raw.splitlines()[-1])
        deny_operation_id = str(deny_seed["operation_id"])
    else:
        deny_payload = await run_ticket_tool(
            api,
            token=support_token,
            device_id=device_id,
            ticket_id=ticket_id,
            tool_name=tool_name,
            params=params,
        )
        deny_operation_id = str(deny_payload.get("operation_id") or "")
    await deny_consent(api, token=admin_token, operation_id=deny_operation_id, reason="observer canary deny")
    deny_operation = await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=deny_operation_id,
        statuses={"denied"},
        timeout_sec=30.0,
    )
    deny_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=deny_operation_id)
    results.append(
        ScenarioResult(
            name="consent_deny",
            ok=True,
            summary="Support-triggered consent flow reached denied after explicit deny.",
            details={
                "ticket_id": ticket_id,
                "operation_id": deny_operation_id,
                "trace_id": deny_trace["trace_id"],
                "root_kind": "consent",
                "status": deny_operation["status"],
            },
        )
    )

    timeout_operation_id = ""
    if use_remote_consent_seed:
        raw = await run_remote_python(
            remote=remote,
            code=remote_create_waiting_consent_operation_code(
                device_id=device_id,
                ticket_id=ticket_id,
                tool_name=tool_name,
            ),
        )
        timeout_seed = json.loads(raw.splitlines()[-1])
        timeout_operation_id = str(timeout_seed["operation_id"])
    else:
        timeout_payload = await run_ticket_tool(
            api,
            token=support_token,
            device_id=device_id,
            ticket_id=ticket_id,
            tool_name=tool_name,
            params=params,
        )
        timeout_operation_id = str(timeout_payload.get("operation_id") or "")
    await run_remote_python(remote=remote, code=remote_force_operation_timeout_code(timeout_operation_id, mode="consent"))
    timeout_operation = await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=timeout_operation_id,
        statuses={"timed_out"},
        timeout_sec=75.0,
    )
    timeout_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=timeout_operation_id)
    results.append(
        ScenarioResult(
            name="consent_timeout",
            ok=True,
            summary="Consent timeout was forced through deadline backdating and observed by the running watchdog.",
            details={
                "ticket_id": ticket_id,
                "operation_id": timeout_operation_id,
                "trace_id": timeout_trace["trace_id"],
                "root_kind": "consent",
                "status": timeout_operation["status"],
                "error_code": timeout_operation.get("error_code"),
            },
        )
    )
    return results


async def scenario_module_lifecycle(
    api: ApiClient,
    *,
    admin_token: str,
    support_token: str,
    device_id: str,
) -> tuple[list[ScenarioResult], str]:
    results: list[ScenarioResult] = []
    module_name = f"observer_canary_{uuid.uuid4().hex[:8]}"
    await save_module_version(api, admin_token=admin_token, module_name=module_name, version="1.0.0")

    install_v1 = await module_action(
        api,
        admin_token=admin_token,
        device_id=device_id,
        action="install",
        body={"module_name": module_name, "version": "1.0.0"},
    )
    install_v1_operation_id = str(install_v1.get("operation_id") or "")
    await wait_operation_status(api, admin_token=admin_token, operation_id=install_v1_operation_id, statuses={"succeeded"}, timeout_sec=180.0)
    install_v1_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=install_v1_operation_id)
    await module_action(api, admin_token=admin_token, device_id=device_id, action="activate", body={"module_name": module_name, "version": "1.0.0"})
    await module_action(api, admin_token=admin_token, device_id=device_id, action="sync", body={})
    ticket = await create_ticket(
        api,
        token=support_token,
        device_id=device_id,
        title="Observer canary module lifecycle",
        description="Module install/update/remove canary",
        user_display_name="Observer Canary",
    )
    ticket_id = str(ticket["ticket_id"])
    echo_v1 = await run_ticket_tool(
        api,
        token=support_token,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=f"{module_name}.echo",
        params={"value": "v1"},
        wait_for_result=True,
    )
    results.append(
        ScenarioResult(
            name="module_install",
            ok=extract_tool_result_version(echo_v1.get("result")) == "1.0.0",
            summary="Installed and activated canary module version 1.0.0, then executed its tool through support API.",
            details={
                "module_name": module_name,
                "install_operation_id": install_v1_operation_id,
                "trace_id": install_v1_trace["trace_id"],
                "root_kind": "module_install",
                "ticket_id": ticket_id,
                "observed_version": extract_tool_result_version(echo_v1.get("result")),
                "tool_result": echo_v1.get("result"),
            },
        )
    )

    await save_module_version(api, admin_token=admin_token, module_name=module_name, version="1.1.0")
    install_v2 = await module_action(
        api,
        admin_token=admin_token,
        device_id=device_id,
        action="install",
        body={"module_name": module_name, "version": "1.1.0", "replace_if_exists": True},
    )
    install_v2_operation_id = str(install_v2.get("operation_id") or "")
    await wait_operation_status(api, admin_token=admin_token, operation_id=install_v2_operation_id, statuses={"succeeded"}, timeout_sec=180.0)
    install_v2_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=install_v2_operation_id)
    activate_v2 = await module_action(
        api,
        admin_token=admin_token,
        device_id=device_id,
        action="activate",
        body={"module_name": module_name, "version": "1.1.0"},
    )
    activate_v2_operation_id = str(activate_v2.get("operation_id") or "")
    await wait_operation_status(api, admin_token=admin_token, operation_id=activate_v2_operation_id, statuses={"succeeded"}, timeout_sec=120.0)
    activate_v2_trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=activate_v2_operation_id)
    await module_action(api, admin_token=admin_token, device_id=device_id, action="sync", body={})
    echo_v2 = await run_ticket_tool(
        api,
        token=support_token,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=f"{module_name}.echo",
        params={"value": "v2"},
        wait_for_result=True,
    )
    results.append(
        ScenarioResult(
            name="module_update",
            ok=extract_tool_result_version(echo_v2.get("result")) == "1.1.0",
            summary="Installed and activated module version 1.1.0, then verified that support tool execution uses the new version.",
            details={
                "module_name": module_name,
                "install_operation_id": install_v2_operation_id,
                "install_trace_id": install_v2_trace["trace_id"],
                "trace_id": install_v2_trace["trace_id"],
                "root_kind": "module_update",
                "activate_operation_id": activate_v2_operation_id,
                "activate_trace_id": activate_v2_trace["trace_id"],
                "observed_version": extract_tool_result_version(echo_v2.get("result")),
                "tool_result": echo_v2.get("result"),
            },
        )
    )

    remove_version = await module_action(
        api,
        admin_token=admin_token,
        device_id=device_id,
        action="remove_version",
        body={"module_name": module_name, "version": "1.0.0", "force": True},
    )
    remove_version_operation_id = str(remove_version.get("operation_id") or "")
    await wait_operation_status(api, admin_token=admin_token, operation_id=remove_version_operation_id, statuses={"succeeded"}, timeout_sec=120.0)
    remove_version_trace = await wait_trace_for_operation(
        api,
        admin_token=admin_token,
        operation_id=remove_version_operation_id,
    )

    results.append(
        ScenarioResult(
            name="module_remove_version",
            ok=True,
            summary="Removed the superseded module version 1.0.0 after upgrade.",
            details={
                "module_name": module_name,
                "operation_id": remove_version_operation_id,
                "trace_id": remove_version_trace["trace_id"],
                "root_kind": "module_remove",
            },
        )
    )
    return results, module_name


async def scenario_retry_exhausted(api: ApiClient, *, admin_token: str, device_id: str, remote: str) -> ScenarioResult:
    raw = await run_remote_python(remote=remote, code=remote_inject_retry_exhausted_code(device_id))
    payload = json.loads(raw.splitlines()[-1])
    operation_id = str(payload["operation_id"])
    operation = await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=operation_id,
        statuses={"failed"},
        timeout_sec=30.0,
    )
    trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=operation_id)
    detail = await get_trace_detail(api, admin_token=admin_token, trace_id=str(trace["trace_id"]))
    return ScenarioResult(
        name="retry_exhausted",
        ok=operation.get("error_code") == "DELIVERY_RETRY_EXHAUSTED",
        summary="Controlled delivery retry exhaustion is projected into operations and observer traces.",
        details={
            "operation_id": operation_id,
            "trace_id": trace["trace_id"],
            "root_kind": "retry_exhausted",
            "status": operation.get("status"),
            "error_code": operation.get("error_code"),
            "spans_count": len(detail.get("spans") or []),
        },
    )


async def scenario_ws_ack_nack_replay(
    api: ApiClient,
    *,
    admin_token: str,
    support_token: str,
    ws_url: str,
    ui_ws_url: str,
    remote: str,
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    device_id = str(uuid.uuid4())
    agent_token = await api.issue_agent_token(device_id)
    ticket_id = ""
    try:
        async with api.session.ws_connect(ws_url, timeout=20) as ws:
            handshake = {
                "type": "handshake",
                "request_id": str(uuid.uuid4()),
                "device_id": device_id,
                "protocol_version": "ws_ticket_v3",
                "trace_id": str(uuid.uuid4()),
                "token": agent_token,
                "meta": {"actor_role": "agent", "capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
                "payload": {
                    "device_id": device_id,
                    "machine_id": device_id,
                    "hostname": "observer-canary-ws",
                    "agent_version": "3.1.19",
                    "os": "Windows",
                    "os_type": "windows",
                    "modules": [],
                    "modules_inventory": [],
                },
            }
            await ws.send_json(handshake)
            handshake_messages = await ws_expect_messages(ws, expected_types={"handshake_ack"})
            assert any(item.get("type") == "handshake_ack" for item in handshake_messages)
            ticket = await create_ticket(
                api,
                token=support_token,
                device_id=device_id,
                title="Observer canary WS flows",
                description="WS ack/nack/replay canary",
                user_display_name="Observer Canary",
            )
            ticket_id = str(ticket["ticket_id"])

            unauthorized_trace_id = str(uuid.uuid4())
            await ws.send_json(
                {
                    "type": "outbox_item",
                    "request_id": str(uuid.uuid4()),
                    "device_id": device_id,
                    "protocol_version": "ws_ticket_v3",
                    "trace_id": unauthorized_trace_id,
                    "ticket_id": ticket_id,
                    "meta": {"actor_role": "user"},
                    "payload": {
                        "outbox_id": "observer-unauthorized-1",
                        "item_type": "job_event",
                        "agent_seq": 1,
                        "event": {"event": "chat_message", "from": "user", "text": "unauthorized"},
                    },
                }
            )
            unauthorized_messages = await ws_expect_messages(ws, expected_types={"outbox_nack"})
            unauthorized_nack = next(item for item in reversed(unauthorized_messages) if item.get("type") == "outbox_nack")
            results.append(
                ScenarioResult(
                    name="ws_unauthorized_nack",
                    ok=(unauthorized_nack.get("payload", {}).get("error", {}) or {}).get("code") == "UNAUTHORIZED",
                    summary="Post-handshake unauthorized outbox_item was rejected with typed outbox_nack.",
                    details={
                        "trace_id": unauthorized_nack.get("trace_id"),
                        "root_kind": "ws_delivery",
                        "payload": unauthorized_nack.get("payload"),
                    },
                )
            )

            duplicate_trace_id = str(uuid.uuid4())
            duplicate_message = build_ws_chat_outbox_item(
                device_id=device_id,
                ticket_id=ticket_id,
                outbox_id="observer-duplicate-1",
                agent_seq=2,
                trace_id=duplicate_trace_id,
                text="duplicate",
            )
            await ws.send_json(duplicate_message)
            ack_messages = await ws_expect_messages(
                ws,
                expected_types={"outbox_ack", "outbox_nack"},
                allow_timeout=True,
            )
            first_ack = find_ws_message(ack_messages, "outbox_ack")
            first_nack = find_ws_message(ack_messages, "outbox_nack")
            await ws.send_json(duplicate_message)
            duplicate_ack_messages = await ws_expect_messages(
                ws,
                expected_types={"outbox_ack", "outbox_nack"},
                allow_timeout=True,
            )
            duplicate_ack = find_ws_message(duplicate_ack_messages, "outbox_ack")
            duplicate_nack = find_ws_message(duplicate_ack_messages, "outbox_nack")
            results.append(
                ScenarioResult(
                    name="ws_duplicate_ack",
                    ok=(
                        first_ack is not None
                        and duplicate_ack is not None
                        and "observer-duplicate-1" in first_ack.get("payload", {}).get("outbox_ids", [])
                        and "observer-duplicate-1" in duplicate_ack.get("payload", {}).get("outbox_ids", [])
                    ),
                    summary="Duplicate outbox_item received direct ACK on replayed outbox_id.",
                    details={
                        "trace_id": duplicate_trace_id,
                        "root_kind": "ws_delivery",
                        "first_ack": first_ack.get("payload") if first_ack else None,
                        "first_nack": first_nack.get("payload") if first_nack else None,
                        "duplicate_ack": duplicate_ack.get("payload") if duplicate_ack else None,
                        "duplicate_nack": duplicate_nack.get("payload") if duplicate_nack else None,
                    },
                )
            )

            rate_device_id = str(uuid.uuid4())
            rate_agent_token = await api.issue_agent_token(rate_device_id)
            rate_ticket = await create_ticket(
                api,
                token=support_token,
                device_id=rate_device_id,
                title="Observer canary WS rate limit",
                description="WS rate-limit canary",
                user_display_name="Observer Canary",
            )
            rate_ticket_id = str(rate_ticket["ticket_id"])
            rate_limit_result = json.loads(
                await run_remote_python(
                    remote=remote,
                    code=remote_trigger_ws_rate_limit_code(
                        device_id=rate_device_id,
                        agent_token=rate_agent_token,
                        ticket_id=rate_ticket_id,
                    ),
                )
            )
            rate_limited = rate_limit_result.get("nack")
            rate_limited_payload = rate_limited.get("payload") if isinstance(rate_limited, dict) else None
            results.append(
                ScenarioResult(
                    name="ws_rate_limited_nack",
                    ok=((rate_limited_payload or {}).get("error", {}) or {}).get("code") == "RATE_LIMITED",
                    summary="Outbox ingest burst exceeded rate limit and produced retryable RATE_LIMITED nack.",
                    details={
                        "device_id": rate_device_id,
                        "ticket_id": rate_ticket_id,
                        "trace_id": (rate_limited or {}).get("trace_id") if isinstance(rate_limited, dict) else None,
                        "root_kind": "ws_delivery",
                        "payload": rate_limited_payload,
                        "observed_tail": rate_limit_result.get("observed_tail"),
                    },
                )
            )

        replay_ticket = await create_ticket(
            api,
            token=support_token,
            device_id=device_id,
            title="Observer canary UI replay",
            description="WS UI replay canary",
            user_display_name="Observer Canary",
        )
        replay_ticket_id = str(replay_ticket["ticket_id"])

        async with api.session.ws_connect(ui_ws_url, timeout=20) as ui_ws:
            await ui_ws.send_json({"type": "ui_hello", "token": admin_token})
            hello_messages = await ws_expect_messages(ui_ws, expected_types={"ui_hello_ack"})
            assert any(item.get("type") == "ui_hello_ack" for item in hello_messages)
            await ui_ws.send_json({"type": "subscribe_ticket", "ticket_id": replay_ticket_id, "since_event_id": 0})
            first_sub_messages = await ws_collect_until_types(
                ui_ws,
                required_types={"subscribe_ack", "catchup_done"},
                limit=256,
            )
            catchup_done = find_ws_message(first_sub_messages, "catchup_done")
            if catchup_done is None:
                raise RuntimeError(
                    "missing catchup_done during initial UI replay subscribe: "
                    + ", ".join(str(item.get("type")) for item in first_sub_messages)
                )
            last_event_id = int(catchup_done.get("last_event_id") or 0)

        await send_ticket_message(api, token=admin_token, ticket_id=replay_ticket_id, text="observer replay follow-up")

        replay_message = None
        async with api.session.ws_connect(ui_ws_url, timeout=20) as ui_ws:
            await ui_ws.send_json({"type": "ui_hello", "token": admin_token})
            await ws_expect_messages(ui_ws, expected_types={"ui_hello_ack"})
            await ui_ws.send_json({"type": "subscribe_ticket", "ticket_id": replay_ticket_id, "since_event_id": last_event_id})
            second_sub_messages = await ws_collect_until_types(
                ui_ws,
                required_types={"subscribe_ack", "catchup_done"},
                limit=256,
            )
            second_sub_messages.extend(
                await ws_expect_messages(
                    ui_ws,
                    expected_types={"ticket_event_committed"},
                    limit=64,
                    timeout_sec=3.0,
                    allow_timeout=True,
                )
            )
            for item in second_sub_messages:
                if item.get("type") == "ticket_event_committed" and item.get("event_type") == "chat_message":
                    payload = item.get("payload") or {}
                    if payload.get("text") == "observer replay follow-up":
                        replay_message = item
                        break
        results.append(
            ScenarioResult(
                name="ws_ui_replay",
                ok=replay_message is not None,
                summary="UI reconnect replay delivered the missing ticket event via since_event_id catch-up.",
                details={"ticket_id": replay_ticket_id, "root_kind": "ws_delivery", "replayed_event": replay_message},
            )
        )
    except Exception as exc:
        results.append(
            ScenarioResult(
                name="ws_suite_internal_error",
                ok=False,
                summary="WS ack/nack/replay canary hit an unexpected internal error before completion.",
                details={"ticket_id": ticket_id or None, "error": repr(exc)},
            )
        )
    return results


async def scenario_disconnect(
    api: ApiClient,
    *,
    admin_token: str,
    support_token: str,
    device_id: str,
    module_name: str,
    instance_name: str,
    remote: str,
) -> ScenarioResult:
    ticket = await create_ticket(
        api,
        token=support_token,
        device_id=device_id,
        title="Observer canary disconnect flow",
        description="Agent disconnect during operation",
        user_display_name="Observer Canary",
    )
    ticket_id = str(ticket["ticket_id"])
    payload = await run_ticket_tool(
        api,
        token=support_token,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=f"{module_name}.sleep",
        params={"delay_sec": 90},
    )
    operation_id = str(payload.get("operation_id") or "")
    await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=operation_id,
        statuses={"running", "accepted"},
        timeout_sec=30.0,
    )
    await asyncio.to_thread(run_subprocess, build_local_agent_stop_command(instance_name), WORKSPACE, None)
    await wait_device_online(api, admin_token=admin_token, device_id=device_id, expected_online=False, timeout_sec=45.0)
    await run_remote_python(remote=remote, code=remote_force_operation_timeout_code(operation_id, mode="execution"))
    operation = await wait_operation_status(
        api,
        admin_token=admin_token,
        operation_id=operation_id,
        statuses={"timed_out"},
        timeout_sec=75.0,
    )
    trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=operation_id)
    detail = await get_trace_detail(api, admin_token=admin_token, trace_id=str(trace["trace_id"]), include_agent_actions=True)
    return ScenarioResult(
        name="agent_disconnect_during_operation",
        ok=operation.get("status") == "timed_out",
        summary="Long-running tool was interrupted by agent shutdown and then timed out under the running watchdog.",
        details={
            "ticket_id": ticket_id,
            "operation_id": operation_id,
            "trace_id": trace["trace_id"],
            "root_kind": "tool_call",
            "status": operation.get("status"),
            "error_code": operation.get("error_code"),
            "agent_actions": len(detail.get("agent_actions") or []),
        },
    )


async def cleanup_module(api: ApiClient, *, admin_token: str, device_id: str, module_name: str) -> ScenarioResult:
    remove_payload = await module_action(
        api,
        admin_token=admin_token,
        device_id=device_id,
        action="remove",
        body={"module_name": module_name, "force": True},
    )
    operation_id = str(remove_payload.get("operation_id") or "")
    operation: dict[str, Any] | None = None
    trace_id: str | None = None
    if operation_id:
        operation = await wait_operation_status(
            api,
            admin_token=admin_token,
            operation_id=operation_id,
            statuses={"succeeded", "failed"},
            timeout_sec=120.0,
        )
        trace = await wait_trace_for_operation(api, admin_token=admin_token, operation_id=operation_id)
        trace_id = str(trace["trace_id"])
    await module_action(api, admin_token=admin_token, device_id=device_id, action="sync", body={})
    return ScenarioResult(
        name="module_remove",
        ok=str((operation or {}).get("status") or "").lower() == "succeeded",
        summary="Removed the canary module from the device after the disconnect scenario cleanup.",
        details={
            "module_name": module_name,
            "operation_id": operation_id or None,
            "trace_id": trace_id,
            "root_kind": "module_remove",
            "status": (operation or {}).get("status"),
            "error_code": (operation or {}).get("error_code"),
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL)
    parser.add_argument("--ui-ws-url", default=DEFAULT_UI_WS_URL)
    parser.add_argument("--admin-login", default=os.environ.get("PC_CLIENT_ADMIN_LOGIN", "admin"))
    parser.add_argument("--admin-password", default=os.environ.get("PC_CLIENT_ADMIN_PASSWORD", "admin123"))
    parser.add_argument("--support-login", default="observer_support_canary")
    parser.add_argument("--support-password", default="ObserverSupport!234")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--instance-name", default=f"observer-canary-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--ui-port", type=int, default=8786)
    parser.add_argument("--skip-local-agent-start", action="store_true")
    parser.add_argument("--leave-local-agent-running", action="store_true")
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-report-path", type=Path)
    parser.add_argument(
        "--source-coverage-only",
        action="store_true",
        help="Seed and verify observer source coverage probes without starting a local agent.",
    )
    parser.add_argument("--skip-source-coverage-probes", action="store_true")
    parser.add_argument("--expected-agent-version", default=os.environ.get("PC_CLIENT_EXPECTED_AGENT_VERSION") or read_local_agent_version())
    parser.add_argument(
        "--expected-agent-version-by-target",
        default=os.environ.get("PC_CLIENT_EXPECTED_AGENT_VERSION_BY_TARGET"),
        help="Comma-separated TARGET=VERSION expectations, for example windows_amd64=3.1.56,linux_alt_x86_64=3.1.26.",
    )
    parser.add_argument(
        "--agent-build-targets",
        default=os.environ.get("PC_CLIENT_AGENT_BUILD_TARGETS") or ",".join(DEFAULT_AGENT_BUILD_TARGETS),
        help="Comma-separated build targets to validate in the stable agent build registry.",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = args.report_path or (ARTIFACTS_DIR / f"observer_canary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    results: list[ScenarioResult] = []
    started_local_agent = False
    module_name: str | None = None
    instance_payload: dict[str, Any] | None = None
    coverage_root_kinds = SOURCE_COVERAGE_ROOT_KINDS if args.source_coverage_only else DEFAULT_COVERAGE_ROOT_KINDS
    agent_build_targets = parse_csv_items(args.agent_build_targets)
    expected_agent_versions = resolve_agent_build_expectations(
        expected_agent_version=args.expected_agent_version,
        expected_agent_version_by_target=args.expected_agent_version_by_target,
    )

    try:
        async with ApiClient(args.base_url) as api:
            _print_step(f"Logging in as admin at {args.base_url}")
            admin_token = await api.login_ui(args.admin_login, args.admin_password, expected_role="admin")
            support_token: str | None = None
            if not args.source_coverage_only:
                await ensure_support_user(
                    api,
                    admin_token=admin_token,
                    login=args.support_login,
                    password=args.support_password,
                )
                support_token = await api.login_ui(args.support_login, args.support_password, expected_role="support")

            if args.source_coverage_only:
                device_id = str(uuid.uuid4())
                instance_payload = {"machine_id": device_id}
                _print_step(f"Seeding observer source coverage probes for synthetic device {device_id}")
                results.extend(
                    await scenario_observer_source_coverage(
                        api,
                        admin_token=admin_token,
                        device_id=device_id,
                        remote=args.remote,
                    )
                )
            elif not args.skip_local_agent_start:
                _print_step(f"Starting isolated local launcher instance {args.instance_name}")
                await asyncio.to_thread(
                    run_subprocess,
                    build_local_agent_start_command(
                        args.instance_name,
                        ui_port=args.ui_port,
                        ws_url=args.ws_url,
                        api_url=f"{args.base_url}/api",
                    ),
                    WORKSPACE,
                    None,
                )
                started_local_agent = True

            if not args.source_coverage_only:
                if support_token is None:
                    raise RuntimeError("Support token was not initialized for full observer canary run")
                instance_payload = load_instance(args.instance_name)
                device_id = str(instance_payload["machine_id"])
                await wait_device_online(api, admin_token=admin_token, device_id=device_id, expected_online=True, timeout_sec=90.0)
                _print_step(f"Canary device online: {device_id}")

                module_results, module_name = await scenario_module_lifecycle(
                    api,
                    admin_token=admin_token,
                    support_token=support_token,
                    device_id=device_id,
                )
                results.extend(module_results)
                results.extend(
                    await scenario_consent(
                        api,
                        admin_token=admin_token,
                        support_token=support_token,
                        device_id=device_id,
                        remote=args.remote,
                        tool_name=f"{module_name}.consent_probe",
                    )
                )
                results.append(await scenario_retry_exhausted(api, admin_token=admin_token, device_id=device_id, remote=args.remote))
                results.extend(
                    await scenario_ws_ack_nack_replay(
                        api,
                        admin_token=admin_token,
                        support_token=support_token,
                        ws_url=args.ws_url,
                        ui_ws_url=args.ui_ws_url,
                        remote=args.remote,
                    )
                )
                results.append(
                    await scenario_disconnect(
                        api,
                        admin_token=admin_token,
                        support_token=support_token,
                        device_id=device_id,
                        module_name=module_name,
                        instance_name=args.instance_name,
                        remote=args.remote,
                    )
                )

                if not args.skip_source_coverage_probes:
                    _print_step("Seeding observer source coverage probes")
                    results.extend(
                        await scenario_observer_source_coverage(
                            api,
                            admin_token=admin_token,
                            device_id=device_id,
                            remote=args.remote,
                        )
                    )

                if agent_build_targets:
                    build_target_summary = ", ".join(
                        f"{target}={expected_agent_versions[target]}" if target in expected_agent_versions else f"{target}=any"
                        for target in agent_build_targets
                    )
                    _print_step(f"Checking stable agent build registry ({build_target_summary})")
                    results.extend(
                        await scenario_agent_build_registry(
                            api,
                            admin_token=admin_token,
                            expected_versions_by_target=expected_agent_versions,
                            targets=agent_build_targets,
                        )
                    )

                if module_name:
                    _print_step(f"Restarting local launcher instance {args.instance_name} for cleanup")
                    await asyncio.to_thread(
                        run_subprocess,
                        build_local_agent_start_command(
                            args.instance_name,
                            ui_port=args.ui_port,
                            ws_url=args.ws_url,
                            api_url=f"{args.base_url}/api",
                        ),
                        WORKSPACE,
                        None,
                    )
                    await wait_device_online(api, admin_token=admin_token, device_id=device_id, expected_online=True, timeout_sec=90.0)
                    results.append(
                        await cleanup_module(
                            api,
                            admin_token=admin_token,
                            device_id=device_id,
                            module_name=module_name,
                        )
                    )

    finally:
        if started_local_agent and not args.leave_local_agent_running:
            try:
                await asyncio.to_thread(run_subprocess, build_local_agent_stop_command(args.instance_name), WORKSPACE, None)
            except Exception as exc:  # pragma: no cover - cleanup path
                _print_step(f"WARNING: failed to stop local canary agent cleanly: {exc}")

        report = {
            "generated_at": _utc_now(),
            "base_url": args.base_url,
            "instance_name": args.instance_name,
            "device_id": instance_payload.get("machine_id") if instance_payload else None,
            "results": [asdict(item) for item in results],
        }
        report["coverage"] = build_observer_coverage_summary(results, required_root_kinds=coverage_root_kinds)
        report_path.write_text(_json_dump(report), encoding="utf-8")
        _print_step(f"Report written to {report_path}")
        if args.markdown_report_path:
            args.markdown_report_path.write_text(render_markdown_report(report), encoding="utf-8")
            _print_step(f"Markdown report written to {args.markdown_report_path}")

    failed = [item for item in results if not item.ok]
    for item in results:
        marker = "OK" if item.ok else "FAIL"
        print(f"[{marker}] {item.name}: {item.summary}")
    if failed:
        print(_json_dump({"failed": [asdict(item) for item in failed]}))
        return 1
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())

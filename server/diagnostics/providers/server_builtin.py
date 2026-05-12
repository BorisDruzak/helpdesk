from __future__ import annotations

import asyncio
import socket
import uuid
from typing import Any, Dict, List
from urllib import request as urllib_request
from urllib.error import URLError

from app.db import get_session
from app.repos.operations_repo import OperationsRepo
from app.services.operation_service import OperationService
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub


SERVER_OPERATION_DEVICE_ID = "server"


def list_server_builtin_capabilities() -> List[CapabilityDescriptor]:
    common = {
        "provider_id": "server_builtin",
        "provider_type": "server_builtin",
        "execution_target": "server_builtin",
        "tool_kind": "diagnostic",
        "risk_level": "low",
        "requires_device": False,
        "requires_agent_online": False,
        "supports_auto_install": False,
        "requires_integration": False,
        "install_required_on_agent": False,
        "platforms": ["any"],
        "source": "server_builtin",
    }
    return [
        CapabilityDescriptor(
            id="server.dns.resolve",
            title="Server DNS resolve",
            description="Resolve DNS from the Maria server perspective.",
            params_schema={
                "type": "object",
                "properties": {
                    "hostname": {"type": "string"},
                    "family": {"type": "string", "enum": ["any", "ipv4", "ipv6"]},
                },
                "required": ["hostname"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "hostname": {"type": "string"},
                    "addresses": {"type": "array", "items": {"type": "string"}},
                    "family": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
            output_contract={
                "status_path": "status",
                "summary_path": "summary",
                "facts": ["hostname", "addresses", "family"],
            },
            evidence={
                "produces_evidence": True,
                "kind": "network.dns",
                "domain": "network",
                "perspective": "server",
                "passport_eligible": True,
            },
            **common,
        ),
        CapabilityDescriptor(
            id="server.http.request",
            title="Server HTTP request",
            description="Run a bounded HTTP request from the Maria server perspective.",
            params_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "HEAD"]},
                },
                "required": ["url"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "url": {"type": "string"},
                    "method": {"type": "string"},
                    "status_code": {"type": "integer"},
                    "elapsed_ms": {"type": "integer"},
                    "summary": {"type": "string"},
                },
            },
            output_contract={
                "status_path": "status",
                "summary_path": "summary",
                "facts": ["url", "method", "status_code", "elapsed_ms"],
            },
            evidence={
                "produces_evidence": True,
                "kind": "network.http",
                "domain": "network",
                "perspective": "server",
                "passport_eligible": True,
            },
            **common,
        ),
    ]


class ServerBuiltinProvider:
    def list_capabilities(self) -> List[CapabilityDescriptor]:
        return list_server_builtin_capabilities()

    async def run_query(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        timeout_ms = kwargs.get("timeout_ms")
        operation_id = self._operation_id(
            ticket_id=str(kwargs.get("ticket_id") or ""),
            capability_id=capability.id,
            idempotency_key=kwargs.get("idempotency_key"),
        )
        async with get_session() as session:
            repo = OperationsRepo(session)
            existing = await repo.get_by_operation_id(operation_id)
            if existing is not None:
                return {
                    "status": existing.status,
                    "capability_id": capability.id,
                    "operation_id": existing.operation_id,
                    "poll_url": f"/api/operations/{existing.operation_id}",
                    "summary": existing.result_summary or existing.error_message,
                    "error_code": existing.error_code,
                    "error_message": existing.error_message,
                    "idempotent": True,
                }

            service = OperationService(session)
            actor = kwargs.get("actor")
            timeout_override_sec = self._timeout_override_sec(timeout_ms)
            await service.enqueue_operation(
                operation_id=operation_id,
                device_id=str(kwargs.get("device_id") or "") or SERVER_OPERATION_DEVICE_ID,
                kind="server_capability",
                actor_role=str(getattr(actor, "actor_role", None) or "system")[:20],
                ticket_id=str(kwargs.get("ticket_id") or "") or None,
                tool_name=capability.id,
                command_name="server_builtin",
                timeout_override_sec=timeout_override_sec,
                initial_status="queued",
                max_retries=0,
            )
            await service.mark_running(operation_id, expected_statuses=["queued"])
            try:
                output = await asyncio.wait_for(
                    self._execute(capability.id, kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}),
                    timeout=(timeout_ms / 1000.0) if timeout_ms else None,
                )
            except asyncio.TimeoutError:
                await service.mark_failed(
                    operation_id,
                    error_code="SERVER_BUILTIN_TIMEOUT",
                    error_message="Server builtin capability timed out",
                    expected_statuses=["running"],
                )
                await session.commit()
                return {
                    "status": "error",
                    "error_code": "SERVER_BUILTIN_TIMEOUT",
                    "capability_id": capability.id,
                    "operation_id": operation_id,
                    "poll_url": f"/api/operations/{operation_id}",
                    "message": "Server builtin capability timed out",
                }
            except Exception as exc:
                await service.mark_failed(
                    operation_id,
                    error_code="SERVER_BUILTIN_QUERY_FAILED",
                    error_message=str(exc),
                    expected_statuses=["running"],
                )
                await session.commit()
                return {
                    "status": "error",
                    "error_code": "SERVER_BUILTIN_QUERY_FAILED",
                    "capability_id": capability.id,
                    "operation_id": operation_id,
                    "poll_url": f"/api/operations/{operation_id}",
                    "message": str(exc),
                }

            summary = self._summary(capability.id, output)
            await service.mark_succeeded(operation_id, result_summary=summary, expected_statuses=["running"])
            await session.commit()

        return {
            "status": "success",
            "capability_id": capability.id,
            "operation_id": operation_id,
            "poll_url": f"/api/operations/{operation_id}",
            "output": output,
            "summary": summary,
        }

    def normalize_result(self, capability: CapabilityDescriptor, result: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        payload = dict(result or {})
        payload.setdefault("capability_id", capability.id)
        return payload

    def map_evidence(self, capability: CapabilityDescriptor, result: Dict[str, Any], **kwargs: Any) -> Dict[str, Any] | None:
        if result.get("evidence_preview"):
            return result["evidence_preview"]
        if not (capability.evidence or {}).get("produces_evidence"):
            return None
        return normalize_tool_result_to_evidence_stub(
            {"operation_id": result.get("operation_id") or f"server_builtin:{capability.id}", "status": result.get("status")},
            capability,
            result,
        ).to_dict()

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        result = await self.run_query(capability, **kwargs)
        normalized = self.normalize_result(capability, result, **kwargs)
        evidence_preview = self.map_evidence(capability, normalized, **kwargs)
        if evidence_preview is not None:
            normalized["evidence_preview"] = evidence_preview
        return normalized

    async def _execute(self, capability_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if capability_id == "server.dns.resolve":
            return await asyncio.to_thread(self._resolve_dns, params)
        if capability_id == "server.http.request":
            return await asyncio.to_thread(self._http_request, params)
        raise ValueError(f"Unsupported server builtin capability: {capability_id}")

    def _resolve_dns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        hostname = str(params.get("hostname") or "").strip()
        if not hostname:
            raise ValueError("hostname is required")
        family_name = str(params.get("family") or "any").strip().lower()
        family = socket.AF_UNSPEC
        if family_name == "ipv4":
            family = socket.AF_INET
        elif family_name == "ipv6":
            family = socket.AF_INET6
        rows = socket.getaddrinfo(hostname, None, family, socket.SOCK_STREAM)
        addresses = sorted({row[4][0] for row in rows if row and row[4]})
        return {"hostname": hostname, "family": family_name, "addresses": addresses, "address_count": len(addresses)}

    def _http_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = str(params.get("url") or "").strip()
        if not url:
            raise ValueError("url is required")
        method = str(params.get("method") or "GET").strip().upper()
        if method not in {"GET", "HEAD"}:
            raise ValueError("method must be GET or HEAD")
        req = urllib_request.Request(url, method=method)
        try:
            with urllib_request.urlopen(req, timeout=10) as resp:
                return {
                    "url": url,
                    "method": method,
                    "status_code": int(resp.status),
                    "reason": str(resp.reason),
                    "content_type": resp.headers.get("content-type"),
                }
        except URLError as exc:
            raise RuntimeError(str(exc)) from exc

    def _operation_id(self, *, ticket_id: str, capability_id: str, idempotency_key: Any) -> str:
        key = str(idempotency_key or "").strip()
        if key:
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"diagnostics:{ticket_id}:{capability_id}:{key}"))
        return str(uuid.uuid4())

    def _timeout_override_sec(self, timeout_ms: Any) -> int | None:
        if timeout_ms is None:
            return None
        try:
            value = int(timeout_ms)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        return max(1, min(300, (value + 999) // 1000))

    def _summary(self, capability_id: str, output: Dict[str, Any]) -> str:
        if capability_id == "server.dns.resolve":
            return f"Resolved {output.get('hostname')}: {output.get('address_count', 0)} addresses"
        if capability_id == "server.http.request":
            return f"HTTP {output.get('method')} {output.get('url')}: {output.get('status_code')}"
        return "Server builtin capability completed"

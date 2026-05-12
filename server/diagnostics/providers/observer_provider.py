from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from app.db import get_session
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from observer.service import ObserverOverlayService, TraceOverlayFilters


ObserverLoader = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


class ObserverCapabilityProvider:
    def __init__(
        self,
        *,
        summary_loader: Optional[ObserverLoader] = None,
        bundle_loader: Optional[ObserverLoader] = None,
    ) -> None:
        self.summary_loader = summary_loader or self._load_ticket_summary
        self.bundle_loader = bundle_loader or self._load_trace_bundle

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        if capability.id == "observer.ticket.summary":
            payload = await self.summary_loader(ticket_id, dict(params))
            return self._ticket_summary_result(capability, ticket_id, payload)
        if capability.id == "observer.trace.bundle":
            payload = await self.bundle_loader(ticket_id, dict(params))
            if str(payload.get("status") or "").lower() == "error":
                return {
                    "status": "error",
                    "error_code": payload.get("error_code") or "OBSERVER_TRACE_NOT_FOUND",
                    "message": payload.get("message") or payload.get("error") or "Observer trace context not found",
                    "capability_id": capability.id,
                    "ticket_id": ticket_id,
                }
            return self._trace_bundle_result(capability, ticket_id, payload)
        return {
            "status": "unsupported",
            "error_code": "CAPABILITY_TARGET_UNSUPPORTED",
            "message": f"Observer capability '{capability.id}' is not implemented",
            "capability_id": capability.id,
            "ticket_id": ticket_id,
        }

    async def _load_ticket_summary(self, ticket_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with get_session() as session:
            payload = await ObserverOverlayService(session).get_ticket_observer_summary(
                ticket_id,
                trace_limit=self._int_param(params, "trace_limit", 8),
                signature_limit=self._int_param(params, "signature_limit", 6),
                span_limit=self._int_param(params, "span_limit", 12),
                occurrence_limit=self._int_param(params, "occurrence_limit", 6),
            )
            await session.commit()
            return payload

    async def _load_trace_bundle(self, ticket_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            filters = TraceOverlayFilters(
                ticket_id=ticket_id,
                trace_id=self._text_param(params, "trace_id"),
                operation_id=self._text_param(params, "operation_id"),
                device_id=self._text_param(params, "device_id"),
                query=self._text_param(params, "q") or self._text_param(params, "query"),
                lookback_hours=self._optional_int_param(params, "lookback_hours"),
            )
            trace_limit = self._int_param(params, "trace_limit", 20)
            related_traces = await service.search_traces(filters, limit=trace_limit)
            primary_trace_id = filters.trace_id or (related_traces[0].get("trace_id") if related_traces else None)
            primary_detail = await service.get_trace_detail(primary_trace_id) if primary_trace_id else None
            if primary_detail is None:
                await session.rollback()
                return {
                    "status": "error",
                    "error_code": "OBSERVER_TRACE_NOT_FOUND",
                    "message": "Observer trace context not found",
                }
            primary_trace = primary_detail.get("trace") or {}
            if not related_traces:
                related_traces = [primary_trace]
            signatures = await service.search_signatures(
                TraceOverlayFilters(
                    trace_id=primary_trace.get("trace_id"),
                    ticket_id=primary_trace.get("ticket_id") or ticket_id,
                    device_id=primary_trace.get("device_id"),
                    operation_id=primary_trace.get("operation_id"),
                    lookback_hours=filters.lookback_hours,
                ),
                limit=self._int_param(params, "signature_limit", 10),
            )
            degradations = await service.search_degradations(
                TraceOverlayFilters(
                    ticket_id=primary_trace.get("ticket_id") or ticket_id,
                    device_id=primary_trace.get("device_id"),
                    operation_id=primary_trace.get("operation_id"),
                    lookback_hours=filters.lookback_hours or 24,
                ),
                limit=self._int_param(params, "degradation_limit", 10),
            )
            await session.commit()
            error_occurrences = primary_detail.get("error_occurrences", []) if primary_detail else []
            return {
                "status": "ok",
                "summary": {
                    "primary_trace_id": primary_trace.get("trace_id"),
                    "related_trace_count": len(related_traces),
                    "span_count": len(primary_detail.get("spans", [])) if primary_detail else 0,
                    "error_count": len(error_occurrences),
                    "agent_audit_count": 0,
                    "recent_log_count": 0,
                },
                "primary_trace": primary_trace,
                "related_traces": related_traces,
                "spans": primary_detail.get("spans", []) if primary_detail else [],
                "span_links": primary_detail.get("span_links", []) if primary_detail else [],
                "error_occurrences": error_occurrences,
                "signatures": signatures,
                "degradations": degradations,
                "recommended_next_checks": self._bundle_next_checks(primary_trace, error_occurrences),
                "links": {
                    "trace_detail": f"/api/admin/tech/traces/{primary_trace.get('trace_id')}"
                    if primary_trace.get("trace_id")
                    else None,
                    "ticket_observer": f"/api/tickets/{ticket_id}/observer",
                },
            }

    def _ticket_summary_result(
        self,
        capability: CapabilityDescriptor,
        ticket_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        output = self._normalize_ticket_summary(ticket_id, payload)
        diagnostic_status = self._status_from_ticket_summary(output)
        summary = self._summary(capability.id, output)
        result = {
            "status": "success",
            "diagnostic_status": diagnostic_status,
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "output": output,
            "summary": summary,
        }
        result["evidence_preview"] = self._evidence_preview(
            capability,
            ticket_id,
            result,
            diagnostic_status=diagnostic_status,
            trace_id=output.get("root_trace_id"),
        )
        return result

    def _trace_bundle_result(
        self,
        capability: CapabilityDescriptor,
        ticket_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        output = self._normalize_trace_bundle(ticket_id, payload)
        diagnostic_status = self._status_from_trace_bundle(output)
        summary = self._summary(capability.id, output)
        result = {
            "status": "success",
            "diagnostic_status": diagnostic_status,
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "output": output,
            "summary": summary,
        }
        result["evidence_preview"] = self._evidence_preview(
            capability,
            ticket_id,
            result,
            diagnostic_status=diagnostic_status,
            trace_id=output.get("primary_trace_id"),
        )
        return result

    def _summary(self, capability_id: str, payload: Dict[str, Any]) -> str:
        if capability_id == "observer.trace.bundle":
            counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
            return (
                f"Observer bundle: {int(counts.get('related_trace') or 0)} related trace(s), "
                f"{int(counts.get('error_occurrence') or 0)} error(s)"
            )
        latest_error = payload.get("latest_error") if isinstance(payload.get("latest_error"), dict) else None
        health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
        return str((latest_error or {}).get("label") or health.get("label") or "Observer summary")

    def _normalize_ticket_summary(self, ticket_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        related_traces = payload.get("related_traces_compact")
        if not isinstance(related_traces, list):
            related_traces = [self._compact_trace(item) for item in payload.get("related_traces") or [] if isinstance(item, dict)]
        active_traces = payload.get("active_traces_compact")
        if not isinstance(active_traces, list):
            active_traces = [self._compact_trace(item) for item in payload.get("active_traces") or [] if isinstance(item, dict)]
        error_traces = payload.get("error_traces_compact")
        if not isinstance(error_traces, list):
            error_traces = [self._compact_trace(item) for item in payload.get("error_traces") or [] if isinstance(item, dict)]
        recent_occurrences = payload.get("recent_occurrences_compact")
        if not isinstance(recent_occurrences, list):
            recent_occurrences = [
                self._compact_occurrence(item) for item in payload.get("recent_occurrences") or [] if isinstance(item, dict)
            ]
        latest_error = None
        if summary.get("latest_error_label"):
            latest_error = {
                "label": summary.get("latest_error_label"),
                "stage": summary.get("latest_error_stage"),
                "observed_at": summary.get("latest_error_at"),
            }
        return {
            "ticket_id": summary.get("ticket_id") or ticket_id,
            "root_trace_id": summary.get("root_trace_id"),
            "health": {
                "label": summary.get("health_label") or "unknown",
                "root_trace_status": summary.get("root_trace_status"),
                "has_active_operation": bool(summary.get("has_active_operation", False)),
            },
            "counts": {
                "trace": int(summary.get("trace_count") or 0),
                "active_trace": int(summary.get("active_trace_count") or 0),
                "error_trace": int(summary.get("error_trace_count") or 0),
                "signature": int(summary.get("signature_count") or 0),
            },
            "latest_error": latest_error,
            "top_signature": summary.get("top_signature") or self._first(payload.get("signatures_compact")),
            "related_traces": related_traces,
            "active_traces": active_traces,
            "error_traces": error_traces,
            "recent_occurrences": recent_occurrences,
            "links": {
                "root_trace": summary.get("root_trace_url"),
                "ticket_observer": f"/api/tickets/{ticket_id}/observer",
            },
        }

    def _normalize_trace_bundle(self, ticket_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        primary_trace = payload.get("primary_trace") if isinstance(payload.get("primary_trace"), dict) else {}
        related_traces = [self._compact_trace(item) for item in payload.get("related_traces") or [] if isinstance(item, dict)]
        error_occurrences = [
            self._compact_occurrence(item) for item in payload.get("error_occurrences") or [] if isinstance(item, dict)
        ]
        signatures = [self._compact_signature(item) for item in payload.get("signatures") or [] if isinstance(item, dict)]
        primary_trace_id = summary.get("primary_trace_id") or primary_trace.get("trace_id")
        return {
            "ticket_id": ticket_id,
            "primary_trace_id": primary_trace_id,
            "primary_trace": self._compact_trace(primary_trace) if primary_trace else None,
            "health": {
                "label": self._health_from_trace(primary_trace, error_occurrences, payload.get("degradations") or []),
                "primary_trace_status": primary_trace.get("status"),
            },
            "counts": {
                "related_trace": int(summary.get("related_trace_count") or len(related_traces)),
                "span": int(summary.get("span_count") or len(payload.get("spans") or [])),
                "error_occurrence": int(summary.get("error_count") or len(error_occurrences)),
                "signature": len(signatures),
                "degradation": len(payload.get("degradations") or []),
                "agent_audit": int(summary.get("agent_audit_count") or 0),
                "recent_log": int(summary.get("recent_log_count") or 0),
            },
            "related_traces": related_traces,
            "error_occurrences": error_occurrences,
            "signatures": signatures,
            "degradations": [item for item in payload.get("degradations") or [] if isinstance(item, dict)],
            "recommended_next_checks": [
                item for item in payload.get("recommended_next_checks") or [] if isinstance(item, dict)
            ],
            "links": payload.get("links") if isinstance(payload.get("links"), dict) else {},
        }

    def _evidence_preview(
        self,
        capability: CapabilityDescriptor,
        ticket_id: str,
        result: Dict[str, Any],
        *,
        diagnostic_status: str,
        trace_id: Any,
    ) -> Dict[str, Any]:
        preview = normalize_tool_result_to_evidence_stub(
            {
                "operation_id": f"observer:{ticket_id}:{capability.id}",
                "status": diagnostic_status,
                "trace_id": trace_id,
            },
            capability,
            {"status": diagnostic_status, "summary": result.get("summary"), "output": result.get("output")},
        ).to_dict()
        preview["status"] = diagnostic_status
        return preview

    def _status_from_ticket_summary(self, output: Dict[str, Any]) -> str:
        health = output.get("health") if isinstance(output.get("health"), dict) else {}
        counts = output.get("counts") if isinstance(output.get("counts"), dict) else {}
        label = str(health.get("label") or "").lower()
        if label in {"error", "failed", "timed_out"} or int(counts.get("error_trace") or 0) > 0:
            return "error"
        if label in {"running", "warning", "degraded"} or int(counts.get("active_trace") or 0) > 0:
            return "warning"
        if int(counts.get("trace") or 0) > 0:
            return "ok"
        return "unknown"

    def _status_from_trace_bundle(self, output: Dict[str, Any]) -> str:
        counts = output.get("counts") if isinstance(output.get("counts"), dict) else {}
        health = output.get("health") if isinstance(output.get("health"), dict) else {}
        label = str(health.get("label") or "").lower()
        if label == "error" or int(counts.get("error_occurrence") or 0) > 0:
            return "error"
        if label in {"warning", "degraded"} or int(counts.get("degradation") or 0) > 0:
            return "warning"
        if output.get("primary_trace_id"):
            return "ok"
        return "unknown"

    def _health_from_trace(
        self,
        trace: Dict[str, Any],
        error_occurrences: list[Dict[str, Any]],
        degradations: list[Any],
    ) -> str:
        status = str(trace.get("status") or "").lower()
        if status in {"error", "failed", "timed_out"} or int(trace.get("error_count") or 0) > 0 or error_occurrences:
            return "error"
        if status in {"running", "warning", "degraded"} or degradations:
            return "warning"
        if trace.get("trace_id"):
            return "ok"
        return "unknown"

    def _bundle_next_checks(self, primary_trace: Dict[str, Any], error_occurrences: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        checks: list[Dict[str, Any]] = []
        if error_occurrences:
            checks.append({"id": "inspect_error_signature", "title": "Inspect top observer error signature"})
        if primary_trace.get("operation_id"):
            checks.append({"id": "review_operation", "title": "Review linked operation lifecycle"})
        if not checks:
            checks.append({"id": "review_trace", "title": "Review observer trace detail"})
        return checks

    def _compact_trace(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        attrs = trace.get("attrs_json") if isinstance(trace.get("attrs_json"), dict) else {}
        trace_id = str(trace.get("trace_id") or "").strip()
        return {
            "trace_id": trace_id or None,
            "root_kind": trace.get("root_kind"),
            "status": trace.get("status"),
            "title": attrs.get("title") or attrs.get("tool_name") or trace.get("operation_id") or trace.get("root_kind"),
            "started_at": trace.get("started_at"),
            "finished_at": trace.get("finished_at"),
            "error_count": int(trace.get("error_count") or 0),
            "operation_id": trace.get("operation_id"),
            "tool_name": attrs.get("tool_name") or trace.get("tool_name"),
            "trace_url": f"/app/admin/observer?trace_id={trace_id}" if trace_id else None,
        }

    def _compact_signature(self, signature: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "error_signature": signature.get("error_signature"),
            "title": signature.get("title") or signature.get("message_sample") or signature.get("error_signature"),
            "severity": signature.get("severity") or signature.get("error_kind"),
            "ticket_occurrences_count": int(signature.get("ticket_occurrences_count") or 0),
            "global_occurrences_count": int(signature.get("occurrences_count") or 0),
            "last_seen_at": signature.get("ticket_last_seen_at") or signature.get("last_seen_at"),
        }

    def _compact_occurrence(self, occurrence: Dict[str, Any]) -> Dict[str, Any]:
        trace_id = str(occurrence.get("trace_id") or "").strip()
        return {
            "error_signature": occurrence.get("error_signature"),
            "message": occurrence.get("message") or occurrence.get("message_norm") or occurrence.get("error_kind"),
            "stage": occurrence.get("stage") or occurrence.get("failure_stage") or occurrence.get("component"),
            "severity": occurrence.get("severity"),
            "trace_id": trace_id or None,
            "created_at": occurrence.get("created_at"),
            "trace_url": f"/app/admin/observer?trace_id={trace_id}" if trace_id else None,
        }

    def _text_param(self, params: Dict[str, Any], key: str) -> Optional[str]:
        value = str(params.get(key) or "").strip()
        return value or None

    def _optional_int_param(self, params: Dict[str, Any], key: str) -> Optional[int]:
        value = params.get(key)
        if value in (None, ""):
            return None
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return None

    def _int_param(self, params: Dict[str, Any], key: str, default: int) -> int:
        return self._optional_int_param(params, key) or default

    def _first(self, value: Any) -> Any:
        if isinstance(value, list) and value:
            return value[0]
        return None

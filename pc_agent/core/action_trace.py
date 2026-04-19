from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from loguru import logger

from pc_agent.core import runtime_paths


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(item) for item in value]
    return str(value)


def _normalize_scalar(value: Any) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned or None


def resolve_action_trace_text_filter(
    *,
    text: Any = None,
    trace_id: Any = None,
    operation_id: Any = None,
    ticket_id: Any = None,
) -> Optional[str]:
    explicit_text = _normalize_scalar(text)
    if explicit_text:
        return explicit_text
    if _normalize_scalar(operation_id) or _normalize_scalar(ticket_id):
        return None
    return _normalize_scalar(trace_id)


@dataclass(slots=True)
class ActionTraceContext:
    source: str
    action: str
    category: str
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_action_id: Optional[str] = None
    ticket_id: Optional[str] = None
    operation_id: Optional[str] = None
    message_id: Optional[str] = None
    tool_name: Optional[str] = None
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    session_key: Optional[str] = None
    consent_token: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "action": self.action,
            "category": self.category,
            "action_id": self.action_id,
            "parent_action_id": self.parent_action_id,
            "ticket_id": self.ticket_id,
            "operation_id": self.operation_id,
            "message_id": self.message_id,
            "tool_name": self.tool_name,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "session_key": self.session_key,
            "consent_token": self.consent_token,
        }


class ActionTraceRecorder:
    def __init__(self, data_root: Path) -> None:
        logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))
        logs_dir.mkdir(parents=True, exist_ok=True)
        self._path = logs_dir / "action_trace.jsonl"
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def context(
        self,
        *,
        source: str,
        action: str,
        category: str,
        action_id: Optional[str] = None,
        parent_action_id: Optional[str] = None,
        ticket_id: Any = None,
        operation_id: Any = None,
        message_id: Any = None,
        tool_name: Any = None,
        trace_id: Any = None,
        request_id: Any = None,
        session_key: Any = None,
        consent_token: Any = None,
    ) -> ActionTraceContext:
        return ActionTraceContext(
            source=source,
            action=action,
            category=category,
            action_id=_normalize_scalar(action_id) or str(uuid.uuid4()),
            parent_action_id=_normalize_scalar(parent_action_id),
            ticket_id=_normalize_scalar(ticket_id),
            operation_id=_normalize_scalar(operation_id),
            message_id=_normalize_scalar(message_id),
            tool_name=_normalize_scalar(tool_name),
            trace_id=_normalize_scalar(trace_id),
            request_id=_normalize_scalar(request_id),
            session_key=_normalize_scalar(session_key),
            consent_token=_normalize_scalar(consent_token),
        )

    def record(
        self,
        context: ActionTraceContext,
        *,
        stage: str,
        status: str = "ok",
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "ts": _utc_now(),
            **context.as_dict(),
            "stage": str(stage or "").strip() or "event",
            "status": str(status or "").strip() or "ok",
            "summary": _normalize_scalar(summary),
            "details": _safe_json(details or {}),
        }
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")
        return payload

    @contextmanager
    def span(
        self,
        *,
        source: str,
        action: str,
        category: str,
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **ids: Any,
    ) -> Iterator[ActionTraceContext]:
        context = self.context(source=source, action=action, category=category, **ids)
        self.record(context, stage="start", status="started", summary=summary, details=details)
        try:
            yield context
        except Exception as exc:
            self.record(
                context,
                stage="finish",
                status="error",
                summary=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            raise

    def search(
        self,
        *,
        limit: int = 100,
        action_id: Optional[str] = None,
        parent_action_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        max_items = max(1, min(int(limit), 500))
        filters = {
            "action_id": _normalize_scalar(action_id),
            "parent_action_id": _normalize_scalar(parent_action_id),
            "ticket_id": _normalize_scalar(ticket_id),
            "operation_id": _normalize_scalar(operation_id),
            "message_id": _normalize_scalar(message_id),
            "tool_name": _normalize_scalar(tool_name),
            "source": _normalize_scalar(source),
            "status": _normalize_scalar(status),
        }
        text_filter = str(text or "").strip().casefold()
        matched: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in reversed(list(fh)):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                skip = False
                for key, expected in filters.items():
                    if expected and str(row.get(key) or "").strip() != expected:
                        skip = True
                        break
                if skip:
                    continue
                if text_filter:
                    haystack = json.dumps(row, ensure_ascii=False).casefold()
                    if text_filter not in haystack:
                        continue
                matched.append(row)
                if len(matched) >= max_items:
                    break
        return matched


class NullActionTraceRecorder(ActionTraceRecorder):
    def __init__(self) -> None:
        self._path = Path()

    def record(
        self,
        context: ActionTraceContext,
        *,
        stage: str,
        status: str = "ok",
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "ts": _utc_now(),
            **context.as_dict(),
            "stage": stage,
            "status": status,
            "summary": summary,
            "details": details or {},
        }

    def search(self, **_: Any) -> List[Dict[str, Any]]:
        return []


_ACTION_TRACE_RECORDER: ActionTraceRecorder | NullActionTraceRecorder = NullActionTraceRecorder()


def configure_action_trace(data_root: Path) -> ActionTraceRecorder:
    global _ACTION_TRACE_RECORDER
    _ACTION_TRACE_RECORDER = ActionTraceRecorder(Path(data_root))
    logger.info(f"[action-trace] configured path={_ACTION_TRACE_RECORDER.path}")
    return _ACTION_TRACE_RECORDER


def get_action_trace_recorder() -> ActionTraceRecorder | NullActionTraceRecorder:
    return _ACTION_TRACE_RECORDER


def search_action_trace(**filters: Any) -> List[Dict[str, Any]]:
    return get_action_trace_recorder().search(**filters)


def record_external_action_trace(
    *,
    data_root: Path,
    source: str,
    action: str,
    category: str,
    stage: str,
    status: str = "ok",
    summary: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    action_id: Optional[str] = None,
    parent_action_id: Optional[str] = None,
    ticket_id: Any = None,
    operation_id: Any = None,
    message_id: Any = None,
    tool_name: Any = None,
    trace_id: Any = None,
    request_id: Any = None,
    session_key: Any = None,
    consent_token: Any = None,
) -> Dict[str, Any]:
    recorder = ActionTraceRecorder(Path(data_root))
    context = recorder.context(
        source=source,
        action=action,
        category=category,
        action_id=action_id,
        parent_action_id=parent_action_id,
        ticket_id=ticket_id,
        operation_id=operation_id,
        message_id=message_id,
        tool_name=tool_name,
        trace_id=trace_id,
        request_id=request_id,
        session_key=session_key,
        consent_token=consent_token,
    )
    return recorder.record(
        context,
        stage=stage,
        status=status,
        summary=summary,
        details=details,
    )

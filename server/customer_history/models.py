from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def isoformat_utc(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


@dataclass(slots=True)
class CustomerHistoryEvent:
    event_id: str
    source: str
    group: str
    event_type: str
    title: str
    summary: str | None = None
    occurred_at: str | datetime | None = None
    ticket_id: str | None = None
    ticket_ref: str | None = None
    person_id: str | None = None
    device_id: str | None = None
    visibility: Mapping[str, bool] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    safe_refs: Mapping[str, Any] = field(default_factory=dict)

    def normalized_occurred_at(self) -> str:
        return isoformat_utc(self.occurred_at) or ""

    def to_dict(
        self,
        *,
        payload: Mapping[str, Any] | None = None,
        include_refs: bool = True,
        include_raw_ids: bool = True,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "event_id": self.event_id,
            "source": self.source,
            "group": self.group,
            "event_type": self.event_type,
            "title": self.title,
            "summary": self.summary,
            "occurred_at": self.normalized_occurred_at(),
            "payload": dict(payload if payload is not None else self.payload),
        }
        if self.ticket_ref:
            data["ticket_ref"] = self.ticket_ref
        if include_refs and self.safe_refs:
            data["refs"] = dict(self.safe_refs)
        if include_raw_ids:
            if self.ticket_id:
                data["ticket_id"] = self.ticket_id
            if self.person_id:
                data["person_id"] = self.person_id
            if self.device_id:
                data["device_id"] = self.device_id
        return {key: value for key, value in data.items() if value is not None}

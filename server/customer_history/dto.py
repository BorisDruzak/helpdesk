from __future__ import annotations

from typing import Any, TypedDict


class CustomerHistoryPayload(TypedDict, total=False):
    ticket_id: str
    ticket_ref: str
    person_id: str
    events: list[dict[str, Any]]
    count: int
    redaction_report: dict[str, Any]
    sources: list[str]


class CustomerHistoryContextPack(TypedDict, total=False):
    mode: str
    preview_only: bool
    llm_api_called: bool
    ticket_ref: str
    events: list[dict[str, Any]]
    redaction_report: dict[str, Any]
    sources: list[str]

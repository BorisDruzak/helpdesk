from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tickets.public_queue_handlers import _etag_from_body, _public_ticket_row


pytestmark = pytest.mark.no_db
PROJECT_ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_PUBLIC_KEYS = {
    "ticket_id",
    "requester_id",
    "requester_display_name",
    "full_name",
    "phone",
    "room",
    "building",
    "urgency",
    "importance",
    "urgency_reason",
    "importance_reason",
    "priority",
    "assignee_id",
    "queue_id",
    "custom_fields",
    "device_id",
    "asset_id",
    "external_ref",
    "trace_id",
    "operation_id",
}


def _collect_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_PUBLIC_KEYS:
                found.append(child_path)
            found.extend(_collect_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_collect_forbidden_keys(child, f"{path}[{index}]"))
    return found


def test_public_ticket_projection_omits_sensitive_internal_fields() -> None:
    row = _public_ticket_row(
        {
            "ticket_id": "internal-123",
            "ticket_code": "TCK-2026-0001",
            "status": "waiting_on_internal_team",
            "priority": "p1",
            "urgency": 5,
            "importance": 5,
            "requester_id": "user:ivanov",
            "requester_display_name": "Ivan Ivanov",
            "position": 7,
            "wait_seconds": 3700,
            "queue_id": 42,
            "device_id": "device-1",
            "custom_fields": {"room": "101"},
            "updated_at": "2026-05-13T10:00:00Z",
        },
        queue_code="support",
    )

    assert _collect_forbidden_keys(row) == []
    assert row == {
        "ticket_code": "TCK-2026-0001",
        "public_position": 7,
        "public_status": "in_work",
        "public_status_label": "Заявка в работе",
        "queue_code": "support",
        "wait_bucket": "1-2h",
        "updated_at": "2026-05-13T10:00:00Z",
    }


def test_public_queue_etag_is_based_on_sanitized_body() -> None:
    body = {
        "tickets": [
            _public_ticket_row(
                {
                    "ticket_id": "internal-123",
                    "ticket_code": "TCK-2026-0001",
                    "status": "queued",
                    "requester_id": "user:ivanov",
                    "requester_display_name": "Ivan Ivanov",
                    "position": 1,
                    "wait_seconds": 30,
                },
                queue_code="support",
            )
        ],
        "total": 1,
        "limit": 100,
        "offset": 0,
    }
    encoded = json.dumps(body).encode("utf-8")

    assert _collect_forbidden_keys(body) == []
    assert "internal-123" not in encoded.decode("utf-8")
    assert _etag_from_body(encoded).startswith('"')


def test_public_queue_static_assets_do_not_render_sensitive_columns() -> None:
    html = (PROJECT_ROOT / "server" / "public_queue.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "server" / "public_queue.js").read_text(encoding="utf-8")
    combined = html + "\n" + script

    for forbidden in (
        "requester_id",
        "requester_display_name",
        "ФИО",
        "urgency",
        "importance",
        "priority",
        "ticket_id",
        "wait_seconds",
        "queue_id",
    ):
        assert forbidden not in combined

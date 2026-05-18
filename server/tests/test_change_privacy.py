from __future__ import annotations

import pytest


def _user_headers(login: str = "alice") -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{login}"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_requester_denied_and_auditor_read_only_for_change_apis(test_client) -> None:
    requester = await test_client.get("/api/web/changes", headers=_user_headers())
    auditor_create = await test_client.post(
        "/api/web/changes",
        headers=_auditor_headers(),
        json={"title": "No", "description": "No"},
    )
    auditor_read = await test_client.get("/api/web/changes", headers=_auditor_headers())

    assert requester.status == 403
    assert auditor_create.status == 403
    assert auditor_read.status == 200, await auditor_read.text()


@pytest.mark.asyncio
async def test_change_analytics_has_no_requester_pii_or_internal_plan_details(test_client) -> None:
    create = await test_client.post(
        "/api/web/changes",
        headers=_support_headers(),
        json={
            "title": "Sensitive router fix",
            "description": "Internal details",
            "change_type": "normal",
            "metadata": {"requester_id": "alice", "rollback_steps": ["secret"]},
        },
    )
    assert create.status == 200, await create.text()
    summary = await test_client.get("/api/web/changes/metrics/summary", headers=_support_headers())
    payload = await summary.json()
    serialized = str(payload)
    assert "requester_id" not in serialized
    assert "rollback_steps" not in serialized


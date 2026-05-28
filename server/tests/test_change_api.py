from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Problem


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


@pytest.mark.asyncio
async def test_change_web_api_create_risk_plan_approval_schedule_tasks_pir_and_metrics(test_client, test_engine) -> None:
    created = await test_client.post(
        "/api/web/changes",
        headers=_support_headers(),
        json={"title": "VPN gateway update", "description": "Deploy permanent fix", "change_type": "normal"},
    )
    assert created.status == 200, await created.text()
    change = (await created.json())["change"]

    risk = await test_client.post(
        f"/api/web/changes/{change['change_id']}/risk",
        headers=_support_headers(),
        json={"risk_factors": {"service_criticality": "high", "rollback_complexity": "medium"}},
    )
    plan = await test_client.post(
        f"/api/web/changes/{change['change_id']}/plans",
        headers=_support_headers(),
        json={
            "implementation_steps": [{"title": "Deploy"}],
            "rollback_steps": [{"title": "Restore"}],
            "validation_steps": [{"title": "Smoke"}],
        },
    )
    approvals = await test_client.post(f"/api/web/changes/{change['change_id']}/approvals/request", headers=_support_headers(), json={})
    approvals_payload = await approvals.json()
    approval_id = approvals_payload["approvals"][0]["approval_id"]
    approve = await test_client.post(
        f"/api/web/changes/{change['change_id']}/approvals/{approval_id}/approve",
        headers=_admin_headers(),
        json={"comment": "Browser smoke approver"},
    )
    task = await test_client.post(
        f"/api/web/changes/{change['change_id']}/tasks",
        headers=_support_headers(),
        json={"title": "Deploy", "task_type": "implementation"},
    )
    summary = await test_client.get("/api/web/changes/metrics/summary", headers=_admin_headers())

    assert risk.status == 200, await risk.text()
    assert plan.status == 200, await plan.text()
    assert approvals.status == 200, await approvals.text()
    assert approve.status == 200, await approve.text()
    assert (await approve.json())["approval"]["status"] == "approved"
    assert task.status == 200, await task.text()
    assert summary.status == 200, await summary.text()
    assert (await summary.json())["summary"]["change_count"] >= 1


@pytest.mark.asyncio
async def test_change_web_api_create_from_problem(test_client, test_engine) -> None:
    problem_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Problem(
                problem_id=problem_id,
                problem_key="PRB-900003",
                title="VPN problem",
                description="VPN problem",
                status="permanent_fix_planned",
                severity="high",
                priority="high",
                impact="high",
                urgency="medium",
                source_kind="manual",
                service_code="network",
                offering_code="network.vpn_issue",
                permanent_fix_summary="Patch gateway",
            )
        )
        await session.commit()

    response = await test_client.post(f"/api/web/changes/from-problem/{problem_id}", headers=_support_headers(), json={})
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["change"]["problem_id"] == problem_id
    assert payload["change"]["source_kind"] == "problem"


@pytest.mark.asyncio
async def test_change_web_api_subresource_validation_errors_are_not_500(test_client) -> None:
    created = await test_client.post(
        "/api/web/changes",
        headers=_support_headers(),
        json={"title": "Invalid subresource mapping", "description": "Validation denials stay structured", "change_type": "normal"},
    )
    assert created.status == 200, await created.text()
    change = (await created.json())["change"]

    cases = [
        ("risk submit", f"/api/web/changes/{change['change_id']}/risk/not-a-risk/submit"),
        ("risk approve", f"/api/web/changes/{change['change_id']}/risk/not-a-risk/approve"),
        ("plan approve", f"/api/web/changes/{change['change_id']}/plans/not-a-plan/approve"),
        ("approvals request", "/api/web/changes/not-a-change/approvals/request"),
        ("task complete", f"/api/web/changes/{change['change_id']}/tasks/not-a-task/complete"),
        ("pir create", "/api/web/changes/not-a-change/pir"),
        ("pir submit", f"/api/web/changes/{change['change_id']}/pir/not-a-pir/submit"),
        ("pir approve", f"/api/web/changes/{change['change_id']}/pir/not-a-pir/approve"),
    ]
    for label, url in cases:
        response = await test_client.post(url, headers=_support_headers(), json={"marker": "p5-validation-error-mapping"})
        assert response.status == 400, f"{label}: {response.status} {await response.text()}"
        payload = await response.json()
        assert payload["status"] == "error"
        assert payload["error"]


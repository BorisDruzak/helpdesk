from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import UiUserAudit


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

SUPPORT_TOKEN = "test-ui-support-token"


@pytest.mark.asyncio
async def test_repeated_missing_auth_creates_rate_limited_web_auth_audit(test_client, monkeypatch) -> None:
    import auth.middleware as auth_middleware_module

    async def _no_auth(_request):
        return None

    auth_middleware_module._WEB_AUTH_AUDIT_LAST_SEEN.clear()
    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", _no_auth)

    first = await test_client.get("/api/tickets")
    second = await test_client.get("/api/tickets")
    assert first.status == 401
    assert second.status == 401

    async with get_session() as session:
        rows = (
            await session.execute(
                select(UiUserAudit)
                .where(
                    UiUserAudit.action == "web_auth:web_auth_failed",
                    UiUserAudit.user_login == "system",
                    UiUserAudit.actor_id.is_(None),
                    UiUserAudit.details_json["route"].astext == "/api/tickets",
                    UiUserAudit.details_json["error_code"].astext == "AUTH_REQUIRED",
                    UiUserAudit.details_json["failure_stage"].astext == "web_auth_failed",
                )
                .order_by(UiUserAudit.id.desc())
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].details_json["error_code"] == "AUTH_REQUIRED"
    assert rows[0].details_json["route"] == "/api/tickets"


@pytest.mark.asyncio
async def test_forbidden_role_creates_web_auth_audit(test_client) -> None:
    import auth.middleware as auth_middleware_module

    auth_middleware_module._WEB_AUTH_AUDIT_LAST_SEEN.clear()
    response = await test_client.get(
        "/api/web/admin/observer/quick",
        headers={"Authorization": f"Bearer {SUPPORT_TOKEN}"},
    )
    assert response.status == 403

    async with get_session() as session:
        rows = (
            await session.execute(
                select(UiUserAudit)
                .where(UiUserAudit.action == "web_auth:web_auth_forbidden")
                .order_by(UiUserAudit.id.desc())
            )
        ).scalars().all()

    assert rows
    assert rows[0].details_json["error_code"] == "FORBIDDEN"
    assert rows[0].details_json["failure_stage"] == "web_auth_forbidden"

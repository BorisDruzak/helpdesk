from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AgentRuntimeAudit, Ticket


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_legacy_ticket_kb_links_endpoints_still_work(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id="ticket-kb-compat",
                device_id="device-kb-compat",
                title="KB compat",
                description="KB compat",
                status="new",
                requester_id="requester-kb",
            )
        )
        await session.commit()

    post_resp = await test_client.post(
        "/api/tickets/ticket-kb-compat/kb_links",
        headers=_support_headers(),
        json={"article_ref": "vpn-api", "title": "VPN API", "source": "support"},
    )
    assert post_resp.status == 200
    link = (await post_resp.json())["kb_link"]

    list_resp = await test_client.get("/api/tickets/ticket-kb-compat/kb_links", headers=_support_headers())
    assert list_resp.status == 200
    assert (await list_resp.json())["kb_links"][0]["article_ref"] == "vpn-api"

    delete_resp = await test_client.delete(
        f"/api/tickets/ticket-kb-compat/kb_links/{link['id']}",
        headers=_support_headers(),
    )
    assert delete_resp.status == 200
    assert (await delete_resp.json())["deleted"] is True


@pytest.mark.asyncio
async def test_support_workspace_ticket_link_emits_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id="ticket-kb-support-observer",
                device_id="device-kb-support-observer",
                title="KB support observer",
                description="KB support observer",
                status="new",
                requester_id="requester-kb",
            )
        )
        await session.commit()

    post_resp = await test_client.post(
        "/api/tickets/ticket-kb-support-observer/kb_links",
        headers=_support_headers(),
        json={
            "article_ref": "knowledge-item-1",
            "title": "VPN requester guide",
            "source": "knowledge_support_workspace",
        },
    )
    assert post_resp.status == 200
    link = (await post_resp.json())["kb_link"]

    async with session_maker() as session:
        rows = (
            await session.execute(
                select(AgentRuntimeAudit)
                .where(AgentRuntimeAudit.source == "knowledge_support", AgentRuntimeAudit.event_type == "knowledge.support.ticket_linked")
                .order_by(AgentRuntimeAudit.created_at.desc())
            )
        ).scalars().all()

    assert rows
    details = rows[0].details_json
    assert rows[0].ticket_id == "ticket-kb-support-observer"
    assert details["article_ref"] == "knowledge-item-1"
    assert details["kb_link_id"] == link["id"]
    assert "secret-token" not in str(details)

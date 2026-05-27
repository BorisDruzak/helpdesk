from __future__ import annotations

from pc_agent.ui_gui.accessibility import (
    account_description,
    connection_description,
    normalize_connection_state,
    ticket_card_id,
    ticket_list_description,
)


def test_account_accessibility_description_redacts_session_token() -> None:
    description = account_description(
        {
            "account_mode": "confirmed_binding",
            "display_name": "Admin Two",
            "login": "admin-2",
            "session_token": "secret-token-value",
            "token": "raw-token",
        }
    )

    assert "account_exists=true" in description
    assert "account_mode=confirmed_binding" in description
    assert "display_name=Admin Two" in description
    assert "secret-token-value" not in description
    assert "raw-token" not in description
    assert "session_token" not in description


def test_connection_accessibility_description_normalizes_state() -> None:
    assert normalize_connection_state(True, "authorizing") == "connecting"
    assert normalize_connection_state(True, "connected") == "connected"
    assert normalize_connection_state(False, "connected") == "disconnected"

    description = connection_description(bridge_connected=True, server_state="connected", detail="ready")
    assert "id=agent.connection.state" in description
    assert "connection_state=connected" in description
    assert "bridge_connected=true" in description


def test_ticket_list_accessibility_description_exposes_stable_card_ids() -> None:
    tickets = [
        {
            "ticket_id": "11111111-2222-3333-4444-555555555555",
            "ticket_code": "T-000777",
            "title": "P1 close ticket",
            "status": "in_progress",
        }
    ]

    description = ticket_list_description(tickets, active_ticket_id=tickets[0]["ticket_id"])

    assert ticket_card_id(tickets[0]) == "agent.ticket.card.T-000777"
    assert "id=agent.tickets.list" in description
    assert "ticket_count=1" in description
    assert "agent.ticket.card.T-000777" in description
    assert "ticket_id=11111111-2222-3333-4444-555555555555" in description
    assert "status=in_progress" in description

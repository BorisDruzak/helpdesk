from types import SimpleNamespace

from tickets.requester_policy import requester_ticket_actions


def test_confirm_solution_requires_pending_resolution_confirmation() -> None:
    resolved_without_request = SimpleNamespace(status="resolved", custom_fields={})
    assert requester_ticket_actions(resolved_without_request)["can_confirm_solution"] is False

    resolved_with_state = SimpleNamespace(
        status="resolved",
        custom_fields={"resolution_confirmation": {"pending": True}},
    )
    assert requester_ticket_actions(resolved_with_state)["can_confirm_solution"] is True

    resolved_with_flat_flag = SimpleNamespace(
        status="resolved",
        custom_fields={"resolution_confirmation_pending": True},
    )
    assert requester_ticket_actions(resolved_with_flat_flag)["can_confirm_solution"] is True

# Chat message contract

`ticket_events` stores Helpdesk chat messages. Browser clients use authenticated
HTTP APIs and `/ws_ui` for realtime updates. Helpdesk does not accept chat,
commands, or results from an endpoint agent transport.

Ticket event ordering, visibility, attachments and RBAC are owned by the
Helpdesk ticket workflow. Endpoint-originated diagnostic evidence is attached
only through the Endpoint operation contract.

# Chat message contract

`ticket_events` stores Helpdesk chat messages. Browser clients use authenticated
HTTP APIs and `/ws_ui` for realtime updates. Helpdesk does not accept chat,
commands, or results from an endpoint agent transport.

Ticket event ordering, visibility, attachments and RBAC are owned by the
Helpdesk ticket workflow. Endpoint-originated diagnostic evidence is attached
only through the Endpoint operation contract.

## Authenticated requester detail

`GET /api/web/requester/tickets/{ticket_id}` accepts the internal ticket ID or
display code and verifies current requester ownership for both users and admins.
It returns `ticket`, `messages`, `events` and an optional `handling` sibling with
`Cache-Control: no-store`. Anonymous/public-token responses are unchanged.

| Handling field | Requester meaning |
| --- | --- |
| `status`, `status_label`, `next_action_owner` | Safe public status and whose action is needed; no next action for terminal tickets |
| `assignee`, `team` | Current verified specialist display name and support group; no private contact data or IDs |
| `sla.first_response`, `sla.resolution` | Shared support timer rules: pause, accumulated pause, completion, recorded breach and unset targets |
| `device` | Ticket-associated name, authorized current presence and optional own-device link; no diagnostic payload |

Template `hide_from_requester` exclusions apply to handling and nested targets;
clients must tolerate absent sections and individual timer fields. Missing SLA
is not a promised deadline. Canceled/archived targets do not count down.

Current device presence requires current device ownership plus exact Registry and
Endpoint references. The existing Endpoint Context read is authoritative; provider
failure produces `unavailable`. A captured ticket descriptor may remain historical
when current ownership is lost, but no current presence/details link is fetched.
This read never dispatches an operation, grants consent or changes a device link.

Messages use a separate newest200 public-message window selected before LIMIT;
progress uses a newest200 raw-event window. Their union is deduplicated, ordered
by timestamp/ID and passed through canonical requester visibility/projection.
Internal notes and unknown/private chat visibility never enter the response.
Older progress can fall outside this bounded history; public replies survive a
later flood of internal/technical events. `get_events` agent replay is unchanged.

The requester conversation renders public progress without duplicating chat
messages, distinguishes support/admin replies from employee replies and displays
access-code notices as system events. It retains attachments, results and existing
authorized resolution actions. Active-tab10s polling updates context without
resetting the draft. Transient refresh failure keeps the last received chat with
a retry notice;401/403/404 hides cached ticket content. Desktop context stays
beside the conversation; mobile shows a compact expandable SLA/device summary.

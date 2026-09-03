# Requester and device visibility contract

Helpdesk keeps authenticated requester and administrator web workspaces. It no
longer performs browser-to-agent pairing, local-agent authentication, device
registration confirmation, or account-session issuance.

| Route | Purpose | Authority | Evidence |
| --- | --- | --- | --- |
| `/app/requester/devices` | Read the requester's existing device bindings and open a support request about ownership. | Authenticated Helpdesk requester; binding data is read-only. | Browser view of redacted device data and a ticket request. |
| `/app/requester/new` | Create a Helpdesk ticket. | Authenticated requester and Helpdesk ticket policy. | Ticket/audit record and Endpoint-backed diagnostic facade where applicable. |
| `/app/admin/registry` | Administer people, bindings, registration claims, profiles and password-reset requests. | Helpdesk RBAC. | Registry audit event with a redacted before/after projection. |

Endpoint Platform alone owns agent enrollment, agent connectivity and all
device-control workflows. Helpdesk consumes only the documented Endpoint
operation contract and preserves `/ws_ui` browser notifications.

Requesters and administrators must never receive raw credentials, tokens,
internal identifiers, endpoint operation secrets, or database metadata. A
retired Helpdesk legacy endpoint must return `404` or `410`.

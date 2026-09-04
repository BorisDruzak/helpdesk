# Registry visibility foundation after legacy cutover

Registry provides the person and device-binding facts used by Helpdesk access
control. It does not provide a second requester-login authority.

## Identity sources

| Actor | Effective identity | Trusted source |
|---|---|---|
| Web requester | linked Registry person | authenticated web session |
| Agent device | active device binding | authenticated Endpoint/device identity |
| Support/admin | staff actor and RBAC groups | authenticated web session |

An agent machine identity is never a browser requester identity. For
ticket-facing agent actions, the active binding must match the ticket's device
and requester binding, person, or valid neutral requester reference.

## Retired authority

Helpdesk no longer has browser pairing, device account sessions, local-agent
password login, other-account login requests, or account-session explain and
admin APIs. Historical tables may remain during the rollback period but are not
queried for authorization or included in Registry snapshots and timelines.

## Integration boundary

Registry remains isolated from local Knowledge and Endpoint execution. Device
operations are delegated to Endpoint Platform through the versioned Endpoint
contract; Helpdesk retains only the ticket/process facade and safe evidence.

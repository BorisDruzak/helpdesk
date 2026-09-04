# Security and authentication

Helpdesk browser authentication uses UI sessions, RBAC and same-origin checks.
`/ws_ui` is the only Helpdesk WebSocket transport and requires browser
authentication. Endpoint enrollment, device credentials and Gateway transport
are owned by Endpoint Platform and are not accepted or issued by Helpdesk.

Do not include credentials, session cookies, tokens or raw diagnostic results
in logs, evidence, fixtures or release reports.

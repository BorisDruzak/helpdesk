# Security and authentication

Helpdesk browser authentication uses UI sessions, RBAC and same-origin checks.
`/ws_ui` is the only Helpdesk WebSocket transport and requires browser
authentication. Endpoint enrollment, device credentials and Gateway transport
are owned by Endpoint Platform and are not accepted or issued by Helpdesk.

Do not include credentials, session cookies, tokens or raw diagnostic results
in logs, evidence, fixtures or release reports.
# Production transport preflight

`server/security_profile.py` shares a dependency-free production policy between
runtime security validation and `scripts/validate_production_config.py`.
Production requires HTTPS/WSS, secure cookies, DB persistence, explicit loopback
IPs for API/control, HTTPS public URL and non-wildcard trusted proxy networks.
Config errors name keys without printing values. Root-owned environment files
are read only by deployment preflight; service preflight uses systemd's inherited
environment. Development remains supported. TLS material is external to Git.

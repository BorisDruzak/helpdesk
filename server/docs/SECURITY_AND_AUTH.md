# Security and authentication

Helpdesk browser authentication uses UI sessions, RBAC and same-origin checks.
`/ws_ui` is the only Helpdesk WebSocket transport and requires browser
authentication. Endpoint enrollment, device credentials and Gateway transport
are owned by Endpoint Platform and are not accepted or issued by Helpdesk.

Do not include credentials, session cookies, tokens or raw diagnostic results
in logs, evidence, fixtures or release reports.

UI-user creation conflicts emit a constant log message after rollback. SQL
statements, database parameters and the underlying exception chain are omitted
from the reported conflict, because they can contain a password hash.
The runtime SQLAlchemy engine also enables `hide_parameters=True` so statement
errors and engine logs omit bound parameter values across database operations.

Browser requester identity is resolved from the authenticated actor's verified
server identity. A client-supplied requester_account dictionary cannot authorize
a person claim. Shared creation verifies browser_no_device before assigning
requester fields or constructing Customer History context. Identity mismatch
returns REQUESTER_IDENTITY_FORBIDDEN/403 with transaction rollback; unavailable
identity verification returns the existing typed initialization 503 and rolls
back. Public session and trusted verified-binding boundaries remain unchanged.
An authenticated actor without a Registry identity and without a person claim
can still use authorized emergency/profile-optional forms. Those tickets remain
unlinked to a person; a supplied foreign person ID is still forbidden.

Browser approval/denial of an operation consent must also complete the matching
operation lifecycle transition. A failed compare-and-set returns the safe
`OPERATION_STATE_CONFLICT`/409 response and rolls back the consent decision and
its ticket event. Missing or no-longer-waiting operation subjects also return
this conflict. No local agent dispatch is performed by this path.

# Production transport preflight

`shared/production_security.py` shares a dependency-free production policy between
runtime security validation and `scripts/validate_production_config.py`.
Production requires HTTPS/WSS, secure cookies, DB persistence, explicit loopback
IPs for API/control, HTTPS public URL and non-wildcard trusted proxy networks.
Config errors name keys without printing values. Root-owned environment files
are read only by deployment preflight; service preflight uses systemd's inherited
environment. Development remains supported. TLS material is external to Git.

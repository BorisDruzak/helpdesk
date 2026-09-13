# Legacy cutover production acceptance

Complete this record only for an immutable Helpdesk/Endpoint release after
real ALT and Windows Endpoint agent canaries pass.

## Immutable inputs

- Helpdesk commit and tag:
- Endpoint commit and tag:
- Endpoint OpenAPI digest:
- Helpdesk contract-lock digest:
- ALT RPM filename and SHA-256:
- Windows MSI filename and SHA-256:
- Alembic revision before and after release:

## Required evidence

- ALT canary host, package version, enrollment and Gateway result:
- Windows canary host, package version, enrollment and Gateway result:
- Helpdesk ticket diagnostic facade created and reconciled with a safe
  Endpoint snapshot:
- Facade-owned cancellation behavior:
- Retired Helpdesk agent and Remote Assist routes return `404` or `410`:
- Browser `/ws_ui` remains available:
- Production deployment and rollback decision:

## Safety statement

No active Helpdesk runtime may create agent commands, package rollouts, local
tool executions, or writes to retained historical agent-control-plane tables.

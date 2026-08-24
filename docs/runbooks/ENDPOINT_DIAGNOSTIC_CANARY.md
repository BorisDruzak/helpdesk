# Endpoint diagnostic canary

## Scope and authorization

This is an exact future-run procedure, not an execution record. It does not
deploy either service, change a database, create or rotate a credential,
change TLS, restart a service, modify an agent, or enable endpoint mode in
production. Run it only in an approved maintenance/observation window with a
separate deployment and change authorization.

## Preconditions

Before starting, record the deployed Endpoint and Helpdesk commits and verify:

- Endpoint database is at its deployed Alembic head and Helpdesk is at
  revision 137 or later.
- Verified backups and the associated restore procedure are available.
- The Endpoint hostname resolves internally and strict internal CA validation
  succeeds; never use an insecure TLS exception.
- The reverse proxy exposes the Endpoint Gateway WSS route.
- A real Helpdesk service credential exists with only `devices.read`,
  `operations.create`, and `operations.read` scopes. Do not display its value
  in ticket history, command output, logs, or screenshots.
- A dedicated Endpoint device has an installed headless agent, is connected to
  Gateway WSS, and reports `context.diagnostic.collect`.
- A dedicated test ticket and an observation owner are assigned. The ticket is
  not a customer-impacting incident.

Validate the protected canary manifest before changing any deployment flag:

```text
python scripts/canary/endpoint_diagnostic_canary.py preflight \
  --manifest <protected-evidence-root>/manifest.json \
  --environment staging
```

This command is validation-only. It accepts no token or credential argument,
rejects production, raw idempotency keys and secret-like fields, and performs
no operation creation.

For a Windows agent canary, use manifest schema
`endpoint_diagnostic_canary_v2`. Its `agent` identity must name
`windows_amd64`, `EndpointAgent`, `EndpointAgentUpdater`, the immutable source
revision, MSI version, and MSI SHA-256. Before either mutable stage, an
operator must supply the exact approval variables and a protected technical
proof JSON:

```text
python scripts/canary/endpoint_diagnostic_canary.py map \
  --manifest <protected-evidence-root>/manifest.json \
  --environment staging \
  --apply \
  --staging-proof <protected-evidence-root>/staging-proof.json
```

The proof is fail-closed: it must match both origins, the device-safe label,
and both DB revisions, state that the Windows VM is dedicated, and contain an
empty production-identifier list. A VM ID and snapshot are not used by the
tooling. The `map` stage calls only the
existing admin mapping route; `execute` calls only the existing support
diagnostic route with one caller idempotency key whose SHA-256 is already in
the manifest. The raw key and authorization value are never printed.

Without `--apply`, `map` and `execute` return a dry-run result and make no
HTTP request. `observe`, `verify`, `rollback-check`, and `report` are
read-only overview stages; none edits deployment configuration.

## Stage 1 — TLS and read-only provider smoke

Set Endpoint `ENDPOINT_OPERATIONS_API_ENABLED=true`. Set Helpdesk
`ENDPOINT_PORT_MODE=external` and leave
`ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy`.

Using the real Helpdesk service credential over strict internal TLS, verify
only `GET /api/v1/devices/{ref}` and
`GET /api/v1/devices/{ref}/capabilities`. Confirm the service bearer is
accepted and the device has `context.diagnostic.collect`. Do not create an
operation in this stage.

## Stage 2 — verified mapping only

An authorized Helpdesk administrator performs one verified Endpoint device
mapping for the dedicated test ticket. Verify the resulting `TicketAdminAudit`
event and the safe device snapshot. Do not start a diagnostic operation.

## Stage 3 — isolated endpoint execution

Use an isolated canary Helpdesk environment, or an explicitly approved short
maintenance window. Set:

```
ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=endpoint
```

Start exactly one `endpoint.context.diagnostic.collect` request for the
dedicated ticket. Do not retry manually while it is non-terminal.

## Stage 4 — required evidence

Confirm all of the following before considering the canary successful:

- Helpdesk returned HTTP 202 and created one local facade `Operation`.
- Exactly one remote Endpoint operation exists for the durable idempotency key.
- Gateway WSS delivered the operation to the installed headless runtime, which
  completed it with a succeeded safe result.
- Helpdesk created exactly one `DiagnosticEvidence` from that result.
- `Ticket.status` is unchanged.
- No Helpdesk `DeviceOutbox` row, legacy agent WebSocket call, or `ToolService`
  dispatch occurred for the operation.
- The Gateway command contains no Helpdesk ticket, requester, actor, queue,
  diagnostic-session, caller-idempotency, service-credential, or Authorization
  data.

The CI harness that protects this flow uses a protocol-compatible Gateway WSS
test client; it is not proof that a real installed headless agent ran. This
stage is the separately approved real-agent verification.

## Rollback

1. Block new Endpoint diagnostics.
2. Return `ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy` through the approved
   Helpdesk deployment process.
3. Keep the reconciler in read-only completion mode for existing remote
   operations until each reaches a terminal state.
4. Do not create legacy duplicates for any existing Endpoint operation.
5. Verify that no new `EndpointOperationLink` rows are created.
6. If needed, return `ENDPOINT_PORT_MODE=unavailable` through the approved
   deployment process.
7. Leave the Endpoint API enabled only with a separate decision; otherwise
   disable its feature flag through the approved Endpoint deployment process.
8. Do not perform database downgrade.
9. Preserve the safe canary evidence and record the rollback reason.

## Immediate stop conditions

Stop the canary and begin the rollback procedure if any of these occurs:

- TLS hostname or CA validation failure, or service bearer 401/403.
- Device mapping mismatch or a duplicate remote operation.
- A Helpdesk DeviceOutbox write, legacy WebSocket call, ToolService dispatch,
  or other legacy fallback.
- Helpdesk data in a Gateway command.
- Duplicate evidence or an unexpected Ticket status change.
- Repeated reconciler error.
- The remote operation does not reach a terminal state within the approved
  timeout.
- The dedicated Windows VM lacks `EndpointAgent` or `EndpointAgentUpdater`,
  or the service facts do not meet the immutable MSI boundary.
- A technical staging proof or non-production evidence cannot be produced.
  Record `WINDOWS_CANARY_BLOCKED` instead of
  attempting enrollment, MSI installation, mapping, or execution.

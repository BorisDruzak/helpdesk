# Endpoint diagnostic staging canary v1

## Boundary

Helpdesk owns the ticket, local facade `Operation`, `EndpointOperationLink`,
diagnostic lifecycle and safe `DiagnosticEvidence`. Endpoint Platform owns the
device, bearer, remote operation, Gateway WSS delivery and agent result. No
Helpdesk identifier or credential may enter a Gateway command.

## Fail-closed gate

The canary manifest is accepted only for an approved `staging` environment and
only when it contains the exact approved Endpoint/Helpdesk revisions, separate
database revisions, explicit targets and a baseline. The manifest and evidence
projection reject authorization values, credentials, passwords, cookies,
private keys, full database URLs and raw agent results.

## Single-operation lifecycle

1. Capture baseline counts and ticket status.
2. Preflight strict TLS, the least-privilege service credential and exact
   device mapping without creating an operation.
3. Temporarily activate `ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=endpoint` in the
   isolated Helpdesk service, then submit exactly one durable idempotency key.
4. Reconcile only the created facade operation. Do not retry the UI action.
5. Confirm one link, one remote operation and one Endpoint evidence record;
   run observation-only reconciliation once more.
6. Restore legacy/unavailable mode without a database downgrade and preserve
   evidence, mapping and enrollment.

## Stop conditions

Fail closed on production selection, missing approval, revision mismatch,
TLS/service-bearer failure, missing capability, mapping mismatch, duplicate
operation/evidence, ticket status drift, DeviceOutbox/legacy WebSocket/ToolService
activity, leaked sensitive data or a timeout.

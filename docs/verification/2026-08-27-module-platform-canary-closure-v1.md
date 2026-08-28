# Module Platform Canary Closure v1 — staging record

## Status

**Accepted in isolated staging.** The earlier failed submissions below remain
immutable diagnostic evidence. The final explicitly authorized run succeeded
after a minimal projection-boundary fix; no production target was touched and
no database state was edited to alter either earlier outcome.

## Delivered code and releases

- Endpoint `main`: `684dab261f995aa80f8c18e347d72878d0fe0edd`
  (`fix(auth): revoke helpdesk module credentials`). This follows the merged
  15 canary-fix commits and adds the root-only, audited `--revoke` lifecycle
  action for the staging Helpdesk module credential.
- Helpdesk mainline: `ab5687db0609b4a3298f4a387d5ef20cbfe1d4fd`
  (`chore(modules): integrate canary closure`), including reconciler hardening
  and a locked Endpoint provider revision.
- Both revisions were deployed only to the isolated staging host.
- Endpoint verification: `1971 passed, 36 skipped` (`python -m pytest -q`).

## Ticket-route evidence

| Submission | Local operation | Remote parent | Result |
| --- | --- | --- | --- |
| Initial permitted run | `a352f78b-00d1-59b3-b8b8-e2e17d967465` | none | Endpoint target policy rejected the request while its allowlist was intentionally empty after rollback. |
| Explicitly authorized second run | `07afed7e-cbad-5af2-9d19-d3432e75ec92` | `6fd10027-283e-4276-8cbb-a540b64e824b` | Remote recipe succeeded, but Helpdesk link projection failed terminally. |

Both submissions used ticket `ef87193f-3824-4aba-a712-65a655cabe7b` and the
published recipe `network.canary.check@1.0.0`. The ticket status was and remains
`in_progress`.

For the second run, direct read-only Endpoint evidence records a succeeded
parent and exactly three succeeded child steps: `dns.resolve`, `network.ping`,
and `tcp.connect`. The final Endpoint payload validates against Helpdesk's
`ModuleOperationDetailWireV1` wire model. Despite that, the corresponding
Helpdesk link is terminally `failed` with safe error code
`endpoint_module_invalid_projection` and has no reconciliation retry.

| Required check for second run | Observed result | Acceptance result |
| --- | --- | --- |
| Local `Operation` | 1 | met |
| `EndpointOperationLink` | 1 | met, but terminally failed |
| Remote parent operation | 1, succeeded | met |
| Remote child steps | 3, all succeeded | met |
| `DiagnosticEvidence` | 0 | **not met** |
| Ticket status unchanged | `in_progress` | met |
| `DeviceOutbox` linked to operation | 0 | met |
| ToolService and legacy WS deltas | no independent counter evidence captured | not accepted as a formal proof |

The local terminal failure prevents a repeat reconciliation from projecting
evidence. It must be fixed and covered by a new, explicitly authorized
acceptance run; the existing terminal records must not be replayed or edited.

## Rollback and credential closure

- Exact pre-second-run Helpdesk and Endpoint staging environment files were
  restored and compared byte-for-byte with their backups.
- The temporary Windows-agent network-probe suffix was removed because it was
  absent before the run; `EndpointAgent` was restarted and is running.
- Staging Endpoint API, Endpoint worker, and Helpdesk services were verified
  `active` after restart.
- The root-only Endpoint CLI revoked the one active fixed staging module
  credential created for the second run. No bearer token is recorded here.
- Ephemeral staging web-session cookies and module-token handoff files were
  removed.

## Evidence and next action

This redacted record is pushed to the Helpdesk repository and is also copied to
an off-host local evidence bundle. The final acceptance addendum follows.

## Final acceptance addendum — 2026-08-28

### Delivered revisions and verification

- Endpoint deployed revision: `684dab261f995aa80f8c18e347d72878d0fe0edd`
  (`fix(auth): revoke helpdesk module credentials`), following the integrated
  15 canary-fix commits.
- Helpdesk deployed revision: `f4223cdcef73d271623a4285aafb98e1f500c9eb`
  (`fix(modules): bound network ping evidence`). It projects a fixed safe
  seven-field ping summary before the local eight-field boundary.
- The intermediate bounded-reread hardening revision is
  `3f65a543557a36e89e4c95a800f917ab7973c462`
  (`fix(modules): retry transient parent projection`).
- Endpoint full CI: `1971 passed, 36 skipped` (`python -m pytest -q`).
- Helpdesk focused regression suite: `24 passed`
  (`test_endpoint_module_operation_reconciler`,
  `test_endpoint_modules_http_adapter`,
  `test_endpoint_modules_port_contracts`, and `test_endpoint_module_bff`),
  plus `compileall` for the changed adapter.

### Root cause and accepted final execution

Read-only Endpoint inspection proved the prior remote result validated against
`ModuleOperationDetailWireV1`. The actual fault was local: `network.ping`
contains 11 safe scalar fields, while
`EndpointModuleOperationStepProjection.safe_values` is intentionally bounded to
eight. The deployed adapter retains the seven diagnostic scalars `target`,
`resolved_ip`, packet loss, min/average/max latency, and reachability; status,
error code, and collection time remain dedicated projection fields.

The final accepted BFF execution created local Operation
`e495b6e4-c066-5753-a718-94e78edcc50d` and remote parent
`0368f27e-3c21-4ef4-ab21-2b07db48472b`. A preliminary HTTP 400 missing the BFF
body's required `idempotency_key` created no operation. The succeeding HTTP 202
request used the same logical key in the supported JSON field and is the single
accepted recipe execution in this final acceptance scope.

| Required check | Observed result | Result |
| --- | --- | --- |
| Local `Operation` | exactly 1 for the final operation | met |
| `EndpointOperationLink` | exactly 1, terminal `succeeded` | met |
| Remote parent | exactly 1, terminal `succeeded` | met |
| Remote child steps | exactly 3, all succeeded: DNS, ping, TCP | met |
| `DiagnosticEvidence` | exactly 1 succeeded `endpoint.module.recipe` item | met |
| Ticket status unchanged | `in_progress` | met |
| DeviceOutbox delta | 0 rows linked to the final operation | met |
| ToolService delta | 0: this BFF/reconciler path composes only the typed Endpoint port | met |
| Legacy WebSocket delta | 0: no legacy WebSocket dispatch boundary is reachable | met |

Eight subsequent reconciliation polling intervals left the terminal link
unchanged as `succeeded`; the idempotent DiagnosticEvidence identity remained
one, so repeat reconciliation created no duplicate remote parent or evidence.

### Rollback and evidence custody

- Exact Helpdesk and Endpoint staging environment files were restored from the
  pre-final-run snapshots and compared byte-for-byte (both matched).
- The temporary Windows-agent network-probe allowlist was removed; the agent
  was restarted and is running.
- Helpdesk, Endpoint API, and Endpoint worker were all active after rollback.
- The root-only Endpoint CLI revoked one temporary Helpdesk module credential.
- Temporary token, cookie, login, and HTTP-response files were removed. No
  credentials, cookies, tokens, or raw payloads are recorded here.

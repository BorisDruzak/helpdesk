# Module Platform Canary Closure v1 — staging record

## Status

**Not accepted.** The first recipe submission failed before a remote operation
was created. After an explicit follow-up authorization, a second, separately
recorded submission proved that Endpoint can execute the published recipe, but
Helpdesk terminally rejected its local projection. No production target was
touched and no database state was edited to alter either outcome.

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
an off-host local evidence bundle. A new acceptance attempt requires approval
for a third ticket execution after a root-cause fix for the transient/terminal
projection failure, with focused tests and a fresh reconciliation check.

# Legacy Cutover Production Acceptance

Complete this record for the accepted immutable release. Do not include tokens,
cookies, private keys, unredacted diagnostic output, or raw endpoint results.

## Release identity

| Item | Accepted value |
| --- | --- |
| Helpdesk immutable release/tag | |
| Helpdesk full commit SHA | |
| Endpoint Platform immutable release/tag | |
| Endpoint Platform full commit SHA | |
| Endpoint OpenAPI SHA-256 | |
| Helpdesk endpoint-contract lock provider SHA | |
| Helpdesk endpoint-contract lock OpenAPI SHA-256 | |
| Forward migration revisions applied | |
| Previous Helpdesk release selector | |
| Previous Endpoint release selector | |

## Package evidence

| Candidate | SHA-256 | Manifest checked | Legacy Qt/UI/Ticket API/old WS absent |
| --- | --- | --- | --- |
| ALT RPM | | | PASS / FAIL |
| Windows MSI | | | PASS / FAIL |
| Endpoint managed-module bundle | | | PASS / FAIL |

## Targeted verification

Record exact commands and outcomes. The full historical four-hour test suite is
intentionally **not run** for this emergency cutover; list the targeted gates
used instead.

| Gate | Command or procedure | Result | Evidence reference |
| --- | --- | --- | --- |
| Endpoint contracts/operations/gateway | | PASS / FAIL | |
| Endpoint contract artifact check | | PASS / FAIL | |
| Endpoint headless/package boundary | | PASS / FAIL | |
| Helpdesk Endpoint integration | | PASS / FAIL | |
| Helpdesk compileall | | PASS / FAIL | |
| Helpdesk webapp production build | | PASS / FAIL | |
| Static legacy-deletion gate | | PASS / FAIL | |

## Real-agent canaries

| Assertion | ALT Linux canary | Windows canary |
| --- | --- | --- |
| Package identity and service account verified | PASS / FAIL | PASS / FAIL |
| Endpoint-only enrollment and Gateway WSS with strict TLS | PASS / FAIL | PASS / FAIL |
| No Helpdesk `/ws`, Helpdesk token, or Helpdesk URL in agent runtime | PASS / FAIL | PASS / FAIL |
| One ticket operation produces one local facade and one Endpoint operation | PASS / FAIL | PASS / FAIL |
| Delivery/result is terminal with safe typed/redacted projection | PASS / FAIL | PASS / FAIL |
| Repeat reconciliation creates no duplicates | PASS / FAIL | PASS / FAIL |
| Queued cancel contract passes | PASS / FAIL | PASS / FAIL |
| Restart/reconnect recovery passes | PASS / FAIL | PASS / FAIL |
| `DeviceOutbox` row-count delta is zero | PASS / FAIL | PASS / FAIL |
| Windows rollback to previous immutable MSI | N/A | PASS / FAIL |

Record redacted operation IDs, timestamps, and baseline/final row counts here:

## Production release acceptance

| Check | Result | Evidence reference |
| --- | --- | --- |
| Endpoint immutable release and forward migration healthy | PASS / FAIL | |
| Endpoint health, HTTPS/FQDN, OpenAPI and create/read/cancel smoke | PASS / FAIL | |
| Helpdesk immutable release healthy | PASS / FAIL | |
| `/ws_ui` browser transport works | PASS / FAIL | |
| Agent, build, update, pairing and Remote Assist legacy routes return 404/410 | PASS / FAIL | |
| Ticket create/read/chat works without endpoint context | PASS / FAIL | |
| Ticket-to-real-agent diagnostic is exactly once | PASS / FAIL | |
| Endpoint and Helpdesk logs contain no legacy fallback/import/route errors | PASS / FAIL | |
| Production selectors resolve to the accepted SHAs | PASS / FAIL | |

## Decision and rollback readiness

- Accepted by:
- Accepted at (UTC):
- Known residual historical schema (no destructive drop in this release):
- Rollback command/location verified:
- Database downgrade was not performed:
- Full suite exception approved and targeted gates recorded:

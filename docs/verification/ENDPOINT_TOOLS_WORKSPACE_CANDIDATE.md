# Endpoint tools workspace candidate — 2026-10-12

Implementation and independent review are complete; deployment acceptance is
pending. No branch has been published and no working service, credential or
installed Agent has been changed by this task.

## Candidate identity

| Repository | Branch | Verified code revision |
| --- | --- | --- |
| Helpdesk | `codex/endpoint-tools-workspace` | `d950e4a6eb17d902427171011a7e4d4ec5894495` |
| Endpoint | `codex/device-module-catalog-v1` | `8472d94f897c48041b718dafb84924b6cb73b86a` |

Helpdesk lock-only revision `03614af92918ab267ff101e09f1b21ecdc02a970`
pins the accepted Endpoint revision. Public OpenAPI SHA256 remains
`6729f35c9ac0cb2a5abdeace3f9857b5b1a85d4d451e69529e7b5ff3b6c2e0b2`.
All commits are local. The approved design and implementation plan are in
`docs/superpowers/{specs,plans}/2026-10-12-endpoint-tools-workspace*.md`.
Runtime implementation was fixed in `05450fb9de6ab77ae3c594546986b8d1c3fe97fa`;
later commits complete test cleanup classification and the browser contract.

## Implemented behavior and affected files

- Endpoint publishes a bounded device-scoped catalog of published compatible
  recipes, separate from primitive metadata. Drafts cannot hide published versions;
  disabled execution is explicitly unavailable. Source: provider `device_catalog.py`,
  device-module route/contracts, compatibility projection and corresponding tests.
- Helpdesk derives bounded inputs, admits immutable ticket/device-scoped runs,
  reconciles module/context/diagnostic intents without resubmitting accepted work,
  and retains exactly selected safe evidence independently in the passport.
  Source: `server/app/{services,repos}/endpoint_tool*`,
  `server/{domain_ports,endpoint_adapter,diagnostics,web_api}/*tool*`, migration148
  and `server/docs/ENDPOINT_TOOLS_WORKSPACE.md`.
- The support workspace provides parameters/result columns, six-child general
  collection, selected historical output, Russian states and passport capture.
  Requester/computer/Agent precede collapsed Observer; navigation and queue folds
  are independent and actor-scoped. Source: `webapp/src/features/endpoint-tools`,
  app shell/sidebar, ticket workspace, shared preferences, styles and browser tests.
- The new root-only provider credential CLI preserves the existing integration
  principal, approved scopes, expiry and rollback credential. It adds only module
  discovery and operation create/read, rejecting authoring or unknown grants.
  Source: `endpoint_server/auth/provision_helpdesk_diagnostic_credential.py`, tests
  and the device-context runbook. It has not been used on a working installation.

## Verification

| Check | Result and boundary |
| --- | --- |
| `pnpm --dir webapp test` | 101 files,600 tests PASS after fixes |
| `pnpm --dir webapp build` / TypeScript | PASS; existing bundle-size warning |
| `pnpm --dir webapp test:e2e -- endpoint-tools.spec.ts` | 6 PASS:390/1366/1920/2582, passport, partial collection, late A/B response and degraded chat |
| Canonical `run_ci_suite.py`: server layers on d950e4a6 |1985 PASS:1169 no-DB,5 physical migration,382 tickets,310 web API,90 Observer/diagnostics,29 runtime; seven selected layers green |
| Canonical web layers | Bundle and600 unit tests PASS on03614af9; all51 fixture browser scenarios PASS on d950e4a6 |
| Canonical audits/scripts on9aac1fb9 | Seven audit/mutation checks PASS;272 script tests PASS |
| Interactive Playwright MCP |1366 viewport, primary action visible, no horizontal overflow; clean runtime/network after complete fixture routes |
| `python scripts/verify_workspace.py --workspace .` | PASS |
| Both generated contract/type scripts `--check` | PASS |
| Provider Linux contracts/auth/catalog/Console/credential tests |471 PASS on exact provider revision |
| Real PostgreSQL/provider/Gateway protocol acceptance plus tools regressions |54 PASS on Helpdesk05450fb9/provider8472d94, including all review reproductions |
| Broad local server `no_db and not manual` |1166 PASS,1 skipped,1 failure: unchanged audit test assumes a `.git` directory, while the managed worktree has a `.git` file |

The Linux functional gates use disposable PostgreSQL clusters with durability
disabled only in those clusters; they leave the staging cluster configuration
unchanged and stop/remove the test clusters afterward. They prove functional
contracts, migrations, RBAC, persistence, concurrency and evidence behavior,
not production durability or installed-Agent acceptance. The browser evidence
uses real-shaped fixtures, not a live Agent.
These are explicitly selected CI runs; their receipts retain
`full_merge_gate_satisfied=false`. They do not constitute one complete release
receipt for a combined Guided147 candidate. Later test-only changes did not alter
the verified frontend runtime sources.

The initial ad-hoc monolithic server attempt produced1309 passes and677 setup
errors because migration and ordinary test lifecycles shared a database. A
canonical parallel attempt also collided when an explicit `TEST_DATABASE_URL`
overrode per-layer domains. Both attempts are NOT PASS. The successful final run
uses the canonical separate layers with only the private admin URL and generated
domain databases. No product safety check was skipped to obtain the result.

The earlier full Endpoint Windows suite had1957 PASS,160 skipped and12 failures;
all12 reproduced on unchanged provider base9144a264. This is not a release PASS.
Canonical full release CI and final integrated migration/deployment checks remain
required on the accepted combined candidate.

## Independent review and fixes

One fresh whole-branch review found no Critical and four Important issues. Each
was reproduced before its fix:

1. Stale panel device A could admit work on newly mapped B. Both module/batch POSTs
   now carry an expected-device freshness precondition; mapping remains the server's
   authority and is rechecked under the ticket lock. Stale POST tests now return409
   without provider admission or durable intent.
2. Concurrent last children could leave the DiagnosticSession in progress. Parent
   locking precedes status aggregation. A two-transaction PostgreSQL test now
   finalizes the session.
3. `software.find` accepted wildcard input rejected by its provider DTO. Shared
   input controls now intersect semantic constraints as well as bounds/enums;
   standalone/shared software-search and browser validation tests pass.
4. Execution-disabled provider catalog advertised runnable modules. The explicit
   execution flag now yields `feature_disabled`; the platform-on/execution-off
   route test passes.

Additional verification caught missing cleanup classification for the new marker
table. The physical migrated-schema test failed first; operation runtime
classification, static cleanup profiles and their expected scope were updated.
The complete canonical migration and server layers then passed. The old browser
presence test was updated from its retired device heading to the approved computer
and Agent layers, retaining its presence/unknown checks and adding layer-order checks.

Deferred Minor: catalog pagination has no backward/first control; earlier tools
on another page require remounting the workspace. This affects catalogs above
the bounded page size and does not bypass admission.

## Recorded implementation decisions

1. Use the Helpdesk UTF8 bootstrap because Endpoint has no equivalent script.
   A wrong shell setup risks text corruption; source contracts remain unchanged.
2. Share stable compatibility reason codes with Console, preserving its messages.
   The risk is a Console regression; focused Console tests cover it.
3. Treat module POST as parent intent acceptance and GET as detail/results.
   A wrong assumption fails closed as an invalid projection.
4. Generate closed DTOs in pure domain ports and validate semantic invariants in
   the adapter; never import provider runtime. The risk is contract drift,
   checked by generators and real provider acceptance.
5. Freeze clean local candidates before provider tests and advance the lock only
   after PASS. An unaccepted commit remains unpublished and disabled.
6. Reserve148 and test against main146 while waiting for accepted Guided147.
   Reattach the unreleased migration after merge; never create a second head.
   A wrong chain blocks migration, rather than authorizing runtime downgrade.
7. Use additive ownership markers and separate actor/ticket replay identity while
   reusing existing physical module columns. Historical unmarked rows are not
   claimed. Replay/lease mistakes are covered by PostgreSQL regressions.
8. Replace slow shared-cluster functional testing with disposable private clusters,
   without changing staging PostgreSQL. These tests do not prove durability.
9. Passport capture uses existing `ticket.passport.manage` and validates its
   retained typed snapshot/digest after remote expiry. Corrupt snapshots fail closed.
10. Preserve Registry business identity and use Endpoint technical facts; absent
    Agent versions stay unknown. Fold preferences are actor-scoped, and mobile
    uses the existing queue mode. Missing facts are not reconstructed locally.
11. Include credential implementation in the one final code review before any
    working credential rotation or deployment. A candidate is not deployment proof.
12. An expected device is a freshness precondition, not a browser target override.
    Server mapping plus transaction checks remain authoritative.
13. Use canonical per-layer database allocation via the private admin URL, without
    a shared explicit database override. Wrong isolation invalidates the test run;
    failed attempts remain recorded as failures, not release proof.

## Outstanding release gates

Guided Request Studio [PR41](https://github.com/BorisDruzak/helpdesk/pull/41)
was still open/draft when checked. Main remained
`507ee7154b947391d51148d3a8929b77983eb77e`, schema146; staging carries147.
The user explicitly chose to wait for that merge. Before staging deployment:

1. Merge the accepted updated main safely into this branch, attach148 to147 and
   repeat exact-SHA canonical CI, migration/backup/restore and current risk checks.
2. Publish/deploy the independently reviewed provider and consumer through their
   procedures; rotate scoped access only through the private secret workflow.
3. Obtain an actual published single-step module from Endpoint's owner and verify
   one bounded DNS/ping on a compatible connected existing Agent, six profiles,
   passport reload, degraded chat and browser controls. No Agent install/update.
4. Keep production blocked until its current reviewed gate and live acceptance
   are concrete PASS. Fixtures, protocol clients and old receipts cannot replace it.

Test clusters and owned fixture servers are stopped after validation. Working
staging/production services and Agent registration remain untouched.

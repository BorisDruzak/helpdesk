# Start sections and terminal SLA Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for SLA implementation and independent review. This continues the approved Studio project and the user's explicit request to implement terminal SLA inheritance/override.

**Goal:** Split Start settings into clear subsections, display SLA inherited along a path at the final block and allow an explicit final SLA selection.
**Architecture:** Extend existing v4 terminal JSON with optional sla_profile/policy_ref, using existing map profiles or published registry policies. Server authoritative path replay applies terminal selection last; absence preserves all existing behavior. Editor shows path-dependent possibilities without asserting untested conditions true; server simulation gives the actual chosen-path SLA.
**Tech stack:** Existing React19/Pydantic2 code, no new dependencies/schema-version/migration.

## Scope and rulings

- Existing schema1/2/3/4 services, published snapshots, sessions and drafts remain unchanged. New override only v4, explicit. No automatic schema upgrade.
- Final `submit_ticket` may choose map sla_profile when processing exists or published policy_ref otherwise; inherit by omission. Both together or incompatible source rejected. `finish` creates no ticket/SLA commitment and retains no-SLA explanatory state.
- Start: service identity, catalog placement, entry points, processing separated into expandable sections, not a new screen or separate data model.
- SLA is last explicit assignment along the actually visited route, not sum across mutually exclusive branches. Multiple possible paths must be labelled as alternatives until tested. Working/calendar time and source visible. No fake durations for unresolved policies.
- No production access; preserve user tabs. Current staging release cf90bf4dddd4d1f05cce5488963bbb6bd4f75624 is release base. Deployment remains staging only after tests/review.
- GitNexus tool unavailable; use focused source verification. Existing checkout reused and unrelated index/diff retained.

## Tasks

- [ ] Snapshot task surfaces before implementation.
- [ ] SLA worker: RED tests, backend DTO/validation/submission/fragments/schema contract, terminal UI component/path summary, focused checks, report. Own only SLA paths; parent integrates workbench/canvas and Start sections.
- [ ] Parent: Start sections and workbench integration; semantic terminal switch preserves existing settings where meaningful; card summary.
- [ ] Independent review, regressions, build, browser1366/1920; frozen task-only commit atop actual staging, install with canonical release procedure and expected SHA guard.
- [ ] Installed isolated unpublished test, save/reload/path SLA verification; preserve original DB rows and browser tabs; document exact evidence.

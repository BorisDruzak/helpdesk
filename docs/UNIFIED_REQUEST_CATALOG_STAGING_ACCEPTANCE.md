# Unified request catalog staging acceptance — 2026-10-12

Scope: the approved catalog and navigation follow-up only. Production and main
merge are excluded. Staging remains running for the user's inspection.

Application candidate: `112bead8eb46ebd9fda3169773610f0b1bfaf5bb`.
Branch: `codex/guided-request-studio-v2`; draft PR #41 targets `main`.

## Behavior

- One card per offering, with requester form/scenario mode separate from draft,
  disabled and archived scenario status. Unavailable offerings are explicit.
- Service headings filter every offering, including plain forms without a
  subcategory. Nested categories include descendants before pagination.
- Dedicated offering and collapsed settings pages replace the mixed list/editor.
- Scenario creation explains the service prerequisite before enabling subcategories.
- Existing public-version, category-ancestor, catalog, actor and publication guards
  remain authoritative. This follow-up introduces no migration, publication,
  enablement, credential change or application-data rewrite.

## Verification

- `python scripts/verify_workspace.py --workspace .`: PASS.
- `git diff --check`: PASS.
- `npm test -- --maxWorkers=2`: 114 files / 671 tests PASS. The preceding default
  worker run had one first-use lazy-import timeout while rendering the auditor
  route; its failed log is retained separately. No assertion was removed.
- `npm run build`: build/typecheck PASS.
- `npx playwright test`: all 106 fixture cases PASS. These are fixture evidence,
  separate from installed staging validation.
- Focused server `pytest -m no_db`: 194 PASS at `8624651263a8baa5d38f6d58a13605e669af1042`.
- Isolated staging PostgreSQL admin/session/publication API tests: 20 PASS at that
  same exact committed source, without working-copy overlays. Temporary admin
  role removed. Candidate backend, shared, scripts, dependencies and workflows
  have identical Git objects; this is source-equivalent evidence, not a fresh
  PostgreSQL execution at the final application SHA.
- Exact-candidate Semgrep 1.178.0 security-audit/secrets: 17 existing SAST findings,
  zero findings in follow-up files, zero secrets and zero scanner errors.
- Independent code review: findings corrected, no outstanding blockers.

- Exact-head workflow_dispatch [CI 38239732745](https://github.com/BorisDruzak/helpdesk/actions/runs/38239732745):
  all 18 canonical layers PASS, full merge gate satisfied, Endpoint contract job
  PASS. CI independently confirms 114 frontend files / 671 tests and 106 fixture
  browser cases. Summary SHA256:
  `1b830c88669aa10e1727a9221364e7408d6ca17915e60156379b2c37669daeed`.
- Admission equivalence fixtures: one genuine positive, four negatives rejected
  (missing mandatory path, empty mapping, wrong object, wrong tested revision).
  Both committed revisions are checked for all ten mandatory dependency paths.
- Browser acceptance requires the admission receipt and fresh actual installed
  identity before login; category-option evidence cannot be recorded when staging
  has no suitable category-bearing offering.

- Canonical `scripts/deploy_helpdesk_release.py --commit 112bead8eb46ebd9fda3169773610f0b1bfaf5bb`:
  installed identity matches the candidate; isolated staging service is active.
- Real installed browser acceptance at 1366×768, 1440×900, 1920×1080 and
  820×1180: 12 unique offering cards / six service roots; every root includes all
  its offerings; dedicated offering/form link; collapsed one-offering settings;
  cancellation preserves a local edit; accepted exit discards it; category picker
  explains its prerequisite, contains real subcategory options and preserves a
  chosen subcategory after selecting the offering;
  legacy catalog links redirect preserving service context. Primary catalog action
  is fully visible; no horizontal overflow. No settings/scenario save or publication.
- JavaScript errors: zero. Unexpected application request failures: zero.
  One external telemetry envelope request had `net::ERR_ABORTED` during deliberate
  full-page test navigation; it is recorded separately, not hidden as a Helpdesk
  API success or a telemetry-delivery acceptance claim.
- Sixteen screenshots and bound receipt:
  `artifacts/browser_checks/unified-catalog/112bead8eb46ebd9fda3169773610f0b1bfaf5bb/`.
  The new catalog was also opened and visibly verified in a separate in-app browser
  tab using the existing admin session; the user's forms tab was preserved.
- Installed frontend digest: `d4268a401779c69dabd40f45d68b47fce0124ec487cdee2e6a3292752297b1b6`.
  CI frontend digest: `bd3dc88935949adc7b2812e5dd44564c5cd35a5b056d60a134ae48bba1b054f3`.
  The canonical staging installer rebuilt committed source on Windows; these
  distinct digests are not claimed byte-equivalent. Production remains excluded.

The first CI run 38236185103 failed on outdated fixture navigation after three
successful layers; it stopped before the remaining layers. It is not a passing
full-gate receipt.

## Architecture and final state

GitNexus query/context/impact preceded implementation and were checked against
source/tests. This follow-up uses the existing Helpdesk Service Catalog and
requester form/scenario authorities; no cross-repository contract or Endpoint
operation behavior changed. No managed manifest or group synchronization edits.
The final documentation commit changes only this acceptance report and PLANS;
application/dependency/workflow object equivalence is verified separately. No
new application execution or deployment is claimed for that documentation SHA.
Tracked application changes are committed; unrelated pre-existing untracked
coverage, scanner and plan material remains untouched. Sonar is deferred.

## Limits

Sonar PR analysis remains deferred by the user; no successful Sonar gate is
claimed. No fresh backend coverage percentage is claimed for this follow-up.
The installed staging release is built by the reviewed canonical installer;
production artifact admission and deployment remain outside this task.
Historical full Studio acceptance stays in `GUIDED_REQUEST_STUDIO_ACCEPTANCE.md`;
it is not relabeled as a new execution at this follow-up revision.

## Commits

- `8624651263a8baa5d38f6d58a13605e669af1042` —
  `fix(studio): unify request catalog by offering` (31 files).
- `112bead8eb46ebd9fda3169773610f0b1bfaf5bb` —
  `fix(studio): complete offering navigation and status coverage` (7 files).

## Changed files

- `PLANS.md`
- `docs/GUIDED_REQUEST_STUDIO_ADMIN.md`
- `server/app/repos/request_scenario_repo.py`
- `server/docs/CODEMAP.md`
- `server/tests/test_request_scenario_admin_api.py`
- `server/tests/test_request_scenario_admin_contract.py`
- `server/tests/test_request_scenario_catalog_no_db.py`
- `server/tests/test_request_studio_unified_catalog.py`
- `server/tickets/request_scenario_catalog.py`
- `server/tickets/request_studio_catalog_projection.py`
- `server/web_api/request_scenario_admin_handlers.py`
- `webapp/src/app/navigation.tsx`
- `webapp/src/app/router.test.tsx`
- `webapp/src/app/router.tsx`
- `webapp/src/features/request-template-studio/offering-card.tsx`
- `webapp/src/features/request-template-studio/offering-details.test.tsx`
- `webapp/src/features/request-template-studio/offering-details.tsx`
- `webapp/src/features/request-template-studio/scenario-api.ts`
- `webapp/src/features/request-template-studio/scenario-catalog.tsx`
- `webapp/src/features/request-template-studio/scenario-purpose.test.tsx`
- `webapp/src/features/request-template-studio/scenario-purpose.tsx`
- `webapp/src/features/request-template-studio/scenario-simulation.test.tsx`
- `webapp/src/features/request-template-studio/unified-catalog.test.tsx`
- `webapp/src/features/request-template-studio/use-scenario-context.ts`
- `webapp/src/features/service-catalog/service-catalog-panel.test.tsx`
- `webapp/src/features/service-catalog/service-catalog-panel.tsx`
- `webapp/src/pages/admin/request-template-studio-catalog.test.tsx`
- `webapp/src/pages/admin/request-template-studio-page.test.tsx`
- `webapp/src/pages/admin/request-template-studio-page.tsx`
- `webapp/src/pages/admin/service-catalog-page.tsx`
- `webapp/tests/guided-category-inline.spec.ts`
- `webapp/tests/guided-diagnostics.spec.ts`
- `webapp/tests/guided-processing.spec.ts`
- `webapp/tests/guided-sections.spec.ts`
- `webapp/tests/guided-studio.spec.ts`
- `docs/UNIFIED_REQUEST_CATALOG_STAGING_ACCEPTANCE.md` (this final evidence report).

# Endpoint tools: installed staging preview

Date: 2026-10-12. User authorized immediate staging inspection, superseding
waiting for Guided Request Studio in main. This is an integrated preview, not
production readiness or completed live-Agent acceptance.

## Installed versions

- Helpdesk: `adf1f3843266abe21b8951a5032d9c42aaf97a69`, schema `148`.
- Endpoint: `8472d94f897c48041b718dafb84924b6cb73b86a`, schema `0037_launcher_foundation`.
- Helpdesk web digest: `b0f73eb7df9c520e07daf59b54cfbbeee7fb38607641ac62525519852dd2bdfd`.
- Local preview branch: `codex/endpoint-tools-staging-preview`; no Git publication
  or main integration was performed by this preview.
- Existing Guided application `2f2a2ec93b204466b1cf190308506262d2fb31e9` is retained
  through a merge; the additive migration chain is `146 → 147 → 148`.
- Both isolated staging services remain active for user inspection.

## Checks

- UTF-8 bootstrap, clean task worktree, diff checks and scoped workspace verification: PASS.
- Initial migration/cleanup checks: 46 PASS.
- Merged frontend: build/typecheck PASS, 124 files / 699 unit tests PASS.
- Fixture browser suite: 116 PASS, including four Endpoint-tools viewports and
  Guided/requester/SLA/profile/quality regression flows.
- Canonical selected server gate at exact installed Helpdesk SHA: seven layers
  GREEN, 2220 tests PASS (1363 no-DB, 5 physical migrations, 351 web API,
  382 tickets, 90 Observer/diagnostics, 29 runtime). No failures, errors or skips.
- Both staging databases: fresh custom-format backup, digest, isolated restore
  and exact restored Alembic revision verified before mutation. Restore databases
  removed; working staging data retained.
- Provider archive built with the canonical `build_console_server_archive.ps1`;
  staged source archive digest and all member paths validated. Provider install
  followed its reviewed runbook using isolated staging units/paths; a temporary
  migration-unit override was removed after the forward upgrade. Tested provider
  dependency versions were constrained; wsproto retained its existing staging version.
- Helpdesk installed through canonical `scripts/deploy_helpdesk_release.py`.
  Its installer built the accepted source; equivalence to a separate CI web
  archive is not claimed. Installed source identity, web digest, schema and
  service state were read back.
- Root-only scoped credential provisioning retained the old rollback credential
  and added only reviewed diagnostic scopes. Secret input remained in memory /
  protected stdin, output in private remote storage. No credential is evidence.

## Actual browser inspection

[Open the mapped staging ticket](https://helpdesk-staging.sosnadmin.local/app/tickets/88d71d02-c88c-403c-b28a-e65cdf49955d),
then **Инструменты → Диагностика**.

A separate protected synthetic administrator context used strict HTTPS and the
trusted CA, without fixtures or diagnostic mutations. At 1920 and 1366:

- New Endpoint panel visible; real catalog GET returned 200.
- One actually published module, `network.canary.check`, version `1.0.0`, with
  two provider-derived input controls. Parameters and selected-result region,
  general collection and run history rendered; no horizontal page overflow.
- Global navigation and ticket list collapsed independently; hidden search
  unmounted, chat composer remained visible.
- Catalog reason is `feature_disabled`: existing Endpoint module execution is
  disabled. Launch stayed disabled; no Agent command was issued.
- General collection exposes the actual six profiles in its BFF response.
- T-000019, the user's initially selected ticket, has no verified Endpoint device
  mapping. Its catalog returned the expected 409 `endpoint_device_mapping_missing`;
  the panel showed an error and chat remained available. No arbitrary device was
  attached to this ticket.
- Final browser receipt: zero unexpected console/page errors or failed requests.
  The missing-device 409 is an expected negative check.

Owned, ignored evidence is in
`.superpowers/sdd/2026-10-12-endpoint-tools-workspace/`: backup, provider/configuration,
installed identity, selected CI and `browser-preview/receipt.json` plus screenshots.
Synthetic browser contexts were closed after validation.

## Failures preserved and corrected

The first focused command referenced a nonexistent acceptance filename and ran
no tests. The second mixed physical-migration and ordinary DB tests in one process,
causing four fixture setup errors; it also correctly exposed a Studio rollback
assertion pinned to head147. That test now owns a separate temporary database and
explicitly rehearses147→146→147, preserving148's forward-only policy. The final
canonical split-layer run passed all2220 tests, including that regression.

Provider preparation first stopped before runtime mutation because wsproto was
absent from the isolated provider-test environment. Retry verified every prepared
archive file and retained the existing staging wsproto version. Old provider
remained active until preparation succeeded.

Two installed browser attempts used an overly exact label selector and stopped
before selection. Their response capture proved catalog200, not an application
failure. The corrected role selector completed the read-only flow. Windows fixture
pipe-close WinError10054 noise remains separate from product/browser failures.

## Limits

Published modules are authoritative; primitive support alone does not publish a
runnable recipe. Only the existing one published module is shown. This preview
neither publishes invented recipes nor proves DNS/ping execution or passport
attachment on an installed Agent. Endpoint execution remains disabled. Full
exact-SHA release CI / live-Agent acceptance remain required for production.
The local original tools implementation branch is preserved separately.

## Local commits and files

- `b6489115bfcf6679408bb6306aa611900e3de9be` —
  `feat(helpdesk): combine Endpoint tools with the staging Studio`.
  Imports the installed Guided source and resolves the shared CODEMAP/plans,
  cleanup-count and shell changes. Reattaches unreleased148 to147 and updates
  its regression/documentation; 149 files listed below.
- `adf1f3843266abe21b8951a5032d9c42aaf97a69` —
  `test(studio): isolate revision 147 rollback from later migrations`.
  File: `server/tests/test_request_scenario_persistence.py`.
- Provider source was unchanged from the independently reviewed local commit;
  its 471 Linux contract/auth/catalog tests passed in the earlier candidate gate.

```text
.github/tests/test_dev_scanner_candidate_workflow.py
.github/workflows/dev-scanner-quality.yml
PLANS.md
deploy/helpdesk/helpdesk.env.example
docs/GUIDED_REQUEST_STUDIO_ACCEPTANCE.md
docs/GUIDED_REQUEST_STUDIO_ADMIN.md
docs/INDEPENDENT_SERVICE_STAGING_ACCEPTANCE.md
docs/PILOT_RELEASE_GATE.md
docs/UNIFIED_REQUEST_CATALOG_STAGING_ACCEPTANCE.md
docs/superpowers/plans/2026-10-11-guided-request-studio-v2-progress.md
quality/db_table_classification.toml
scripts/reset_test_data.py
scripts/tests/test_reset_test_data_script.py
server/app/db/migrations/versions/20261011_147_guided_request_scenarios.py
server/app/db/migrations/versions/20261012_148_endpoint_tool_runs.py
server/app/db/models.py
server/app/db/request_scenario_models.py
server/app/repos/request_scenario_repo.py
server/app/repos/request_scenario_session_repo.py
server/docs/CODEMAP.md
server/docs/ENDPOINT_TOOLS_WORKSPACE.md
server/docs/GUIDED_REQUEST_SCENARIOS.md
server/docs/REQUEST_FORM_BUILDER.md
server/docs/SERVICE_CATALOG.md
server/routes.py
server/tests/conftest.py
server/tests/test_endpoint_tool_runs_migration.py
server/tests/test_request_scenario_admin_api.py
server/tests/test_request_scenario_admin_contract.py
server/tests/test_request_scenario_calendar_binding_api.py
server/tests/test_request_scenario_catalog_no_db.py
server/tests/test_request_scenario_contract.py
server/tests/test_request_scenario_diagnostic_api.py
server/tests/test_request_scenario_diagnostic_boundary.py
server/tests/test_request_scenario_escape.py
server/tests/test_request_scenario_offering_publication_api.py
server/tests/test_request_scenario_persistence.py
server/tests/test_request_scenario_processing.py
server/tests/test_request_scenario_processing_api.py
server/tests/test_request_scenario_publication_api.py
server/tests/test_request_scenario_queue_availability.py
server/tests/test_request_scenario_readiness.py
server/tests/test_request_scenario_runtime.py
server/tests/test_request_scenario_session_api.py
server/tests/test_request_scenario_session_contract.py
server/tests/test_request_scenario_submission.py
server/tests/test_request_scenario_submit_api.py
server/tests/test_request_studio_unified_catalog.py
server/tests/test_test_harness_no_db.py
server/tickets/create_flow.py
server/tickets/policy_health_service.py
server/tickets/request_scenario_catalog.py
server/tickets/request_scenario_conditions.py
server/tickets/request_scenario_pickers.py
server/tickets/request_scenario_processing.py
server/tickets/request_scenario_publication.py
server/tickets/request_scenario_readiness.py
server/tickets/request_scenario_runtime.py
server/tickets/request_scenario_session.py
server/tickets/request_scenario_submission.py
server/tickets/request_scenario_validation.py
server/tickets/request_studio_catalog_projection.py
server/tickets/request_studio_publication.py
server/tickets/service_catalog_preview.py
server/tickets/service_catalog_runtime.py
server/web_api/dto/request_scenario.py
server/web_api/dto/request_scenario_admin.py
server/web_api/dto/request_scenario_session.py
server/web_api/request_scenario_admin_handlers.py
server/web_api/request_scenario_handlers.py
server/web_api/requester_handlers.py
webapp/src/app/layouts/app-shell.tsx
webapp/src/app/navigation.tsx
webapp/src/app/router.test.tsx
webapp/src/app/router.tsx
webapp/src/features/auth/workspace-access.ts
webapp/src/features/request-template-studio/offering-card.tsx
webapp/src/features/request-template-studio/offering-details.test.tsx
webapp/src/features/request-template-studio/offering-details.tsx
webapp/src/features/request-template-studio/offering-publication.test.tsx
webapp/src/features/request-template-studio/offering-publication.tsx
webapp/src/features/request-template-studio/scenario-action-bar.test.tsx
webapp/src/features/request-template-studio/scenario-action-bar.tsx
webapp/src/features/request-template-studio/scenario-api.ts
webapp/src/features/request-template-studio/scenario-block-builder.test.tsx
webapp/src/features/request-template-studio/scenario-block-builder.tsx
webapp/src/features/request-template-studio/scenario-block-editor.tsx
webapp/src/features/request-template-studio/scenario-block-preview.test.tsx
webapp/src/features/request-template-studio/scenario-block-preview.tsx
webapp/src/features/request-template-studio/scenario-builder-model.test.ts
webapp/src/features/request-template-studio/scenario-builder-model.ts
webapp/src/features/request-template-studio/scenario-catalog.test.tsx
webapp/src/features/request-template-studio/scenario-catalog.tsx
webapp/src/features/request-template-studio/scenario-category-form.tsx
webapp/src/features/request-template-studio/scenario-condition-editor.test.tsx
webapp/src/features/request-template-studio/scenario-condition-editor.tsx
webapp/src/features/request-template-studio/scenario-contract.test.ts
webapp/src/features/request-template-studio/scenario-contract.ts
webapp/src/features/request-template-studio/scenario-diagnostics.ts
webapp/src/features/request-template-studio/scenario-field-editor.tsx
webapp/src/features/request-template-studio/scenario-field-group.test.tsx
webapp/src/features/request-template-studio/scenario-field-group.tsx
webapp/src/features/request-template-studio/scenario-form-page-editor.tsx
webapp/src/features/request-template-studio/scenario-issue-navigation.test.tsx
webapp/src/features/request-template-studio/scenario-issue-navigation.ts
webapp/src/features/request-template-studio/scenario-offering-form.test.tsx
webapp/src/features/request-template-studio/scenario-offering-form.tsx
webapp/src/features/request-template-studio/scenario-preview-panel.tsx
webapp/src/features/request-template-studio/scenario-processing-result.tsx
webapp/src/features/request-template-studio/scenario-processing.test.tsx
webapp/src/features/request-template-studio/scenario-processing.tsx
webapp/src/features/request-template-studio/scenario-publication-summary.tsx
webapp/src/features/request-template-studio/scenario-publication.test.tsx
webapp/src/features/request-template-studio/scenario-publication.tsx
webapp/src/features/request-template-studio/scenario-purpose.test.tsx
webapp/src/features/request-template-studio/scenario-purpose.tsx
webapp/src/features/request-template-studio/scenario-separated-input.tsx
webapp/src/features/request-template-studio/scenario-simulation.test.tsx
webapp/src/features/request-template-studio/scenario-simulation.tsx
webapp/src/features/request-template-studio/scenario-version-history.test.tsx
webapp/src/features/request-template-studio/scenario-version-history.tsx
webapp/src/features/request-template-studio/scenario-wizard.tsx
webapp/src/features/request-template-studio/unified-catalog.test.tsx
webapp/src/features/request-template-studio/use-scenario-context.ts
webapp/src/features/request-template-studio/use-scenario-dirty-guard.ts
webapp/src/features/request-template-studio/use-scenario-editor.test.tsx
webapp/src/features/request-template-studio/use-scenario-editor.ts
webapp/src/features/requester/scenario-fields.tsx
webapp/src/features/requester/scenario-session.test.tsx
webapp/src/features/requester/scenario-session.tsx
webapp/src/features/requester/types.ts
webapp/src/features/service-catalog/service-catalog-panel.test.tsx
webapp/src/features/service-catalog/service-catalog-panel.tsx
webapp/src/pages/admin/request-template-studio-catalog.test.tsx
webapp/src/pages/admin/request-template-studio-page.test.tsx
webapp/src/pages/admin/request-template-studio-page.tsx
webapp/src/pages/admin/service-catalog-page.tsx
webapp/src/pages/admin/service-create-page.test.tsx
webapp/src/pages/admin/service-create-page.tsx
webapp/src/pages/admin/template-create-page.test.tsx
webapp/src/pages/admin/template-create-page.tsx
webapp/src/pages/requester/new-request-page.test.tsx
webapp/src/pages/requester/new-request-page.tsx
webapp/tests/guided-category-inline.spec.ts
webapp/tests/guided-diagnostics.spec.ts
webapp/tests/guided-processing.spec.ts
webapp/tests/guided-requester.spec.ts
webapp/tests/guided-sections.spec.ts
webapp/tests/guided-studio.spec.ts
```

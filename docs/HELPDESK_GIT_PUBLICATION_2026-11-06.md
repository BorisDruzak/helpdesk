# Helpdesk Git publication — 2026-11-06

## Candidate and scope

Target: `origin/codex/ui-support-001` in `BorisDruzak/helpdesk`.
The starting checkout is `31f81cec70d46591c59a55bbdd60f99d3a284919`.
The integration retains the feature history ending at
`212e5e302f7df633fc0c74f1963b128394270653`, together with the Studio
acceptance documentation already present on the active branch. No existing
commit is amended or rebased. The source snapshot preserves the current local
catalog, requester, user administration, notification, deployment and test work.

The independently developed features remain separate commits: service/symptom
search, pinned requester decisions, stopped-resolution SLA, editing spaces,
public reopen reasons, optional screenshots, unified Users administration,
transactional bell/Web Push and active-chat attention handling. The integration
also includes their local acceptance records and current plans/CODEMAP.

The user explicitly authorized the review repairs before publication:

- Reuse validated stored/normalized UI identity aliases for notification
  recipients, inbox reads/acknowledgements, browser ownership/fanout and
  preferences. Deduplicate queue/assignee overlap and preserve self suppression.
  Unknown principals stay exact-only; ambiguous UI identities fail closed.
- Correct stale requester-shell assertions and supply explicit public-message
  permissions in upload fixtures. Race tests now prove uploads start before
  switching tickets; denied/unassigned/resolved/closed states remain covered.
- Give five browser fixtures an explicit disabled push configuration, retaining
  their unexpected-request and console-error assertions.
- Replace nine private screenshot embeds in the historical UX audit with plain
  local evidence references so GitHub does not render broken images.

## Verification

- `python scripts/bootstrap_web_toolchain.py`: passed.
- `python scripts/verify_workspace.py`: passed after repairs.
- `pnpm --dir webapp test --maxWorkers=2`: **1072 passed / 173 files**.
- `pnpm --dir webapp run build --outDir C:/Users/admin-2/CodexProjects/pc_client/artifacts/browser_checks/git-update-20261106/dist`:
  passed, including TypeScript. Vite reports its existing large-chunk warning.
- `pnpm --dir webapp exec playwright test tests/browser-notifications.spec.ts tests/catalog-service-search.spec.ts tests/requester-optional-screenshots.spec.ts tests/requester-resolution-actions.spec.ts tests/requester-text-spaces.spec.ts tests/unified-users.spec.ts --timeout 20000 --output C:/Users/admin-2/CodexProjects/pc_client/artifacts/browser_checks/git-update-20261106/e2e-final`:
  **32 passed**. The child environment selects the isolated built dist above and
  fixture port4193. Desktop/mobile assertions cover the changed flows, unexpected
  browser/API errors and document overflow. Representative notification intro
  and Users screenshots were visually inspected.
- Focused Python catalog/scenario/reopen/workflow/notification/repair/deploy
  checks: **175 passed, 1 skipped** (`Linux flock proof runs during staging acceptance`).
- Disposable PostgreSQL account/access/registry/queue/SSO/approval/push checks:
  **95 passed**. The initial command also included the schema layer and reported
  four setup errors after that layer replaced the session database; migration
  verification was then rerun in its documented separate process.
- `python scripts/run_with_local_postgres.py -- python -m pytest server/tests/test_migration_schema_contract.py -q --tb=short`:
  **8 passed**, including fresh upgrade/schema contracts. Owned cluster stopped.
- `python scripts/run_with_local_postgres.py -- python -m pytest server/tests/test_notification_actor_aliases.py server/tests/test_web_push_persistence.py server/tests/test_stage8.py server/tests/test_ticket_notification_policy.py server/tests/test_notification_scope_no_db.py -q --tb=short`:
  **50 passed** in the final independent rerun; owned cluster stopped. Identity
  failures were reproduced before repair; the final alias-only suite passed15
  cases. Preferences cover historical normalized rows and suppress-self override.
- Additional notification no-DB/policy suite: **45 passed**.
- `python scripts/audit_test_inventory.py --strict`: passed,421 files/zero issues.
- `python scripts/audit_db_cleanup_profiles.py --strict`: passed,zero missing profiles.
- `git diff --check`: passed; independent final review has no remaining findings.
- Credential-pattern review of candidate source and documentation found no
  suspected real credentials. Generated/runtime files are excluded.

## Limits and operational impact

This is a Git publication. No deployment, production/staging database mutation,
role grant or remote service lifecycle action is performed. Local fixture servers
and disposable PostgreSQL clusters stop with their owned checks. Full CI and a
new live staging/production signoff were not requested or run. Browser results
above are fixture evidence; earlier live staging receipts remain historical.

The included existing Web Push feature introduces migration156 and requires
canonical deployment plus private VAPID configuration when activated. No private
key or runtime configuration is published. The new alias repair requires a later
deployment to affect a running service; no Endpoint HTTP contract changes occur.

GitNexus MCP is unavailable in this session; architecture and dynamic actor
boundaries were reviewed against source/tests and matching docs/CODEMAP.
SQLAlchemy2.0 IN/empty-IN behavior was checked through Context7; repository range
is `>=2.0,<2.1`, installed version2.0.51. Existing Authlib deprecation and occasional
Windows fixture connection-reset cleanup warnings remain; browser assertions pass.

Local `tmp/`, `.scannerwork/`, machine-specific Sonar configuration, loose PNGs and
`design-qa.md` remain outside the publication.

## Files included in the integration snapshot

- `PLANS.md`
- `docs/ADMIN_USERS_STAGING_ACCEPTANCE_2026-11-06.md`
- `docs/ADMIN_USERS_VERIFICATION_2026-11-06.md`
- `docs/ADMIN_USERS_WORKSPACE.md`
- `docs/BROWSER_NOTIFICATIONS.md`
- `docs/BROWSER_NOTIFICATIONS_STAGING_ACCEPTANCE_2026-11-06.md`
- `docs/CATALOG_SERVICE_SEARCH_2026-11-05.md`
- `docs/CATALOG_SYMPTOM_SEARCH_2026-11-05.md`
- `docs/HELPDESK_GIT_PUBLICATION_2026-11-06.md`
- `docs/NOTIFICATION_ATTENTION_STAGING_ACCEPTANCE_2026-11-06.md`
- `docs/OPTIONAL_SCREENSHOTS_2026-11-06.md`
- `docs/REQUESTER_CONFIRM_CONTROLS_2026-11-05.md`
- `docs/REQUESTER_REOPEN_MESSAGES_2026-11-06.md`
- `docs/REQUESTER_TEXT_SPACES_FIX_2026-11-06.md`
- `docs/SLA_CONFIRMATION_FIX_2026-11-06.md`
- `docs/UX_PHASE1_AUDIT_2026-11-02.md`
- `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`
- `docs/superpowers/plans/2026-10-27-sso-worktime.md`
- `docs/superpowers/plans/2026-10-30-worktime-staging-navigation.md`
- `docs/superpowers/plans/2026-11-05-catalog-symptom-search.md`
- `docs/superpowers/plans/2026-11-06-browser-notifications.md`
- `docs/superpowers/plans/2026-11-06-notification-attention-fixes.md`
- `docs/superpowers/plans/2026-11-06-unified-users.md`
- `docs/superpowers/specs/2026-11-06-unified-users-design.md`
- `quality/db_table_classification.toml`
- `scripts/configure_helpdesk_web_push.py`
- `scripts/deploy_helpdesk_release.py`
- `scripts/generate_web_push_key.py`
- `scripts/helpdesk_catalog_service_search.py`
- `scripts/helpdesk_optional_screenshot_stage.py`
- `scripts/helpdesk_recover_t77_reopen_messages.py`
- `scripts/helpdesk_repair_t75_sla.py`
- `scripts/reset_test_data.py`
- `scripts/test_configure_helpdesk_web_push.py`
- `scripts/test_deploy_helpdesk_release.py`
- `scripts/test_helpdesk_catalog_service_search.py`
- `scripts/test_helpdesk_optional_screenshot_stage.py`
- `scripts/test_helpdesk_recover_t77_reopen_messages.py`
- `scripts/test_helpdesk_repair_t75_sla.py`
- `server/.env.example`
- `server/app/db/migrations/versions/20261106_156_web_push.py`
- `server/app/db/models.py`
- `server/app/db/web_push_models.py`
- `server/app/repos/access_control_repo.py`
- `server/app/repos/notification_prefs_repo.py`
- `server/app/repos/notification_repo.py`
- `server/app/repos/ticket_admin_config_repo.py`
- `server/app/repos/ticket_events_repo.py`
- `server/app/repos/ui_actor_memberships.py`
- `server/app/repos/web_push_repo.py`
- `server/app/services/user_accounts.py`
- `server/app/services/web_push_dispatcher.py`
- `server/docs/CODEMAP.md`
- `server/docs/GUIDED_REQUEST_SCENARIOS.md`
- `server/docs/QUALITY_LOOP.md`
- `server/docs/SERVICE_CATALOG.md`
- `server/quality/reopen_message.py`
- `server/quality/reopen_service.py`
- `server/routes.py`
- `server/server.py`
- `server/static_pages/webapp_assets.py`
- `server/tests/conftest.py`
- `server/tests/test_browser_notifications_no_db.py`
- `server/tests/test_notification_actor_aliases.py`
- `server/tests/test_notification_attention_api_no_db.py`
- `server/tests/test_notification_scope_no_db.py`
- `server/tests/test_request_scenario_optional_evidence.py`
- `server/tests/test_requester_reopen_message_no_db.py`
- `server/tests/test_service_catalog_search.py`
- `server/tests/test_stage8.py`
- `server/tests/test_ticket_notification_policy.py`
- `server/tests/test_user_account_provider.py`
- `server/tests/test_web_push_api_no_db.py`
- `server/tests/test_web_push_no_db.py`
- `server/tests/test_web_push_persistence.py`
- `server/tests/test_workflow_update_builder_no_db.py`
- `server/tickets/browser_notifications.py`
- `server/tickets/handlers.py`
- `server/tickets/notification_scope.py`
- `server/tickets/notification_service.py`
- `server/tickets/request_scenario_optional_evidence.py`
- `server/tickets/request_scenario_runtime.py`
- `server/tickets/request_scenario_submission.py`
- `server/tickets/service_catalog_runtime.py`
- `server/tickets/service_catalog_search.py`
- `server/tickets/web_push.py`
- `server/tickets/workflow_service.py`
- `server/web_api/access_handlers.py`
- `server/web_api/dto/user_account.py`
- `server/web_api/push_handlers.py`
- `server/web_api/quality_handlers.py`
- `server/web_api/requester_handlers.py`
- `server/web_api/support_handlers.py`
- `server/web_api/user_account_handlers.py`
- `webapp/public/helpdesk-notifications-sw.js`
- `webapp/src/app/navigation.test.ts`
- `webapp/src/app/navigation.tsx`
- `webapp/src/app/router.test.tsx`
- `webapp/src/app/router.tsx`
- `webapp/src/app/routes/lazy-pages.tsx`
- `webapp/src/components/shell/app-sidebar.test.tsx`
- `webapp/src/components/shell/app-topbar.test.tsx`
- `webapp/src/components/shell/app-topbar.tsx`
- `webapp/src/features/admin/registry/registry-import-dialog.tsx`
- `webapp/src/features/admin/registry/registry-overview-tab.test.tsx`
- `webapp/src/features/admin/registry/registry-overview-tab.tsx`
- `webapp/src/features/admin/registry/registry-person-tools.tsx`
- `webapp/src/features/admin/registry/registry-workspace-dialogs.tsx`
- `webapp/src/features/admin/registry/registry-workspace-tabs.ts`
- `webapp/src/features/admin/registry/registry-workspace.tsx`
- `webapp/src/features/admin/registry/use-registry-workspace.ts`
- `webapp/src/features/auth/session-provider.tsx`
- `webapp/src/features/notifications/active-chat.test.tsx`
- `webapp/src/features/notifications/api.ts`
- `webapp/src/features/notifications/browser-push-control.tsx`
- `webapp/src/features/notifications/browser-push.test.ts`
- `webapp/src/features/notifications/browser-push.ts`
- `webapp/src/features/notifications/notification-bell.tsx`
- `webapp/src/features/notifications/notification-introduction.test.tsx`
- `webapp/src/features/notifications/notification-introduction.tsx`
- `webapp/src/features/notifications/notification-menu.test.tsx`
- `webapp/src/features/notifications/notification-menu.tsx`
- `webapp/src/features/notifications/use-active-chat-notifications.ts`
- `webapp/src/features/requester/catalog-search-api.ts`
- `webapp/src/features/requester/catalog-search.test.tsx`
- `webapp/src/features/requester/catalog-search.tsx`
- `webapp/src/features/requester/dynamic-form/dynamic-form.test.tsx`
- `webapp/src/features/requester/dynamic-form/index.tsx`
- `webapp/src/features/requester/scenario-entrances.test.tsx`
- `webapp/src/features/requester/scenario-entrances.tsx`
- `webapp/src/features/requester/scenario-session.test.tsx`
- `webapp/src/features/requester/types.ts`
- `webapp/src/features/settings/api.ts`
- `webapp/src/features/users/account-editor.tsx`
- `webapp/src/features/users/api.ts`
- `webapp/src/features/users/create-person-dialog.tsx`
- `webapp/src/features/users/model.ts`
- `webapp/src/features/users/permissions-fields.tsx`
- `webapp/src/features/users/profile-panel.tsx`
- `webapp/src/features/users/unlinked-account.tsx`
- `webapp/src/features/users/user-card.tsx`
- `webapp/src/features/users/users-fixtures.ts`
- `webapp/src/features/users/users-list.tsx`
- `webapp/src/pages/admin/registry-page.test.tsx`
- `webapp/src/pages/admin/registry-page.tsx`
- `webapp/src/pages/admin/users-page.test.tsx`
- `webapp/src/pages/admin/users-page.tsx`
- `webapp/src/pages/admin/users-registry-roundtrip.test.tsx`
- `webapp/src/pages/requester/new-request-page.tsx`
- `webapp/src/pages/requester/ticket-chat-page.test.tsx`
- `webapp/src/pages/requester/ticket-chat-page.tsx`
- `webapp/src/pages/requester/tickets-panels.tsx`
- `webapp/src/pages/tickets/components/simple-support-conversation.tsx`
- `webapp/src/pages/tickets/list-page.test.tsx`
- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/pages/tickets/sections/TicketConversationWorkspace.tsx`
- `webapp/tests/browser-notifications.spec.ts`
- `webapp/tests/catalog-service-search.spec.ts`
- `webapp/tests/fixtures/notification_fixture.py`
- `webapp/tests/fixtures/support_fixture_server.py`
- `webapp/tests/requester-optional-screenshots.spec.ts`
- `webapp/tests/requester-resolution-actions.spec.ts`
- `webapp/tests/requester-text-spaces.spec.ts`
- `webapp/tests/unified-users.spec.ts`

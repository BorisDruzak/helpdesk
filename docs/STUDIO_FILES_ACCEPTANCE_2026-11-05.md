# Studio instruction and answer files: staging acceptance

Verified on 2026-11-05. Feature commit:
`dc60f34573602be834bfeebbf58424db6ccbb929`
(`feat(studio): attach files to instructions and requester answers`).
Branch: `codex/ui-support-001`.

## Result

Studio authors can attach images and other files to instruction blocks and
text-field help. Employees can attach files to text/textarea answers. Picker,
drag/drop and native screenshot Ctrl+V feed the same scoped upload queue; mixed
clipboard text stays editable. Images have thumbnails and an in-app viewer;
other files remain downloadable. Files can be removed before submission.
Limits are ten files per instruction/field and 200 MiB per file.

Existing editor autosave remains unchanged. Upload does not submit a request,
advance a wizard or publish a scenario. Explicit submission atomically transfers
retained visible answer files into ticket artifacts, the initial conversation
event and per-field context. Hidden/abandoned answers are excluded. Create copy
rebases material ownership and retains idempotent retries without accepting
generic foreign references. Required text validation remains unchanged; this is
supplementary attachment support, not a standalone file-answer field type.

Chat clipboard support for both roles was delivered separately in
`ff8db7ec972745fe0b0731a93380942b5eda157b`
(`feat(chat): attach pasted screenshots to reply drafts`):
[chat acceptance](CHAT_CLIPBOARD_ACCEPTANCE_2026-11-05.md).

## Verification

- `python -m pytest server/tests/test_request_scenario_assets.py server/tests/test_request_scenario_contract.py server/tests/test_request_scenario_submission.py server/tests/test_request_scenario_runtime.py server/tests/test_request_scenario_session_contract.py -q --tb=short`: **137 passed**, one existing Authlib deprecation warning.
- `python -m pytest scripts/tests/test_reset_test_data_script.py scripts/test_audit_db_cleanup_schema.py -q --tb=short`: **12 passed**.
- `npm test --prefix webapp -- src/features/requester/scenario-attachments.test.tsx src/features/requester/scenario-session-attachments.test.tsx src/features/request-template-studio`: **49 files / 208 tests passed** after final copy changes. Earlier broader isolated regression: **53 files / 264 tests passed**; these overlapping suites are not additive.
- Frozen frontend `pnpm run build`: TypeScript and Vite passed, both in the isolated source export and canonical deployment archive.
- `PC_CLIENT_WEBAPP_E2E_PORT=14181 PC_CLIENT_WEBAPP_E2E_DIST=<frozen-dist> pnpm --dir webapp exec playwright test tests/studio-files.spec.ts --output ../tmp/studio-files-20261105/browser-complete`: **6 passed**. Desktop/mobile author materials, requester files, reload/back/remove/review/submit, native mixed image/text paste and copy ownership passed. Happy paths had no console/page/network errors or material horizontal overflow. Fixture server stopped afterward.
- Isolated PostgreSQL on approved staging: corrected asset/purge suites **12 passed**, separate copy roundtrip/retry/forgery case **1 passed**. Earlier broad run also passed **26 existing scenario regressions**. Its author-upload fixture incorrectly used a support bearer and received the expected403; the corrected author fixture passed in the final run. Temporary databases and roles were removed.
- `python scripts/verify_workspace.py`, `python scripts/export_request_scenario_schema.py --output docs/contracts/request-scenario.schema.json --check`, scoped `git diff --check`: passed.
- Independent backend/frontend/copy review: no remaining findings. Review-discovered purge FK and premature filesystem unlink risks were fixed and covered before deployment. GitNexus architectural baseline and source/tests were checked; no new cross-repository contract or dependency was introduced.

The strict DB classification audit still reports three pre-existing unclassified
tables (`web_requester_registrations`, `worktime_authorization_codes`,
`worktime_session_leases`). New Studio classification is present; cleanup-risk
checks reported no static/dynamic/FK risks. Full CI was not run.

## Deployment and live evidence

Canonical `python tmp/phase1_deploy_staging.py dc60f34573602be834bfeebbf58424db6ccbb929`
installed the frozen commit after a verified schema154 backup, SHA256
`113ba8ca7d9b3ac6457f13581566fb43582ce123776f0591dcb5c30d57acc33b`.
Migration155 creates separately scoped `request_studio_assets`; the existing
Artifact device-or-ticket constraint remains intact.

Another authorized task subsequently installed descendant
`860c5677f26f5aabc575089819cfa41da1782124` on the same staging service.
Final checks confirmed that runtime, schema155 and **all48 non-PLANS files from
this feature still match dc60**. Helpdesk and Endpoint strict-TLS health returned
HTTP200; all three staging services were active; temporary test-role/known-orphan
DB counts were zero. Staging was left running. Business counts are observations,
not an unchanged-state claim, because other authorized work continued concurrently.

Live browser proof used only a new synthetic, **unpublished** author draft:
`STUDIO-FILES-001 — проверка вложений (черновик)`. PNG and TXT instruction
materials persisted after reload. The in-app PNG viewer returned HTTP200,
`image/png`, and decoded at520×130; console errors were zero. An earlier viewer
attempt failed during a parallel staging restart; its response status was not
captured. Reopening afterward passed, with matching DB/filesystem hashes.
The private draft and its two benign assets remain available for review.
No real ticket, employee answer submission or publication command was executed
during this live author check. Requester submission was verified in browser
fixtures and isolated PostgreSQL, not claimed as a live employee acceptance.

Successful screenshot: `tmp/studio-files-20261105/staging-instruction-preview.png`.
Machine evidence: `installed-current.json`, `browser-live.json`, `deploy.log`,
`backend-copy-final-units.log`, `db-focused.log`, `db-copy.log`,
`browser-complete.log`, `build-copy-final.log` under that evidence directory;
final Studio unit output is in
`tmp/studio-files-frontend-evidence/copy-provenance-studio-green.log`.
Earlier failed/intermediate logs are retained but are not acceptance results.

## Lifecycle and remaining limits

Download/upload/remove retain role, owner, session expiry/revocation, current
block/revision and visibility checks. Safe canonical URLs, bounded streaming and
image content headers are enforced. Purge releases Studio ownership transactionally
and unlinks eligible blobs only after confirmed commit; author/shared material is
retained. No dummy ticket/device or relaxed Artifact scope was introduced.

Expired unsubmitted files have a bounded maintenance command, with explicit
runtime database/environment and **dry-run by default**:
`python server/scripts/cleanup_request_scenario_assets.py --limit 100 --grace-hours 24`.
No automatic cleanup timer was added. Applying cleanup requires `--apply`;
author/version materials, ticket files and unexpired sessions are retained.

Migration155 downgrade refuses while asset rows exist. Rollback was not performed;
do not deploy an old purge implementation unaware of the new FK onto this data.
Rollback requires a reviewed compatible release or controlled backup restoration.
Production and Endpoint code/configuration were not changed. Unrelated working
copy changes and other tasks' releases were preserved. No push was performed.

## Files in the feature commit

- `PLANS.md`
- `docs/GUIDED_REQUEST_STUDIO_ADMIN.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`
- `docs/REQUEST_STUDIO_USER_GUIDE_RU.md`
- `docs/contracts/request-scenario.schema.json`
- `docs/superpowers/plans/2026-11-05-studio-attachments.md`
- `quality/db_table_classification.toml`
- `scripts/reset_test_data.py`
- `scripts/tests/test_reset_test_data_script.py`
- `server/app/db/request_scenario_models.py`
- `server/app/db/migrations/versions/20261105_155_request_studio_assets.py`
- `server/app/repos/request_scenario_repo.py`
- `server/app/repos/request_scenario_session_repo.py`
- `server/docs/ARTIFACTS_API.md`
- `server/docs/CODEMAP.md`
- `server/docs/GUIDED_REQUEST_SCENARIOS.md`
- `server/routes.py`
- `server/scripts/cleanup_request_scenario_assets.py`
- `server/tests/conftest.py`
- `server/tests/test_request_scenario_assets.py`
- `server/tests/test_request_scenario_assets_api.py`
- `server/tests/test_request_scenario_asset_purge_api.py`
- `server/tests/test_request_scenario_asset_copy_api.py`
- `server/tickets/purge_service.py`
- `server/tickets/request_scenario_assets.py`
- `server/tickets/request_scenario_publication.py`
- `server/web_api/dto/request_scenario.py`
- `server/web_api/dto/request_scenario_admin.py`
- `server/web_api/request_scenario_asset_handlers.py`
- `server/web_api/request_scenario_admin_handlers.py`
- `server/web_api/support_handlers.py`
- `webapp/tests/studio-files.spec.ts`
- `webapp/tests/fixtures/support_fixture_server.py`
- `webapp/src/components/chat-attachment.tsx`
- `webapp/src/features/request-template-studio/scenario-api.ts`
- `webapp/src/features/request-template-studio/scenario-author-attachments.tsx`
- `webapp/src/features/request-template-studio/scenario-block-editor.tsx`
- `webapp/src/features/request-template-studio/scenario-contract.ts`
- `webapp/src/features/request-template-studio/scenario-field-editor.tsx`
- `webapp/src/features/request-template-studio/scenario-requester-preview.tsx`
- `webapp/src/features/request-template-studio/scenario-wizard.tsx`
- `webapp/src/features/requester/scenario-attachments.tsx`
- `webapp/src/features/requester/scenario-attachments.test.tsx`
- `webapp/src/features/requester/scenario-fields.tsx`
- `webapp/src/features/requester/scenario-session.tsx`
- `webapp/src/features/requester/scenario-session-attachments.test.tsx`
- `webapp/src/features/requester/scenario-step-content.tsx`
- `webapp/src/features/request-template-studio/use-scenario-editor.ts`
- `webapp/src/features/request-template-studio/use-scenario-editor.test.tsx`

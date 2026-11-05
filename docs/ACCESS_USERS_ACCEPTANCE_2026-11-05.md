# Access user cleanup and display-name acceptance, 2026-11-05

## Observed causes

Requester handling gets the specialist from the ticket's `assignee_id`, verifies
that Helpdesk account is support/admin, then reads the Registry person attached
through its verified `ui_login` alias. On staging, `admin` was linked to a person
whose full/display name was the fixture “Тестовый Пользователь 1”. The screenshot
therefore reflected stored profile data, not the requester or agent's name.

The admin Access Control table literally rendered “Не передано API” for every
row; its API DTO had no display-name field. This was an unfinished UI/API contract,
not a failed network request. The new shared batch name resolver uses verified
UI aliases, full name/display name/login in that order, with no identity inference.
Admin API adds optional `users[].display_name`; table display/search uses it.

## Frozen source and checks

Branch `codex/ui-support-001`, frozen commit
`41c751623ac9f25038c7d8ff8a0ae49cd8a51621`,
`fix(access): show verified names and retire staging fixtures`.
16 task files: shared display service, requester handling, access handler/DTO,
four access frontend modules and component test, guarded maintenance script and
three test files, CODEMAP/procedure and own PLANS section. Unrelated dirty work
remains unstaged. No dependency or schema changes; no push/PR or production work.

- 13 frontend tests passed:
  `pnpm --dir webapp test src/pages/admin/access-page.test.tsx src/pages/requester/ticket-context-panel.test.tsx`.
- 15 pure backend tests passed:
  `python -m pytest server/tests/test_requester_ticket_handling_no_db.py server/tests/test_support_workspace_projection_no_db.py -q`.
- 7 maintenance guard/lifecycle tests passed:
  `python -m pytest scripts/test_helpdesk_staging_user_cleanup.py -q`.
- 3 PostgreSQL/API tests passed in fresh disposable databases through the existing
  staging test harness: `server/tests/test_access_user_display_db.py`,
  `server/tests/test_requester_ticket_handling_db.py` and
  `server/tests/test_staging_user_cleanup_db.py`. Disposable roles/DBs removed.
  They cover verified/unverified names, support403, safe requester context,
  protected passwords/roles, revocation/audit, plan mismatch and harmless rerun.
- `pnpm --dir webapp build`, `python scripts/verify_workspace.py`, diff checks
  pass. Existing Authlib deprecation warning remains. Full CI/fleet/production
  gates were outside this targeted staging task.
- Built-browser fixtures at1366x768 and390x844 pass: real profile-name rendering
  and search, active default, disabled explicit filter, no document overflow
  (390px), zero page exceptions. Private screenshots in
  `tmp/access-cleanup-20261105/access-fixture-{desktop,mobile}.png`.
- Independent read-only review found/fixed a standalone DB lifecycle omission.
  Regression reproduced it RED; initialization and disposal on init/read errors
  now pass. Final review found no remaining blocker. GitNexus committed baseline
  and source verified identity/access boundaries; Context7 SQLAlchemy2.0 docs
  consulted for the batch/transaction API. No external provider contract changed.

## Guarded staging data action

Approved isolated host `osn-admin@192.168.101.118` only. Canonical verified private
backup at PostgreSQL153, source `1ba7c8166e1d0317479a965dcf63b1b7d2accd3a`:
13617404 bytes, SHA256
`4a0262d21687351190a74e3bb864e5009342ae62e2121424bee2bd3c57516ca0`.
Private receipt `/var/backups/helpdesk-access-cleanup-20261105/backup.json`.

The committed maintenance script ran through the protected staging transport,
using the exact read-only plan fingerprint and verified backup.159 accounts were
retained; active count18→3, disabled141→156. Preserved active accounts/roles:
`admin` (admin), `admin-2` (admin), `bdryzhak` (user).
15 previously active synthetic accounts were disabled;255 previously non-revoked
UI token records for the156 candidates were revoked through canonical helper/audit.
This token count is not a count of live sessions. The exact fixture label on the
already verified admin person was replaced by display `admin` and unset full name;
no new name, person or binding was inferred.

Pre/post-action seals match for tickets, ticket events, Registry identities and
protected accounts' login/role/password hash/active state. Memberships, people,
authors and historical snapshots remain; no business/ticket rows were deleted.
The UI's working list uses Active by default; disabled accounts remain explicitly
inspectable through its filter. Restoring any access is a separate admin action;
revoked sessions remain revoked. See the maintenance procedure for safeguards.

## Deployment and live UI

Initial canonical release41c751623ac9f25038c7d8ff8a0ae49cd8a51621 passed installed
nine-file hash readback, schema153, strict TLS200, three active services and
unchanged history/protected-account seals. Live overview then exposed an older
metric issue: disabled accounts inflated users/elevated-role counts. Follow-up
`e0ff50496442801a9fc5eb143af406d02a991a23`,
`fix(access): count active accounts in overview metrics`, changes only the
overview, its regression and the procedure. The old count was reproduced RED;
13 frontend tests and build passed again; independent review found no issue.

Both releases use canonical `scripts/deploy_helpdesk_release.py` through the
fixed staging transport, committed Git archives and frozen-lockfile local builds.
Fresh backup before the overview release (schema153/source41c75162):13456401
bytes, SHA256 `e3ddc6a07200045b01f821a98e78ae56260dfa7f236d09b84319be88565bcdb2`.
Final runtime and live acceptance follow below. Staging is explicitly left
running. Endpoint/native agent and production are unchanged.

Final installed selector:
`/opt/helpdesk-staging/releases/helpdesk-e0ff50496442801a9fc5eb143af406d02a991a23`.
Ten runtime source files match frozen Git by normalized-LF SHA256; schema remains
153. Strict CA/hostname health checks return200 for Helpdesk and Endpoint.
`helpdesk-staging.service`, `endpoint-staging.service` and
`endpoint-staging-worker.service` are active and explicitly left running.
Final history/protected-account seals still match the pre-cleanup baseline.

Authenticated real `admin` browser session at `/app/admin/access` accepted the
overview (3 active users,2 elevated accounts) and users tab (exactly3 user action
rows). Names are `admin`, `admin-2`, Дрыжак Борис Николаевич (`bdryzhak`).
The API-error placeholder count is0; final error/warning console list is empty.
No password, group, role or other UI business action was submitted. Live screenshot:
`tmp/access-cleanup-20261105/live-access-users.jpg`.
The temporary local preview stopped; user browser tabs/drafts were preserved.
Private evidence/receipts: `tmp/access-cleanup-20261105/`.

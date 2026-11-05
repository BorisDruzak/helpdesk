# Helpdesk → WorkTime: staging acceptance, 2026-11-05

## Result and scope

Accepted on the approved isolated host `osn-admin@192.168.101.118` only.
The existing complete local Helpdesk employee `bdryzhak` clicked **Рабочее время**
and reached `/employee` in WorkTime without entering another password. The day
loaded again after browser reload. No workday transition, correction, explanation,
device link, AD binding or privileged grant was submitted during acceptance.

Helpdesk offers **Войти через AD** alongside its existing password entry and
employee registration. WorkTime offers **Войти через Helpdesk** and **Войти через
AD**. An anonymous WorkTime user follows the former to Helpdesk login with a
closed continuation, without a redirect loop. Registration still opens the
completed employee cabinet; creating a ticket remains an explicit separate action.

## Frozen sources and deployment

Helpdesk branch `codex/ui-support-001`:

- `7d8dda5d814e88c40d5eac2dfa1e7324135638f3`
  `feat(auth): authorize WorkTime handoff from Helpdesk sessions`.
- Installed selector `/opt/helpdesk-staging/releases/helpdesk-7d8dda5d814e88c40d5eac2dfa1e7324135638f3`.
- PostgreSQL revision **153**, previously152. Canonical
  `scripts/deploy_helpdesk_release.py` used through the fixed staging transport;
  frontend built from the committed archive with its frozen lockfile.
- Fresh verified private DB backup: SHA256
  `84824e11e9c8d8f79edeba39f318a3bf98953276bbeda42f955152e384cbbde2`,
  13,470,404 bytes; pre-migration152. Backup marker remains private on the host.

Endpoint branch `codex/worktime-helpdesk-login`, reused isolated staging-baseline
worktree `C:/Users/admin-2/Documents/endpoint/.worktrees/worktime-recorded-release-20261030`:

- `2a7c3ddc937c9e28b6b9990f765e4a5ceb40ae51`
  `fix(auth): keep emergency session within its approved deadline`.
- `55bd00103765efb2225b13ec9b428fd120a92de6`
  `feat(worktime): accept isolated employee sessions from Helpdesk`.
- `8b64dd9e3a30233226602980a7819adf29ff0686`
  `chore(deploy): guard the WorkTime Helpdesk staging upgrade`.
- `6cf3ea5d2d3784ef2b1ebc86ce637f89ccb617e1`
  `test(deploy): use POSIX paths in staging guard fixtures`.
- `ee86a9458a0c7976659b5dc43cc8572e3bb451df`
  `fix(deploy): reject additional migration command blocks` — deployed revision.
- Installed selector `/opt/endpoint-staging/releases/endpoint-platform-ee86a9458a0c`.
- PostgreSQL revision **0044_worktime_helpdesk**, previously0043_worktime_recorded.
- Canonical `tools/release/build_console_server_archive.ps1` with Python3.12.10,
  then reviewed `tools/release/worktime_helpdesk_staging.py` prepare/activate.
  Archive SHA256 `eaf7259eb009adbe1b63bf55b6cd93248ce783be30c29cb6c614819a1cc31fe8`.
- Private `/root/worktime-helpdesk-20261105-ee86a9458a0c` retains source/archive
  digests, frozen dependencies, preparation, activation, verified backup and
  acceptance receipts. Earlier unexecuted capsule remains immutable.

Only `WORKTIME_HANDOFF_ENABLED=true` and
`ENDPOINT_WORKTIME_HELPDESK_ENABLED=true` were added to the respective staging
environment files. Exact original bytes are backed up privately at
`/root/worktime-helpdesk-config-20261105`; all other parsed settings were compared
unchanged. Existing confidential identity credentials were compared in memory,
never printed. No production target or agent/native package changed. No push/PR.

## Changed surfaces and contracts

Helpdesk: `server/auth/worktime_{authority,handoff,handlers}.py`, canonical token
hash verification, optional typed OIDC outage handling and closed durable return
path, migration153/models, route/middleware/config and session flag projection.
Frontend: explicit AD label, validated WorkTime continuation, existing desktop/
mobile navigation. Tests and `server/docs/{SSO_IDENTITY,CODEMAP}.md` accompany it.

Endpoint: `auth/worktime_{protocol,handoff,sessions}.py`,
`identity/worktime_{client,identity}.py`, explicit authority kind/migration0044,
same-person verified AD adoption, WorkTime-only authorization/session selection,
frontend login options and session API, focused tests and reviewed staging adapter.
Generated browser contract:
`contracts/openapi/endpoint-platform-worktime-v1.yaml`; canonical service and
agent contracts remain unchanged. The bounded emergency-session fix is separate:
the prior test reproduced a five-microsecond deadline overshoot, now prevented by
using one issuance instant instead of relaxing the deadline.

GitNexus group status/query/context were consulted before source exploration.
The committed architectural baseline and local diffs were treated separately.
The new confidential consumer direction is **Endpoint → Helpdesk**; provider
and consumer were verified directly against source/tests. No managed cross-links,
group synchronization or invented manifest contract was added. Context7 was used
for FastAPI/Starlette cookie/redirect behavior. No dependencies added or upgraded.

## Verification evidence

- Helpdesk unit/API:
  `python -m pytest server/tests/test_worktime_handoff_no_db.py server/tests/test_worktime_handoff_api_no_db.py -q`
  — **18 passed**.
- Existing password/browser-error/TLS and new API guards — **37 passed**:
  `python -m pytest server/tests/test_worktime_handoff_api_no_db.py server/tests/test_sso_password_only.py server/tests/test_sso_browser_errors_no_db.py server/tests/test_sso_tls.py -q`.
- Isolated PostgreSQL handoff file — **3 passed**. Separate final isolated run of
  `server/tests/test_sso_oidc.py` and the optional-ticket-gate/incomplete-profile/
  revoked-alias regression — **12 passed**. Fresh temporary DB roles/databases
  were removed, not the working staging databases.
- Helpdesk frontend:
  `pnpm --dir webapp test src/features/auth/worktime-login.test.tsx src/app/layouts/app-shell.test.tsx src/features/auth/login-page.test.tsx`
  — **30 passed**. `pnpm --dir webapp build` passed, including TypeScript.
- `python scripts/verify_workspace.py` and diff checks passed.
- Endpoint `tests/server/test_worktime_handoff.py` + `test_identity_sso.py`
  — **38 passed**. Real isolated PostgreSQL `test_worktime_handoff_postgres.py`
  + `test_identity_sso_postgres.py` — **5 passed**, including concurrency, replay,
  CSRF, DLP rejection, self-only permissions, outage, AD adoption/history and
  bounded emergency access. Temporary DB/role cleanup confirmed.
- Endpoint `tests/worktime/test_api.py`, `test_domain.py`, `test_companion.py`
  — **23 passed**; dependency fixtures now target the selected WorkTime authority.
- Endpoint focused handoff/admin-auth/config/runtime requirements — **69 passed,
  2 platform skips**. The Windows checks skip unavailable symlink/permission
  semantics; these are not live AD acceptance.
- Contract/handoff suite — **143 passed**; subsequent
  `python -m tools.contracts.generate_contract_artifacts --check` passed after
  adding disabled-feature404 to the generated browser contract.
- Staging migration-unit guard tests — **5 passed**, including overriding
  environment files, wrong cwd/argv and an extra ExecStart block.
- Final complete Endpoint frontend `npm --prefix webapp test` — **76 passed**
  across12 files. `npm --prefix webapp run build` and canonical archive build passed.
  One earlier full-suite timeout disappeared in the final complete run.

Browser fixtures used the real built bundles: explicit entries, anonymous
continuation, separate DLP entry, 390px width without horizontal overflow and zero
page exceptions. Expected anonymous session401 responses were observed. Preview
servers were stopped after testing. Live anonymous handoff navigation had zero
failed requests; live WorkTime login page had zero page exceptions. Screenshot:
`tmp/worktime-handoff-20261105/live-worktime-login.png` (private local artifact).
Authenticated user-browser acceptance verified actual day loading and reload;
its console was not separately exported.

Strict hostname/CA HTTPS returned200 for Helpdesk `/api/health` and Endpoint
`/healthz`. A confidential invalid-handle probe returned the exact expected401,
proving the dedicated provider credential and route were wired. Twelve installed
source files were compared by normalized-LF SHA256 with frozen Git sources.
Both AD entry points reached the configured SSO provider with S256 and **without
acr_values/claims requesting MFA**. No fresh domain password was entered, so a
complete live AD credential round trip is not claimed.

## Identity, data and final state

Read-only DB verification matched the live WorkTime identity to the verified
Helpdesk UI alias for `bdryzhak`: same person, explicit Helpdesk authority, null AD
GUID, no administrative owner and one separate WorkTime session. No identity was
guessed by name. All recorded WorkTime personnel/business/grant seals matched
their pre-release values after acceptance; the expected new auth identity/session
are the only additions in that scope. Source revoke/disable/profile/alias guards
and provider errors were covered by isolated tests.

`helpdesk-staging.service`, `endpoint-staging.service` and
`endpoint-staging-worker.service` are **active**, explicitly left running.
Endpoint checkout is clean. Existing unrelated Helpdesk PLANS/older SSO plans,
audit drafts and local artifacts are preserved unstaged. No service/data downgrade
or historical operation replay occurred. Rollback disables the new flags and uses
the prior selector while preserving additive schema/history.

Residual limits: live AD credential completion was not performed; authenticated
browser console export was not collected. Existing npm audit output reports five
findings (two moderate/three high) in the unchanged Endpoint dependency lock; this
task did not run automatic dependency fixes. Full backend/fleet/production gates
were outside scope; focused auth, DB, frontend, contract and staging gates above
are the evidence for this change.

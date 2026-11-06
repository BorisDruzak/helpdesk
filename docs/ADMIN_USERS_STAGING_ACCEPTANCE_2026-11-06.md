# Unified Users — staging acceptance, 2026-11-06

Deployed to the authorized `osn-admin@192.168.101.118` Helpdesk staging service.
Production and Endpoint services were not redeployed. Staging is deliberately
left running for the user's work.

## Frozen release

- Commit: `d7971ca528b416eb77616026ee9144a713334304`.
- Message: `feat(admin): unify user profiles and access administration`.
- Branch: `codex/unified-users-staging-20261106` (local, not pushed).
- Parent/current-staging baseline: `9c247da1f5ae65c5ad131eccc305e3891852486e`.
- Installed selector: `/opt/helpdesk-staging/releases/helpdesk-d7971ca528b416eb77616026ee9144a713334304`.
- Database stays at schema155. No migration was added by this change.

An alternate Git index assembled48 task-only paths over the actual staging
baseline. The active local branch/index were not switched or staged wholesale.
Concurrent notification code, migration156 and other unfinished work were
excluded; already deployed requester/catalog fixes were retained. Independent
review found no P0–P2 extraction/dependency/security issues. The deployed48 files
match Git after newline normalization.

Changed areas: Users page and profile/account/permission components, compact
Registry operations/view/hook/dialogs, sidebar/routes, atomic account provider,
safe membership aliases and related tests/docs. Exact files:
`git diff-tree --no-commit-id --name-only -r d7971ca528b416eb77616026ee9144a713334304`.

## Release checks and installer

Checks ran on an export of the frozen candidate, not the mixed dirty checkout:

- Disposable PostgreSQL provider/auth/access/registry/queue/SSO/approval suite:
  **83 passed**,16 existing framework warnings; owned cluster stopped.
- Users/Registry/access/navigation/sidebar frontend suite: **80 passed /11 files**.
- TypeScript + Vite production build: **passed**.
- `python scripts/verify_workspace.py --workspace <frozen-source>`: **passed**.
- `git diff --check <base> <candidate-tree>`: **passed**.

Exact test file commands are the same as the83-server/80-frontend commands in
[local verification](ADMIN_USERS_VERIFICATION_2026-11-06.md); the PostgreSQL
wrapper used the existing prepared binaries through `--bin-dir`.

The canonical `scripts/deploy_helpdesk_release.py --commit <SHA>` rebuilt the
committed source with its frozen lockfile and installed through the existing
protected staging transport. An additional expected-current-release guard ran
immediately before stopping the Helpdesk writer. No deployed files were patched.

Fresh canonical verified backup: schema155,14527800 bytes,
SHA256 `3d091c2eef93ceded566b8051673a8caf7305fcf344b5f22c2b1c4182286ea25`.
Backup format/digest were verified; no restore rehearsal is claimed.

After deployment: Helpdesk/Endpoint/Endpoint worker active; strict CA/hostname
HTTPS health200 for both applications; all26 served initial JS/CSS/preload assets
byte-match the frozen release. Rendered HTML matches `read_text()` of the frozen
index after removing the expected public runtime-config injection. Anonymous
account read returns401.

## Authenticated browser and Marina

Reused an existing authenticated in-app browser session for the synthetic staging
administrator. An older protected synthetic credential was rejected once; no
password was changed, authentication weakened or additional administrator created.

Actual existing card:
`/app/admin/users?person=f9da2bd9-9d0f-4c1e-9652-ba2b46c9b33f`.
Its recorded name is **Заварухина Марина**, status active. It has no linked
`ui_login` account. Name, profile, identities and real rights were not changed.

Verified against live UI without fixture routes:

- Distinct Users/Registries navigation; Registry has no People/Access-group tab.
- Legacy `/app/admin/access` redirects to `/app/admin/users?tab=access`.
- Marina's card loads; Profile, Account, Permissions/queues are reachable.
- Support role can be selected; ServiceDesk L1 checkbox is enabled/selectable.
- Creating local access requires login, new password and reason; Save remains
  disabled while these are empty. Group/direct-queue explanation is present.
- No horizontal document overflow; no console errors in the final validation
  window. Real forms were inspected, but no live account PUT was submitted.

The remaining UI choice is the employee's account: create the intended login
and password, or explicitly link an existing account, select Support and queue,
enter the reason and save. Never link an unrelated disabled synthetic login.

## Live persistence smoke with rollback

On the installed release, `UserAccountsService.save` ran against
`helpdesk_staging_db` with a transient synthetic person/login inside one outer
transaction. Support role, verified linkage and direct ServiceDesk L1 membership
were saved and read back; subsequent deactivation/removal was also checked.
The outer transaction then rolled back. Fresh-session checks confirm no synthetic
person, account, identity or user-audit row remains. This is deployed-service/DB
evidence, not a claim of a browser-submitted account update or a committed grant.

Before/after business counts match: tickets77, ticket events18525, artifacts6,
users160, people45. Marina still has zero linked accounts.

Private redacted evidence: `tmp/unified-users-staging-20261106/` contains candidate
manifest/diff, frozen test/build logs, backup/install/source/health receipts,
rollback smoke and live screenshots `live-marina-account.jpg` and
`live-marina-queues.jpg`. No credentials or cookies are stored in that evidence.

Full CI, production promotion, live IdP/agent acceptance and concurrent-request
load testing are outside this staging deployment. The separately documented
three failures in the mixed working-copy frontend suite are not presented as
green release evidence. GitNexus was unavailable in this session; extraction
dependencies were checked in committed source and frozen tests.

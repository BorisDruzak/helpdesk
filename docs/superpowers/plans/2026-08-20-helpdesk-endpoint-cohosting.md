# Helpdesk Co-hosting on Endpoint Platform Production Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate Helpdesk to `osn_admin@192.168.100.19` as a clean, independently deployed service without migrating legacy Helpdesk or agent data.

**Architecture:** Helpdesk receives its own immutable release tree, PostgreSQL role/database, Unix user, systemd services, runtime storage and Nginx vhost. It calls Endpoint only through the existing HTTPS Operations API and remains fail-closed until a scoped service credential is accepted.

**Tech Stack:** Python, aiohttp, SQLAlchemy, Alembic, PostgreSQL 16, systemd, Nginx, OpenSSH, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-helpdesk-endpoint-cohosting-design.md`

## Global Constraints

- Do not modify Endpoint Platform source, database, service account, release tree, or runtime directories.
- The Helpdesk database starts empty. Do not copy device, agent-token, user, ticket, session, attachment, audit, or other database data.
- The IP-only bootstrap is restricted and temporary. Final acceptance requires FQDN, trusted TLS, HTTPS/WSS and secure cookies.
- Never print or commit environment values, passwords, tokens, private keys, or certificate material.

---

### Task 1: Define and test the deployment profile

**Files:**
- Create: `scripts/helpdesk_remote_profile.py`, `scripts/test_helpdesk_remote_profile.py`
- Modify: `scripts/manage_remote_stack.py`, `scripts/run_remote_migrations.py`, `scripts/release_server_to_remote.py`

- [ ] Write tests that assert the default remote is `osn_admin@192.168.100.19`, root is `/opt/helpdesk/current`, server Python resolves inside that root, and generated commands use only the current deployment profile.
- [ ] Run the test and verify RED.
- [ ] Implement one environment-overridable profile (`HELPDESK_REMOTE`, `HELPDESK_REMOTE_ROOT`, `HELPDESK_SSH_KEY`) and migrate the three scripts to it.
- [ ] Run focused tests and `git diff --check`.
- [ ] Commit `scripts(deploy): add Helpdesk endpoint-host profile`.

### Task 2: Add immutable release and privileged bootstrap assets

**Files:**
- Create: `deploy/helpdesk/helpdesk-server.service`, `deploy/helpdesk/helpdesk-control.service`, `deploy/helpdesk/helpdesk-migrate.service`, `deploy/helpdesk/helpdesk.nginx.conf`, `deploy/helpdesk/helpdesk.env.example`, `deploy/helpdesk/install_helpdesk_host.sh`, `deploy/helpdesk/release_helpdesk.sh`
- Create: `scripts/test_helpdesk_deploy_assets.py`

- [ ] Write asset-contract tests for dedicated paths/users/ports, root-owned environment file, `/var/lib/helpdesk` writable only by Helpdesk, loopback binding, systemd hardening, Nginx websocket proxying, and no Endpoint directories or legacy release paths.
- [ ] Run RED.
- [ ] Implement the assets: `/opt/helpdesk/releases`, `current` symlink, `helpdesk` non-login user, private venv, separate database role/database, backup before migration, and restricted Nginx IP bootstrap vhost.
- [ ] Run asset tests and shell syntax checks; commit `build(deploy): add Helpdesk production assets`.

### Task 3: Make runtime control safe for the new system service model

**Files:**
- Modify: `server/runtime_control.py`, `server/control_plane.py`, `scripts/runtime_stack.py`
- Create: `server/tests/test_runtime_control_system_service.py`

- [ ] Write failing tests for Helpdesk server/control unit names, root-system service status, and rejected agent lifecycle actions in clean-deployment mode.
- [ ] Run RED.
- [ ] Implement explicit system-service configuration without `systemctl --user`; control-plane lifecycle calls must be disabled unless the reviewed privileged wrapper is installed.
- [ ] Run focused tests; commit `fix(runtime): support isolated Helpdesk system services`.

### Task 4: Build and verify the clean deployment workflow

**Files:**
- Create: `scripts/deploy_helpdesk_to_endpoint_host.py`, `scripts/test_deploy_helpdesk_to_endpoint_host.py`
- Modify: `scripts/release_server_to_remote.py`, `scripts/verify_workspace.py` only if needed to discover the new checked-in deployment assets

- [ ] Write failing tests for archive allow-list, prohibited secret files, remote immutable-release commands, root-owned environment transfer without stdout, migration invocation, and rollback marker handling.
- [ ] Run RED.
- [ ] Implement archive deployment and environment transfer. It must upload only committed runtime source plus the reviewed deployment assets; it must never use `git pull` on the target.
- [ ] Run focused tests, static Python compilation, and `git diff --check`; commit `scripts(deploy): release Helpdesk to endpoint host`.

### Task 5: Update operational documentation and defaults

**Files:**
- Modify: `AGENTS.md`, `PLANS.md`, `server/docs/CODEMAP.md`, `server/docs/README.md`, `server/docs/SECURITY_AND_AUTH.md`, affected deployment/test docs and scripts discovered by targeted search
- Create: `server/docs/RUNBOOK_HELPDESK_ENDPOINT_HOST.md`

- [ ] Write documentation assertions or focused script tests for the new profile defaults where coverage exists.
- [ ] Replace active deployment instructions and runtime defaults referencing the retired host. Preserve explicit historical evidence only when labelled historical and secret-free.
- [ ] Document fresh database/bootstrap-admin flow, IP-only bootstrap boundary, TLS cutover, Endpoint API credential gate, verification, and rollback.
- [ ] Run docs drift checks and focused tests; commit `docs(deploy): document Helpdesk endpoint-host release`.

### Task 6: Deploy the clean Helpdesk baseline to the production host

**Files:**
- Runtime only: `/opt/helpdesk`, `/etc/helpdesk`, `/var/lib/helpdesk`, PostgreSQL role/database, systemd units, Nginx vhost on `192.168.100.19`

- [ ] Re-check disk, memory, listeners, Nginx syntax, PostgreSQL version and Endpoint service health; stop on insufficient capacity or a listener collision.
- [ ] Transfer the current environment securely, replace runtime-path/public-host settings, exclude legacy UI/admin credentials, and create only the approved new administrator by the documented bootstrap command.
- [ ] Install the immutable release, take a fresh Helpdesk database backup, migrate to head, start Helpdesk services, and validate loopback health.
- [ ] Enable the restricted IP bootstrap vhost and test login/health from the approved administrative network without agents.
- [ ] Record redacted service, migration, and health evidence; commit only repository changes, never host secrets or artifacts.

### Task 7: Accept Endpoint integration and final TLS cutover

**Files:**
- Runtime only: Endpoint feature/configuration and Helpdesk root-owned environment/Nginx assets

- [ ] Enable Endpoint Operations only after provisioning a separate least-privilege Helpdesk service identity; prove Helpdesk still cannot access Endpoint data without that bearer.
- [ ] Add the DNS record for `helpdesk.sosnadmin.local`, install the existing wildcard certificate/key through a privileged non-repository path, and validate Nginx.
- [ ] Change Helpdesk to strict production settings (`REQUIRE_HTTPS=true`, `REQUIRE_WSS=true`, secure cookies and final public URL), reload only Helpdesk Nginx configuration, and verify FQDN/TLS hostname/CA chain.
- [ ] Run HTTPS admin browser smoke, Helpdesk-to-Endpoint API smoke, and no-agent clean-state checks. Record residual agent-onboarding work separately.

### Task 8: Final verification and handoff

- [ ] Run `python scripts/verify_workspace.py`, focused deployment/runtime tests, `git diff --check`, and inspect the complete task diff.
- [ ] Verify repository status contains only task commits and remove the retired local `linux` Git remote after confirming `origin` is intact.
- [ ] Update `PLANS.md` with exact deployed commit, schema revision, checks and remaining TLS/agent work; commit the evidence-free documentation update.
- [ ] Report the commits, changed files, redacted host verification, skipped checks, and the fact that Endpoint Platform was not modified as source code.

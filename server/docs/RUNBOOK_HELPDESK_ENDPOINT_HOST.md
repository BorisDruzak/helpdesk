# Helpdesk on the Endpoint host

## Device presence read permission

Support ticket snapshots read the published Endpoint Context API for current
agent presence. The Helpdesk service credential requires `context.read` in
addition to its existing approved scopes. This read does not create collections
or operations. Preserve existing scopes and credential isolation; never bypass
the provider's scope check. A missing scope returns 403 and is displayed as
unknown presence, not offline. The pre-rollout probe on 2026-09-29 returned 403
for the existing production credential; resolve this permission before live
online/offline acceptance. No database migration or Endpoint code change is
required by the Helpdesk presence projection.

## Scope

Helpdesk is deployed to `osn_admin@192.168.100.19` beside Endpoint Platform,
but it is a separate application. It owns `/opt/helpdesk`, `/etc/helpdesk`,
`/var/lib/helpdesk`, the `helpdesk` PostgreSQL database/role and the `helpdesk`
Unix account. Never use Endpoint paths, roles, database or service account for
Helpdesk operations.

## Release and lifecycle

Production Readiness v1 permits exactly one active Helpdesk server process,
one application worker and one Helpdesk Nginx backend. SCALE-036 remains an
open, owner-accepted architectural limitation only for this topology. HA,
active-active, multiple workers, parallel backends and horizontal scaling are
prohibited until separate implementation and acceptance of process-local UI
runtime state. Changing to any of these topologies reopens SCALE-036 as a
release blocker; it is not a completed HA fix.

Production acceptance evidence must include `staging_deployment_topology` and
`production_deployment_topology`, each with `server_instances: 1`,
`application_workers: 1`, `helpdesk_backends: 1`, `ha_enabled: false` and
`load_balancing_enabled: false`. Verify these against actual process/service
and proxy configuration evidence. Missing fields, unsupported topology or
string/boolean substitutes for counts fail the production gate. The immutable
release manifest records the accepted production topology. Recheck the actual
topology after deployment and whenever changing the host/proxy/service layout;
the gate is not a continuous runtime monitor.

Requester-create idempotency requires forward migration 144 before starting
the candidate. It adds `requester_ticket_create_requests` to the Helpdesk
database only. Keep its key tombstones when tickets are deleted; do not purge
keys to retry a request. The canonical requester POST now requires
`Idempotency-Key`, so deploy its accepted web bundle from the same SHA and
update any direct callers to retain a key across retries. Old callers without
a key receive 400. No new environment variable or dependency is required.
Rollback follows the existing application/restore procedure, never a schema
downgrade.

For a new/rebuilt host, install the root-only environment first and then run
`sudo deploy/helpdesk/install_helpdesk_host.sh` from a reviewed release. The
bootstrap intentionally does not create database credentials or copy data.

From the local repository, deploy committed code with:

```powershell
python scripts/deploy_helpdesk_release.py --commit <full-sha> `
  --environment-file <reviewed-local-production-env> `
  --risk-audit artifacts/release/<full-sha>/risk-audit.json `
  --readiness-evidence <protected-staging-evidence.json> `
  --provider-root <clean-locked-provider-checkout> --schema-revision <verified-head>
python scripts/manage_remote_stack.py smoke server --base-url https://helpdesk.sosnadmin.local
python scripts/manage_remote_stack.py status all
```

The release script creates `/opt/helpdesk/releases/helpdesk-<commit>`, installs
its private venv, validates security and stops Helpdesk writers. A temporary
runtime drop-in points the reviewed migration unit at the candidate's server
directory and Python; user, environment, sandbox and preparatory commands are
inherited. Backup verification and `upgrade head` finish before switching
`/opt/helpdesk/current`. The drop-in is removed and systemd reloaded on success
or failure; an existing drop-in blocks deployment. Existing preparatory commands
must remain valid before the switch, including on a rebuilt host. The script
then restarts `helpdesk-server.service` and
`helpdesk-control.service`. The services bind only to `127.0.0.1:8666` and
`127.0.0.1:8667`; the reviewed Nginx template redirects HTTP to HTTPS on
`helpdesk.sosnadmin.local`. Supply root-owned external TLS files at
`/etc/helpdesk/tls/fullchain.pem` and `/etc/helpdesk/tls/privkey.pem` (key mode
0600). The installer refuses missing TLS material or an insecure environment.

To inspect logs, run `python scripts/manage_remote_stack.py logs all --lines 100`.
Rollback is an operator action. **Application-only** rollback switches to a
known previous immutable release only when schema did not change.
**Schema-compatible** rollback requires explicit proof that the previous code
supports the migrated schema. **Restore-required** rollback stops Helpdesk
writers, restores the verified Helpdesk backup under a reviewed recovery plan,
then selects the matching release and verifies DB/business health. A code
symlink rollback alone is not database recovery. Automatic production Alembic
downgrade/stamp is blocked. Production accepts only `upgrade head` and bounded
read commands `current`, `heads`, `history`; alternate/global Alembic argument
forms require separate review. Never touch Endpoint releases, services or data.
On backup/migration failure writers remain stopped for operator recovery;
there is no automatic restart against an unknown schema.

The browser control-plane lifecycle endpoints are deliberately fail-closed on
this host: the `helpdesk` process has no privilege to manage system services.
Use the reviewed remote management script above instead.

## Accepted host adaptations (2026-09-27)

The accepted frozen runtime is `bd3090bd72633a83be5e5f83a894ac959306cf74`,
schema 145, installed as an immutable `helpdesk-<sha>-offline1` release.
The migration, quiesced backup, symlink switch and service restart use the
canonical remote release command. Indexed pip access timed out on this host;
the bounded installation used `--no-index` and a SHA-verified wheelhouse with
Linux package versions identical to the accepted staging runtime. Keep source,
archive and wheel hashes with the release receipt; an offline suffix does not
permit changing application code or skipping the production evidence gate.

For a Windows-exported bootstrap script, use an LF derivative verified byte
for byte against the committed Git blob before running the canonical host
installer. Do not patch deployed application files. Production DB auth remains
enabled and config fallback disabled. Config initialization must also avoid
insecure built-in users: an empty user map selects defaults, so this rollout
uses a protected random disabled fallback identity. It does not reset existing
DB users or weaken the minimum password policy.

Use the approved CA explicitly when the Linux operator trust store lacks the
internal issuer; never waive TLS verification. The release and business smoke
markers refer to the accepted frozen candidate; actual post-deploy process,
proxy topology, restore and Windows receipts are required independently.
Production is authorized to remain running. Stop isolated staging services
and restore protected Windows enrollment after validation. The 72-hour pilot
remains a post-rollout observation, not an elapsed acceptance claim.

## Security and staged acceptance

- `/etc/helpdesk/helpdesk.env` is root-owned, mode 0600, and is never committed
  or printed. Runtime data is in `/var/lib/helpdesk`; legacy runtime copying is
  disabled for this clean deployment.
- The checked-in production profile requires `APP_ENV=prod`, HTTPS/WSS,
  secure cookies, database persistence, loopback backend/control binds and an
  explicit trusted proxy policy. Insecure auth defaults are forbidden.
  Run `python scripts/validate_production_config.py --environment-file
  <root-owned-env> --require-production` before deployment. The deploy script
  repeats validation before switching `current`; systemd also validates the
  inherited environment before starting either service. Existing historical
  HTTP bootstrap deployments are not production-ready merely because these
  assets were updated. Verify real DNS, CA/hostname TLS and browser WSS.
- The initial independent Helpdesk database was created without migrating
  Endpoint or legacy application data. Seed the canonical request catalog
  through the project catalog script before the first requester preview.
  Bootstrap only the initial administrator through the canonical user script;
  use a policy-compliant protected credential and rotate it after handoff.
  The accepted 2026-09-27 rollout retains the initial admin handoff only at
  `/etc/helpdesk/initial-admin-handoff.json`, root-owned mode 0600. Never copy
  its content into release evidence or command arguments.
- Endpoint Operations integration remains fail-closed until Endpoint accepts a
  dedicated least-privilege Helpdesk service identity. Do not reuse Endpoint
  credentials.
- No existing agents are registered on this deployment. Their future
  authentication/connection flow is a separate rollout.

## Production Readiness v1 rollout sequence

Runtime commands in `scripts/manage_remote_stack.py` use the same
`HELPDESK_SERVER_SERVICE` and optional `HELPDESK_CONTROL_SERVICE` profile as the
release installer. For staging set the server unit to `helpdesk-staging.service`
and the control unit to an empty value when no separate control service exists.
An explicit request for an unconfigured control service fails before SSH dispatch.

The command above is prepared for a separately authorized production rollout.
Do not run it on the basis of local tests alone. Before starting, verify exact
SHA/full CI artifact, accepted CI bundle/digests, Endpoint lock/provider evidence,
current risk dispositions and live staging evidence. Check backup storage free
space, disk/memory, PostgreSQL connectivity, Nginx syntax, DNS and CA/hostname
certificate validation. Certificates/private keys remain in root-owned external
paths; do not use `--insecure-tls` as production acceptance.

The reviewed deploy command validates the frozen RC, packages the accepted web
bundle, verifies transfer digest, validates remote security, stops only Helpdesk
writers, verifies its DB backup before Alembic, migrates the immutable candidate,
then switches the active release and restarts only Helpdesk. On failure it does not silently fall back or roll
back Endpoint. Check HTTPS health, browser login/WSS, real requester/support
business flow, safe Windows Endpoint diagnostic and correlated bounded audit.
The candidate is not deployed merely because its manifest exists.

Staging uses `osn-admin@192.168.101.118`, `/opt/helpdesk-staging`,
`/etc/helpdesk-staging` and `/var/lib/helpdesk-staging`. Windows acceptance uses
`test_agent_win@192.168.101.120`. Obtain synthetic requester/support credentials,
scoped Endpoint credential and isolated DB admin access from the approved secret
channel at runtime. Never substitute the production host or real admin account.
Restore the original staging dependency configuration after outage testing.

### Staging provider alignment and Windows acceptance

Acceptance requires Endpoint staging to match the supported provider lock,
the dedicated Windows VM to be enrolled in that isolated namespace, and a
scoped Helpdesk credential for the same provider. Do not substitute production
for initial acceptance. Provider/agent alignment was completed under separately
authorized Endpoint work on 2026-09-27: the locked `abdd5c7ef596` provider and
existing Windows 3.2.75 agent produced a real safe diagnostic result for Helpdesk
candidate `fbf415f9`. No reinstall was performed. Protected original enrollment
was restored after validation and staging services were stopped.

That result is historical evidence for its exact candidate, not acceptance for
later release SHAs. Every new frozen candidate still requires the documented
staging business, Windows and degraded receipts before an accepted manifest.
Preserve encrypted enrollment recovery and restore the original VM identity
after isolated testing; do not copy agent credentials into Helpdesk evidence.

## Operational signals and controlled 72-hour pilot

Use existing `/api/health`, authenticated Tech Panel snapshot, Observer and
Helpdesk systemd/journal checks. Record API/core liveness, database reachability,
release SHA/schema revision, backup/restore markers, latest business smoke,
stuck operations and critical integrity events. Endpoint dependency failure is
a separate degraded condition; it must not make working Helpdesk core liveness
fail. The adapter's `availability()` currently reports configuration readiness,
not network reachability: do not interpret configured as a live provider probe.
Live safe diagnostic/reconciliation evidence is required for actual availability.
Missing marker/status is unknown and blocks readiness, not an implied success.

After a separately authorized deployment, restrict the first wave to a small
operator/requester cohort and safe capabilities; Windows live acceptance only.
Check at pilot start, each operator shift and after every failure during 72
hours (do not wait 72 hours inside this implementation task):

- HTTP 5xx rate, application restarts and PostgreSQL errors;
- authentication failures and stuck ticket/workflow transitions;
- stuck operations, dependency failures and Windows Agent reconnect;
- duplicate timeline/operation events and Observer critical integrity events;
- verified backup success, business smoke and disk growth.

Record exact revision, observation interval, measured counts, redacted evidence,
owner and disposition. A critical integrity/security failure or loss of core
business workflow pauses the pilot and invokes the reviewed recovery procedure.
Pilot completion is a post-deployment operational gate, not covered by unit CI.

ALT Linux Agent acceptance was intentionally excluded from Production Readiness v1.

### Endpoint dependency operational signal

Tech Panel Runtime shows Endpoint separately from core API/DB health. It probes one
saved verified ticket device mapping through the existing HTTPS typed adapter,
with a two-second limit and no operation creation. Missing mapping means unknown,
not healthy. Configuration readiness does not prove network availability. A
success proves only bounded API read reachability, not Windows execution or
release compatibility. Degradation is a warning; core liveness remains separate.

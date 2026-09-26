# Helpdesk on the Endpoint host

## Scope

Helpdesk is deployed to `osn_admin@192.168.100.19` beside Endpoint Platform,
but it is a separate application. It owns `/opt/helpdesk`, `/etc/helpdesk`,
`/var/lib/helpdesk`, the `helpdesk` PostgreSQL database/role and the `helpdesk`
Unix account. Never use Endpoint paths, roles, database or service account for
Helpdesk operations.

## Release and lifecycle

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
its private venv, validates security, stops Helpdesk writers, switches
`/opt/helpdesk/current`, creates and verifies a PostgreSQL custom backup before
`upgrade head`, then restarts `helpdesk-server.service` and
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
- The Helpdesk database is intentionally empty: no tickets, users, agents,
  tokens, attachments or audit data were migrated. Create the first administrator
  separately after the owner chooses its credentials.
- Endpoint Operations integration remains fail-closed until Endpoint accepts a
  dedicated least-privilege Helpdesk service identity. Do not reuse Endpoint
  credentials.
- No existing agents are registered on this deployment. Their future
  authentication/connection flow is a separate rollout.

## Production Readiness v1 rollout sequence

The command above is prepared for a separately authorized production rollout.
Do not run it on the basis of local tests alone. Before starting, verify exact
SHA/full CI artifact, accepted CI bundle/digests, Endpoint lock/provider evidence,
current risk dispositions and live staging evidence. Check backup storage free
space, disk/memory, PostgreSQL connectivity, Nginx syntax, DNS and CA/hostname
certificate validation. Certificates/private keys remain in root-owned external
paths; do not use `--insecure-tls` as production acceptance.

The reviewed deploy command validates the frozen RC, packages the accepted web
bundle, verifies transfer digest, validates remote security, stops only Helpdesk
writers, selects the immutable candidate, verifies its DB backup before Alembic,
then restarts only Helpdesk. On failure it does not silently fall back or roll
back Endpoint. Check HTTPS health, browser login/WSS, real requester/support
business flow, safe Windows Endpoint diagnostic and correlated bounded audit.
The candidate is not deployed merely because its manifest exists.

Staging uses `osn-admin@192.168.101.118`, `/opt/helpdesk-staging`,
`/etc/helpdesk-staging` and `/var/lib/helpdesk-staging`. Windows acceptance uses
`test_agent_win@192.168.101.120`. Obtain synthetic requester/support credentials,
scoped Endpoint credential and isolated DB admin access from the approved secret
channel at runtime. Never substitute the production host or real admin account.
Restore the original staging dependency configuration after outage testing.

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

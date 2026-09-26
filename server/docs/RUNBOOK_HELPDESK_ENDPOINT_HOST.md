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
python scripts/deploy_helpdesk_release.py --commit <commit>
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
downgrade/stamp is blocked. Never touch Endpoint releases, services or data.
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

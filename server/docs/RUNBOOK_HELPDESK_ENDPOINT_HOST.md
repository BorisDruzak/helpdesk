# Helpdesk on the Endpoint host

## Scope

Helpdesk is deployed to `osn_admin@192.168.100.19` beside Endpoint Platform,
but it is a separate application. It owns `/opt/helpdesk`, `/etc/helpdesk`,
`/var/lib/helpdesk`, the `helpdesk` PostgreSQL database/role and the `helpdesk`
Unix account. Never use Endpoint paths, roles, database or service account for
Helpdesk operations.

The retired `192.168.100.17` host, its SMB share and `/var/chat_bot/pc_client`
are not a deployment source.

## Release and lifecycle

From the local repository, deploy committed code with:

```powershell
python scripts/deploy_helpdesk_release.py --commit <commit>
python scripts/manage_remote_stack.py smoke server --base-url http://192.168.100.19:8080
python scripts/manage_remote_stack.py status all
```

The release script creates `/opt/helpdesk/releases/helpdesk-<commit>`, installs
its private venv, applies `upgrade head` to the fresh Helpdesk database, switches
`/opt/helpdesk/current`, then restarts `helpdesk-server.service` and
`helpdesk-control.service`. The services bind only to `127.0.0.1:8666` and
`127.0.0.1:8667`; Nginx exposes the temporary bootstrap vhost on port 8080.

To inspect logs, run `python scripts/manage_remote_stack.py logs all --lines 100`.
Rollback is an operator action: point `current` at a known previous immutable
release and restart the two Helpdesk services. Do not roll back PostgreSQL by
copying Endpoint data.

The browser control-plane lifecycle endpoints are deliberately fail-closed on
this host: the `helpdesk` process has no privilege to manage system services.
Use the reviewed remote management script above instead.

## Security and staged acceptance

- `/etc/helpdesk/helpdesk.env` is root-owned, mode 0600, and is never committed
  or printed. Runtime data is in `/var/lib/helpdesk`; legacy runtime copying is
  disabled for this clean deployment.
- This is a temporary IP-only HTTP bootstrap restricted at Nginx. It is not the
  final TLS configuration. Before wider access, create the Helpdesk FQDN, enable
  HTTPS/WSS, secure cookies and strict HTTPS settings.
- The Helpdesk database is intentionally empty: no tickets, users, agents,
  tokens, attachments or audit data were migrated. Create the first administrator
  separately after the owner chooses its credentials.
- Endpoint Operations integration remains fail-closed until Endpoint accepts a
  dedicated least-privilege Helpdesk service identity. Do not reuse Endpoint
  credentials.
- No existing agents are registered on this deployment. Their future
  authentication/connection flow is a separate rollout.

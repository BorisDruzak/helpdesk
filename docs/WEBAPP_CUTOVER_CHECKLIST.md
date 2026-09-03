# Webapp route-retirement checklist

The server-rendered Helpdesk shells have been retired. React `/app/*` is the
only browser UI; there is no feature flag, bundle-presence fallback, or
`?legacy=1` escape hatch that can restore a legacy shell.

## Unconditional entry-route contract

| Former URL | React destination |
|---|---|
| `/login` | `/app/login` |
| `/admin` | `/app/admin` |
| `/support` | `/app/support` |
| `/help` | `/app/help` |
| `/ticket.html` | `/app/ticket` |
| `/ticket/{ticket_id}` | `/app/ticket/{ticket_id}` |

Every route responds with HTTP 308. Query parameters are preserved except the
retired `legacy` and `_shell` keys. Thus `/admin?legacy=1&tab=queue` redirects
to `/app/admin?tab=queue`.

Former shell assets such as `/admin.js`, `/support.js`, `/ticket.js` and the
embedded legacy module/form workbenches are deliberately unregistered and must
return HTTP 404.

## Local verification

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run build
python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short
node --test webapp/scripts/remote-browser-signoff.test.mjs
python scripts/verify_workspace.py
```

## Remote signoff after release

```powershell
pnpm --dir webapp run check:remote:webapp -- --base-url https://example.test:9443
```

The helper verifies every retired entry route, including `?legacy=1` variants,
opens `/app`, `/app/admin` and `/app/support`, checks Russian UI text, and
fails on console or page errors. A browser MCP check remains required whenever
a visible workflow changes.

## Out of scope

Public queue and technical/debug static pages are not part of the retired
shell set. Their deletion requires an independent inventory and migration
decision.

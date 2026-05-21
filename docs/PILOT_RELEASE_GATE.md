# Pilot Release Gate

This is the operator checklist for moving a pilot stand from Tech Panel `READY` to a real release candidate. The Tech Panel is evidence and observability; it is not the authority that enables dangerous actions.

## Required Evidence

- `ENABLE_DB_PERSISTENCE=true`.
- `PILOT_STAND_MODE=true`.
- `AUTH_ALLOW_QUERY_TOKEN=false`.
- `AUTH_UI_CONFIG_FALLBACK_ENABLED=false`.
- `WEB_SESSION_COOKIE_SECURE=true`.
- `REQUIRE_HTTPS=true`.
- `REQUIRE_WSS=true`.
- `PILOT_MIN_AGENT_VERSION` set to the current approved agent baseline.
- `TECH_RELEASE_STATUS_PATH`, `TECH_BUSINESS_SMOKE_STATUS_PATH`, `TECH_RESTORE_DRILL_STATUS_PATH` and `TECH_BACKUP_STATUS_PATH` readable by the running server.
- Latest release, backup, restore drill and business smoke markers show `status=success`.

## Business Smoke

Use a dedicated smoke account, not a human admin password. For self-signed stand TLS:

```powershell
python scripts/business_smoke.py `
  --base-url https://192.168.100.17:9443 `
  --username $env:BUSINESS_SMOKE_USERNAME `
  --password $env:BUSINESS_SMOKE_PASSWORD `
  --output $env:TECH_BUSINESS_SMOKE_STATUS_PATH `
  --require-https `
  --require-secure-cookie `
  --browser-check `
  --insecure-tls
```

Optional deeper acceptance requires an explicit test device and ticket:

```powershell
python scripts/business_smoke.py `
  --base-url https://192.168.100.17:9443 `
  --username $env:BUSINESS_SMOKE_USERNAME `
  --password $env:BUSINESS_SMOKE_PASSWORD `
  --output $env:TECH_BUSINESS_SMOKE_STATUS_PATH `
  --require-https `
  --require-secure-cookie `
  --browser-check `
  --insecure-tls `
  --device-id <safe_test_device_id> `
  --create-test-ticket `
  --run-safe-tool inventory.collect `
  --operation-wait-seconds 60 `
  --check-update-recommendation
```

The marker must not contain passwords, cookies, bearer tokens or raw secrets.

## Browser Signoff

Run after release:

```powershell
pnpm --dir webapp run check:remote:webapp -- --base-url https://192.168.100.17:9443
```

If `--base-url` is omitted, the helper reads `PC_CLIENT_BROWSER_BASE_URL`, then `REMOTE_SMOKE_BASE_URL`, and finally falls back to `https://192.168.100.17:9443`.

## Stand Profile

Use env/profile settings instead of editing scripts when a stand changes:

- `PC_CLIENT_REMOTE`
- `PC_CLIENT_REMOTE_ROOT`
- `PC_CLIENT_REMOTE_SERVER_PYTHON`
- `PC_CLIENT_SSH_KEY`
- `REMOTE_SMOKE_BASE_URL`
- `REMOTE_SMOKE_INSECURE_TLS`
- `PC_CLIENT_BROWSER_BASE_URL`

The current 192.168.100.17 stand remains the fallback only for the existing lab profile.

## GitHub Gate

Repository settings must enforce protected release branches outside the codebase:

- Require pull request review before merge.
- Require successful status checks for `python scripts/run_ci_suite.py` or the equivalent CI workflow artifact.
- Require the current branch to be up to date before merge.
- Restrict who can push directly to release branches.
- Require successful deployment/full-gate evidence before declaring a pilot release candidate.

Codex cannot make these settings true from a local commit unless a GitHub admin token and explicit instruction are provided.

## Soak

Before expanding beyond the first controlled pilot wave, run a 72-hour soak with:

- HTTPS/WSS-only stand flags enabled.
- Inventory scheduler either explicitly disabled for the first wave or enabled with `active_task_count <= 1` in Tech Panel runtime details.
- Several online agents reconnecting through server restarts and network interruptions.
- No duplicate inventory scheduler tasks.
- No query-token auth attempts except deliberate negative tests.
- Business smoke marker refreshed at least once per release candidate.

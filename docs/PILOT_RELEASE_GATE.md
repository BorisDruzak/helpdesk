# Pilot Release Gate

This is the operator checklist for moving a pilot stand from Tech Panel `READY` to a real release candidate. The Tech Panel is evidence and observability; it is not the authority that enables dangerous actions.

## Required Evidence

- `ENABLE_DB_PERSISTENCE=true`.
- `APP_ENV=pilot` or `APP_ENV=prod`; legacy `PILOT_STAND_MODE=true` remains a strict-mode compatibility trigger.
- `ALLOW_INSECURE_DEV_DEFAULTS=false`.
- `AUTH_ALLOW_QUERY_TOKEN=false`.
- `AUTH_UI_CONFIG_FALLBACK_ENABLED=false`.
- `WEB_SESSION_COOKIE_SECURE=true`.
- `REQUIRE_HTTPS=true`.
- `REQUIRE_WSS=true`.
- `PILOT_MIN_AGENT_VERSION` set to the current approved agent baseline.
- `TECH_RELEASE_STATUS_PATH` and `TECH_BUSINESS_SMOKE_STATUS_PATH` readable by the running server.
- Latest release and business smoke markers show `status=success`.
- Production Readiness v1 requires successful verified backup and isolated restore
  markers. Earlier mini-prod optional-backup policy is historical, not a waiver.

## Production Readiness v1

The GitHub administrator must make the `production-readiness` job of **Helpdesk
production readiness** mandatory. It combines canonical full CI (fresh isolated
PostgreSQL/migration, Python/scripts, web typecheck/build/Vitest/fixture E2E) and
the pinned real Endpoint contract workflow. This CI check alone does not prove
live staging or Windows Agent acceptance. ALT live acceptance is excluded.

Freeze a clean exact SHA before full CI. Production preflight forbids dirty or
bundle bypasses and identical-tree merge CI reuse. Export the exact-SHA GitHub
CI artifact to `artifacts/ci/<sha>/`, including the web bundle sidecar manifest.
Then run:

```powershell
python scripts/release_candidate_preflight.py --workspace . --production `
  --environment-file <reviewed-local-env> --risk-audit artifacts/release/<sha>/risk-audit.json `
  --readiness-evidence <protected-staging-evidence.json> `
  --provider-root <clean-pinned-provider-checkout> --schema-revision <verified-head>
```

Required acceptance fields are defined in
`scripts/production_release_gate.py`: exact candidate/provider/OpenAPI/schema/
web digest, `configuration_profile=production-v1`, `environment=staging`, and
successful contract/backup/restore/business/Windows/degraded checks. Historical,
fixture or skipped results cannot fill these gates. Evidence must be generated
from actual protected run records, not hand-written success assertions.
P0/P1 current-revision dispositions are validated separately through the risk
audit. Missing runtime credentials or staging access means BLOCKED.

Only after every check passes does preflight create
`artifacts/release/<sha>/release-manifest.json`. It contains bounded fields only,
never credentials/raw diagnostic output; an existing differing manifest cannot
be overwritten. Production deploy repeats this preflight and validates the
remote archive digest before extraction. This task does not authorize an
actual production rollout.

Production packaging copies the accepted CI web archive bytes directly into
the application archive. It does not rebuild frontend assets after acceptance;
the gate verifies both the compressed archive digest and its canonical file
content digest, and rejects links, traversal, duplicates or incomplete bundles.

## Business Smoke

Use a dedicated smoke account, not a human admin password. For self-signed stand TLS:

```powershell
python scripts/business_smoke.py `
  --base-url https://example.test:9443 `
  --output $env:TECH_BUSINESS_SMOKE_STATUS_PATH `
  --require-https `
  --require-secure-cookie `
  --browser-check `
  --insecure-tls
```

Synthetic credentials are read from runtime `BUSINESS_SMOKE_USERNAME` and
`BUSINESS_SMOKE_PASSWORD`; keep them off argv and evidence. The browser helper
verifies TLS by default and requires an actually observed WSS connection.
`--insecure-tls` is an explicit development/stand option, never production
TLS acceptance. This smoke remains partial; it cannot replace the full live
requester/support lifecycle, audit/persistence and Windows/degraded gates.

Optional deeper acceptance requires an explicit test device and ticket:

```powershell
python scripts/business_smoke.py `
  --base-url https://example.test:9443 `
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
pnpm --dir webapp run check:remote:webapp -- --base-url https://example.test:9443
```

If `--base-url` is omitted, the helper reads `PC_CLIENT_BROWSER_BASE_URL`, then `REMOTE_SMOKE_BASE_URL`, and finally falls back to `https://example.test:9443`.

## Stand Profile

Use env/profile settings instead of editing scripts when a stand changes:

- `PC_CLIENT_REMOTE`
- `PC_CLIENT_REMOTE_ROOT`
- `PC_CLIENT_REMOTE_SERVER_PYTHON`
- `PC_CLIENT_SSH_KEY`
- `REMOTE_SMOKE_BASE_URL`
- `REMOTE_SMOKE_INSECURE_TLS`
- `PC_CLIENT_BROWSER_BASE_URL`

The current example.test stand remains the fallback only for the existing lab profile.

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

# Phase-one Studio content publication

`scripts/helpdesk_phase1_catalog.py` is a bounded importable helper for the
reviewed staging procedure. It adds four maps: password/login recovery, new
account requests, equipment replacement, and website/business-system faults.
The maps only collect requests. They do not change AD accounts, passwords,
permissions, devices or external systems.

The authoritative input is the currently published Other map
`scenario_import_608bb9a16cbd45ed9c921c4ba92df310`. Existing maps and drafts are
not rewritten. Its `q_scope` fields, `q_urgency` fields, `d_sla` branches and SLA
profiles are copied. Only the new maps connect urgency directly to `d_sla` and
use Other's first-line route. The current 120/180/300-minute durations remain
authoritative data, not new SLA defaults in the helper. Each new map has a
conditionally required question for the other system/equipment name.

The ordinary closure code `guided_studio_20261011_closure` gets exactly version
`1.0.2` through `HelpdeskPolicyRepo.publish_policy`. Public summary remains
required; resolution code and requester confirmation are not required. Other
policy codes, old policy configuration, immutable scenario versions and ticket
snapshots are untouched. Canonical publication retires the old policy's active
lifecycle state. New submissions resolve the latest policy through existing
runtime code; existing maps need no blanket republication.

## Review and execution boundary

Run the reviewed project staging wrapper on the approved Helpdesk staging host.
The wrapper must verify host `test-helpdesk` / SSH `osn-admin@192.168.101.118`,
the intended deployed release, and obtain its private database configuration and
trusted admin `AuthContext`. It owns a private pre-application backup and later
readback. Do not print connection URLs, credentials, auth contexts with tokens,
raw server configuration or publication confirmation tokens.

Import with the repository root and `server` on `PYTHONPATH`. Construct an
`async_sessionmaker` from the wrapper's approved SQLAlchemy engine, then:

```python
from scripts.helpdesk_phase1_catalog import publish_phase1

plan = await publish_phase1(session_factory, authenticated_admin)
# Review and privately retain the plan; no tokens or writes are produced.
result = await publish_phase1(
    session_factory,
    authenticated_admin,
    apply=True,
    expected_fingerprint=plan["fingerprint"],
)
```

The helper verifies `current_database() == 'helpdesk_staging_db'`. Its database
check supplements the wrapper's host/release guards. An omitted `apply` performs
SELECTs only. Application owns one fresh transaction, follows canonical service
lock order, checks the fingerprint under source locks, publishes the policy,
creates map offerings through `RequestScenarioRepo.create_service`, obtains
canonical readiness/confirmation through `ScenarioPublicationService.preview`,
and publishes through `ScenarioPublicationService.publish`. Any exception rolls
back policy, drafts, offerings, map versions, tokens and audits together.

The result contains version IDs and content fingerprints, never confirmation
tokens. A repeated application requires a fresh reviewed plan fingerprint. Exact
published content and exact policy version/configuration produce a no-op;
conflicting content or a stale baseline fail closed. Nothing is deleted.

## Focused verification

```powershell
python -m pytest server/tests/test_helpdesk_phase1_catalog_no_db.py -q --tb=short
python -m pytest server/tests/test_helpdesk_phase1_catalog_db.py -q --tb=short
python scripts/verify_workspace.py
git diff --check
```

The database tests use the standard isolated PostgreSQL harness and explicitly
pass `isolated_test=True`. Only a unique `pc_support_test_*` database is accepted;
shared `pc_support_test`, template databases and production names are rejected.
Never point this test command at staging's application database. The harness
creates and cleans its own per-run database; credentials remain outside source.

The three PostgreSQL tests cover read-only planning, successful canonical
publication and idempotence, rollback after a second publication fails, and a
stale fingerprint. Pure runtime tests execute all six scope/urgency combinations
for each new map, conditional required/hidden fields and backtracking with SLA
recalculation. Live staging browser/readback verification belongs to the release
coordinator and is not implied by these tests.

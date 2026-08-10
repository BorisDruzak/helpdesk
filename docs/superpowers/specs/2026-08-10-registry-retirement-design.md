# Registry and Registration Retirement Design

## Goal

Remove the local Registry and device-registration persistence only after
Helpdesk consumes equivalent, versioned external Registry projections through
`RegistryPort`. Preserve Helpdesk authentication, web sessions, RBAC, tickets,
and consent records throughout the transition.

## Confirmed scope

The user confirmed that the following remain Helpdesk-owned and are never
targets of this retirement:

- `ui_users`, `ui_user_audit`, UI tokens and Helpdesk web sessions;
- RBAC tables (`access_groups`, membership, permission and queue-membership
  tables);
- tickets, queues, workflow, Endpoint runtime, and `user_consent_requests`.

The retirement targets are local `registry_*` data, local
`device_registration_*` data, device account/pairing data, and Registry-linked
columns/FKs in Helpdesk ticket and consent records. `ticket_kb_links` and
sanitized historical `knowledge_attempts` are separate read-only historical
concerns and are not deleted by the Registry cutover.

## Chosen approach

Use a staged **forward-only** cutover. A linear Alembic downgrade is rejected:
`downgrade 082`, `054`, or `096` would reverse unrelated migrations and leave
the current application incompatible with its schema.

1. **PR-2 — immutable refs and snapshots.** Tickets and consent records gain
   opaque person/device/binding references and redacted immutable requester
   snapshots. Existing Registry fields are read-only compatibility data. New
   history/support projections do not query Registry to render completed work.
2. **PR-8 — internal RegistryPort boundary.** Helpdesk consumers use a single
   `RegistryPort`; a local adapter encapsulates the existing Registry ORM and
   repositories. An import guard rejects new direct Registry service/ORM
   dependencies outside the adapter, migrations and explicitly isolated tests.
3. **PR-9 — external Registry API and shadow reads.** A versioned external
   adapter supplies person/device references, requester snapshots, active
   binding summaries, account-status lookups and audience projections. Start
   with non-authorizing reads; commands affecting registration, account
   sessions, browser pairing or login eligibility require idempotency and
   dedicated acceptance gates before cutover.
4. **PR-11 — schema retirement.** After all active local reads/writes are
   removed and the external adapter is accepted, run one new idempotent
   forward-only migration during a maintenance window. Its rollback is
   restoration of a verified pre-migration backup, not Alembic downgrade.

## Data and safety contract

PR-11 first exports or archives the approved target rows and records counts,
FK inventory, backup hash, restore evidence and target schema head. It then
acquires an advisory lock, stops writers, checks that Registry ORM/routes/jobs
are absent, and drops dependent FK children before their Registry roots.

`user_consent_requests` remains; its Registry FKs are removed or replaced by
opaque external-reference/snapshot fields before Registry rows are dropped.
Ticket requester/account fields follow the same rule. `ui_users` is detached
from local `RegistryPersonIdentity` checks before the Registry identity table
is retired; account eligibility becomes an external Registry status result or
a Helpdesk-owned immutable status snapshot.

The old Knowledge/AI schema follows the same forward-only backup-and-rehearsal
gate, but can be retired independently because its active runtime was removed
in PR-6. No migration edits historical revisions and no cleanup is applied to
production from a development workstation.

## Acceptance evidence

- isolated PostgreSQL clone rehearsal: backup, migration, schema/FK/count
  audit, restore, and re-audit;
- direct upgrade from the current historical head to the new head, plus an
  idempotent repeated upgrade;
- no active Registry imports/ORM mappings/routes/jobs after the cutover;
- contract tests for external unavailable/error outcomes, shadow comparisons,
  snapshots, ticket creation and consent;
- PostgreSQL catalog proof that only approved target tables/FKs are absent;
- post-cutover browser smoke when the stand becomes available.

## Non-goals

This work does not delete Helpdesk authentication/RBAC, rewrite historical
Alembic revisions, reintroduce local Knowledge, deploy to the remote stand, or
perform a destructive production migration before the listed evidence exists.

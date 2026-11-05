# User display names and staging account cleanup

## Display contract

`app/services/user_display_names.py` reads names in one batch from Registry
people linked by **verified `ui_login` identity**, using full name, display name,
then the existing login. This is display-only; no identity/role/ownership is
inferred or changed. UUID-only names are ignored. Unverified aliases never
provide names. Requester specialist names and admin Access Control reuse it.

Admin-only `GET /api/web/admin/access/summary` adds optional `users[].display_name`.
The users table renders it and searches it. Older responses without the field
show “Имя не указано”; there is no API-error placeholder. The initial status
filter is Active, and the users tab count is the active count. Disabled accounts
remain accessible through the status filter for audit/restoration.

## Approved staging cleanup

`scripts/helpdesk_staging_user_cleanup.py` is maintenance-only. It refuses any
host except `test-helpdesk`, any selector outside `/opt/helpdesk-staging/releases`,
an unexpected frozen release, or a database other than `helpdesk_staging_db`.
It preserves active `admin`/`admin-2` administrators and requester `bdryzhak`.
Only known synthetic login families are eligible; an unknown employee stops it.

First run `--release <current-40-character-SHA>` for a read-only plan. Take a
fresh verified backup through `scripts/helpdesk_database_backup.py`'s canonical
backup function. Apply with the same release, `--apply`,
`--fingerprint <plan-hash>` and `--backup-marker <private-receipt>`.
The artifact digest, size, staging DB, source
release and age (at most1hour) must match. Do not print credentials or backup
contents. Use only the approved staging SSH transport.

Apply locks/rechecks user roles/status before modifying anything, disables
synthetic users and revokes their UI tokens through the canonical disable helper
with audit. The three protected accounts' roles/passwords/tokens remain intact.
Only the observed exact “Тестовый Пользователь 1” full/display name on the already
verified `admin` person is cleared to an unset full name and `admin` display name;
the existing identity remains. Any failure rolls back the transaction. The CLI
owns database initialization and disposal on success/error.

Users, people, tickets, messages, memberships and immutable snapshots are retained.
This is reversible cleanup of the working list, without historical deletion.
Restoring access requires an explicit admin decision for the particular account;
revoked sessions stay revoked and must sign in again. The pre-change private
backup and audit provide original state; never restore a whole DB over newer
business data just to reactivate a test account. Do not run this on production.

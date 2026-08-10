# Runbook: Backup и Restore (PostgreSQL)

## Базовый уровень (Stage 12)

- **Daily base backup:** pg_basebackup.
- **WAL archiving** для PITR (Point-in-Time Recovery).
- **Retention:** минимум 14 daily + 8 weekly бэкапов.

## Требования

- Доступ к серверу БД и к месту хранения бэкапов (диск или S3-совместимое хранилище).
- Настроенный `archive_mode = on` и `archive_command` в PostgreSQL.

## Ежедневный base backup (рекомендуемый способ)

```bash
# Создать каталог для бэкапа (дата в имени)
BACKUP_DIR=/var/backups/postgres/base/$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

# pg_basebackup (от имени пользователя с правами репликации)
pg_basebackup -D "$BACKUP_DIR" -F tar -z -P -U replica_user
```

## WAL archiving

В `postgresql.conf`:

- `archive_mode = on`
- `archive_command = 'cp %p /var/backups/postgres/wal/%f'` (или скрипт загрузки в облако)

После изменения перезапуск или `pg_ctl reload`.

## Восстановление из base backup

1. Остановить PostgreSQL.
2. Очистить каталог данных кластера (или использовать новый инстанс).
3. Распаковать base backup в каталог данных.
4. Добавить в каталог данных файл `standby.signal` для режима standby или оставить пустой для полного восстановления.
5. При необходимости скопировать недостающие WAL-сегменты в `pg_wal/`.
6. Запустить PostgreSQL.

## PITR (Point-in-Time Recovery)

1. В каталоге данных создать `recovery.signal`.
2. В `postgresql.conf` (или в каталоге данных) задать:
   - `restore_command = 'cp /var/backups/postgres/wal/%f %p'`
   - `recovery_target_time = '2026-02-17 12:00:00+00'` (желаемая точка восстановления, опционально).
3. Запустить PostgreSQL; сервер восстановится до указанного времени и завершит работу (для проверки) или станет primary (в зависимости от настроек).

## Ежемесячный restore drill (staging)

1. Раз в месяц выполнять полное восстановление на staging из последнего daily backup.
2. Замерить RTO (время восстановления) и RPO (потеря данных по времени).
3. Зафиксировать результаты и при необходимости скорректировать частоту бэкапов или WAL.

## PR-11 retirement rollback gate

Before a future destructive Registry/Knowledge retirement migration, create a
fresh encrypted backup and record its SHA-256. Restore it to an isolated clone,
run the target-table row-count/catalog/FK audit there, and record the passed
restore drill identifier. The production maintenance plan must name its
approved window, stopped writers and PostgreSQL advisory-lock key.

Record only redacted evidence in
`artifacts/registry-retirement-evidence.json`; never commit credentials,
connection URLs, cookies or backup contents. The attested v1 bundle binds one
environment and revision to immutable backup, restore-drill and clone/catalog
IDs, UTC timestamps, a non-negative count for every retirement target, and
the exact current target-FK graph SHA-256. The restore drill must name the
same backup artifact ID and hash as the backup; the catalog must name that
backup and the same clone ID as the restore drill.

The whole canonical bundle (except its detached `attestation` envelope) must
be validated by an organisation-controlled public-key or KMS verifier. Trust
material and verifier code are configured outside the evidence file; an
unsigned bundle, unknown key ID, unsupported algorithm or failed signature is
never accepted. The read-only preflight validates those gates together with the
absence of local Registry runtime:

```text
python scripts/rehearse_registry_retirement.py --workspace . --require-ready \
  --expected-environment production-retirement \
  --attestation-verifier organisation_release_verifiers.registry_retirement:verify
```

`MODULE:FUNCTION` is a release-operator supplied trusted verifier that receives
canonical bytes, algorithm, key ID and signature. It must select its public
key/KMS trust root independently of the evidence bundle. The command is
fail-closed when this option is omitted; the in-repository fixture verifier is
test-only and must never be used for a release.

`--require-ready` also derives the exact immutable Git `HEAD` commit from the
workspace and requires a release-operator supplied `--expected-environment`.
Both must exactly match the signed evidence envelope and every evidence
component; a copied bundle for another revision or environment is rejected.
Evidence is valid for at most 24 hours from `attested_at`, allows at most five
minutes of future clock skew, and is rejected as replayed/stale thereafter.
The signed timestamps must be strictly ordered: backup, restore drill, clone
catalog, approved maintenance/writers-stop plan, then attestation. The command
never writes a replay marker, so the bounded attestation lifetime is the
enforced replay window; an operator must create and sign a fresh bundle for
each release window.

If a forward migration has started or the application is unhealthy, rollback
the application release and restore the verified backup/clone procedure. Do
not run `alembic downgrade`: the Alembic history is linear and a downgrade can
reverse unrelated accepted application changes.

## Связанные документы

- [RUNBOOK_INCIDENT_DB_RECOVERY.md](RUNBOOK_INCIDENT_DB_RECOVERY.md) — действия при инциденте.
- [DATABASE.md](DATABASE.md) — миграции и конфигурация БД.

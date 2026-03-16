-- Migration 035: Playbook run — idempotency_key, индекс для планировщика (Этап 6)
-- Применить от пользователя с правами на запись. Либо: alembic upgrade head

BEGIN;

ALTER TABLE playbook_run ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);

-- Частичный уникальный индекс: один ключ — один run, несколько NULL допустимы
CREATE UNIQUE INDEX ix_playbook_run_idempotency_key
ON playbook_run (idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_playbook_run_status_scheduled_at
ON playbook_run (status, scheduled_at);

COMMIT;

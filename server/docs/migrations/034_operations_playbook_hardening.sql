-- Migration 034: Operations — command_name, timeout_override_sec, playbook_run_id (Этап 5 Hardening)
-- Применить от пользователя с правами на запись. Либо: alembic upgrade head

BEGIN;

ALTER TABLE operations ADD COLUMN IF NOT EXISTS command_name VARCHAR(64);
ALTER TABLE operations ADD COLUMN IF NOT EXISTS timeout_override_sec INTEGER;
ALTER TABLE operations ADD COLUMN IF NOT EXISTS playbook_run_id BIGINT REFERENCES playbook_run(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_operations_command_name ON operations (command_name);

COMMIT;

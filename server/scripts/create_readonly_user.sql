-- Создание read-only пользователя для доступа к БД pc_client извне
-- (например, для второго чат-агента).
-- Запуск: sudo -u postgres psql -d pc_client -f create_readonly_user.sql
-- Перед запуском замените REPLACE_WITH_STRONG_PASSWORD на свой пароль в строке ниже.

CREATE ROLE pc_client_ro WITH LOGIN PASSWORD 'REPLACE_WITH_STRONG_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- Подключение к БД pc_client
GRANT CONNECT ON DATABASE pc_client TO pc_client_ro;

-- Переключиться в pc_client (нужно для GRANT на public; при запуске psql -d pc_client уже в ней)
\connect pc_client

-- Права на схему public (все таблицы приложения в ней)
GRANT USAGE ON SCHEMA public TO pc_client_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pc_client_ro;

-- Права на будущие таблицы (созданные от имени текущего владельца, обычно postgres)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pc_client_ro;

-- Последовательности: только чтение текущего значения (для совместимости; при только SELECT по таблицам не обязаны)
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO pc_client_ro;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO pc_client_ro;

-- Готово
SELECT 'Read-only user pc_client_ro created. Grant SELECT on public.' AS result;

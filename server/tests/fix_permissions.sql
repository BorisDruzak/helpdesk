-- Скрипт для исправления прав на схему public в тестовой БД
-- Выполнить от имени суперпользователя PostgreSQL:
-- sudo -u postgres psql -d pc_support_test -f fix_permissions.sql

GRANT CREATE ON SCHEMA public TO chatbot;
GRANT USAGE ON SCHEMA public TO chatbot;
ALTER SCHEMA public OWNER TO chatbot;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chatbot;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chatbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatbot;

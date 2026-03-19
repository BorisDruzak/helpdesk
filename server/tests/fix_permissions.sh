#!/bin/bash
# Скрипт для исправления прав на схему public в тестовой БД
# Требует прав суперпользователя PostgreSQL

set -e

DB_NAME="pc_support_test"
DB_USER="${DB_USER:-chatbot}"

echo "Fixing permissions for test database: $DB_NAME"
echo "This script requires PostgreSQL superuser privileges"
echo ""

# Проверяем, можем ли мы подключиться как postgres
if ! sudo -u postgres psql -c "SELECT 1" > /dev/null 2>&1; then
    echo "❌ Cannot connect as postgres user"
    echo "   Try: sudo -u postgres psql -d $DB_NAME -f fix_permissions.sql"
    exit 1
fi

# Выдаем права на схему public
echo "Granting permissions on public schema..."
sudo -u postgres psql -d $DB_NAME <<EOF
GRANT CREATE ON SCHEMA public TO $DB_USER;
GRANT USAGE ON SCHEMA public TO $DB_USER;
ALTER SCHEMA public OWNER TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

echo "✅ Permissions granted"
echo ""
echo "You can now run tests:"
echo "  cd server"
echo "  TEST_DATABASE_URL='postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test' pytest tests/ -v"


#!/bin/bash
# Скрипт для подготовки тестовой БД

set -e

DB_NAME="pc_support_test"
DB_USER="${DB_USER:-chatbot}"
DB_PASSWORD="${DB_PASSWORD:-chatbot}"
DB_HOST="${DB_HOST:-example.test}"
DB_PORT="${DB_PORT:-5432}"

echo "Creating test database: $DB_NAME"

# Создаем БД если не существует (требует прав суперпользователя)
# Если нет прав, попробуем создать через существующего пользователя
if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null; then
    echo "Database $DB_NAME created"
else
    echo "Database $DB_NAME already exists or creation failed (may need superuser)"
fi

# Выдаем права на схему public (критично для PostgreSQL 15+)
echo "Granting permissions on public schema..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF 2>/dev/null || echo "Note: Some permissions may require superuser"
-- Выдаем права на схему public
GRANT USAGE ON SCHEMA public TO $DB_USER;
GRANT CREATE ON SCHEMA public TO $DB_USER;

-- Выдаем права на все существующие объекты
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;

-- Выдаем права на будущие объекты
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

echo "Test database $DB_NAME is ready"
echo ""
echo "⚠️  Если тесты все еще не работают, выдайте права через суперпользователя:"
echo "   sudo -u postgres psql -d $DB_NAME -c \"GRANT CREATE ON SCHEMA public TO $DB_USER;\""
echo ""
echo "Run migrations with: TEST_DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME pytest server/tests/"

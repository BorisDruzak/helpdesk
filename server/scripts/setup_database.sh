#!/bin/bash
# Database setup script for PC Client Server
# This script creates the PostgreSQL database and runs migrations

set -e  # Exit on error

echo "=========================================="
echo "PC Client Server - Database Setup"
echo "=========================================="
echo ""

# Configuration
DB_NAME=${DB_NAME:-pc_client}
DB_USER=${DB_USER:-chatbot}
DB_PASSWORD=${DB_PASSWORD:-chatbot}
DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-5432}

# Construct DATABASE_URL
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "Configuration:"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: $DB_HOST:$DB_PORT"
echo ""

# Step 1: Check if PostgreSQL is running
echo "Step 1: Checking PostgreSQL status..."
if ! systemctl is-active --quiet postgresql; then
    echo "❌ PostgreSQL is not running"
    echo "   Start with: sudo systemctl start postgresql"
    exit 1
fi
echo "✅ PostgreSQL is running"
echo ""

# Step 2: Create database and user (if needed)
echo "Step 2: Creating database and user..."
echo "   (This will prompt for postgres user password if needed)"

sudo -u postgres psql -c "SELECT 1" > /dev/null 2>&1 || {
    echo "❌ Cannot connect to PostgreSQL"
    exit 1
}

# Create user if not exists
sudo -u postgres psql <<EOF
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
        RAISE NOTICE 'User $DB_USER created';
    ELSE
        RAISE NOTICE 'User $DB_USER already exists';
    END IF;
END
\$\$;
EOF

# Create database if not exists
sudo -u postgres psql <<EOF
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')
\gexec
EOF

# Grant privileges
sudo -u postgres psql <<EOF
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "✅ Database and user ready"
echo ""

# Step 3: Test connection
echo "Step 3: Testing connection..."
if PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1; then
    echo "✅ Connection successful"
else
    echo "❌ Connection failed"
    exit 1
fi
echo ""

# Step 4: Check Python dependencies
echo "Step 4: Checking Python dependencies..."
cd "$(dirname "$0")/.."

if ! python3 -c "import sqlalchemy, asyncpg, alembic" 2>/dev/null; then
    echo "⚠️  Missing dependencies. Installing..."
    pip install -r requirements.txt
else
    echo "✅ Dependencies installed"
fi
echo ""

# Step 5: Run migrations
echo "Step 5: Running database migrations..."
alembic upgrade head
echo "✅ Migrations complete"
echo ""

# Step 6: Verify schema
echo "Step 6: Verifying schema..."
TABLES=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public';")

if echo "$TABLES" | grep -q "job_events"; then
    echo "✅ job_events table exists"
else
    echo "❌ job_events table not found"
    exit 1
fi

# Show table info
echo ""
echo "Table structure:"
PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -c "\d job_events"

echo ""
echo "=========================================="
echo "✅ Database setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Create .env file with DATABASE_URL:"
echo "     export DATABASE_URL=\"$DATABASE_URL\""
echo ""
echo "  2. Start server:"
echo "     cd /var/chat_bot/pc_client/server"
echo "     export DATABASE_URL=\"$DATABASE_URL\""
echo "     python server.py"
echo ""
echo "  3. Check database:"
echo "     psql -U $DB_USER -d $DB_NAME"
echo "     SELECT COUNT(*) FROM job_events;"
echo ""





# Protocol V3 Integration Tests

Интеграционные тесты для Protocol V3 системы.

## Подготовка БД

1. Создайте тестовую БД:
```bash
cd server/tests
./setup_test_db.sh
```

Или вручную:
```bash
createdb -U chatbot pc_support_test
```

2. Убедитесь, что переменная окружения `TEST_DATABASE_URL` указывает на тестовую БД:
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test"
```

## Запуск тестов

```bash
cd server
pytest tests/ -v
```

Или с явным указанием БД:
```bash
TEST_DATABASE_URL="postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test" pytest tests/ -v
```

## Структура тестов

- `conftest.py` - фикстуры pytest (migrations, cleanup, test_app, test_client, test_agent)
- `test_helpers.py` - вспомогательные функции (wait_for_operation_terminal, create_test_ticket)
- `test_modules/` - тестовые модули (echo, fail)
- `test_integration_p0.py` - P0 (Critical) тесты
- `test_integration_p1.py` - P1 (Important) тесты (TODO)

## Тестовые модули

- `test_echo` - модуль с tool `echo(message)` возвращает `{"echo": message}`
- `test_fail` - модуль с tool `fail(error_code)` выбрасывает исключение

## Важные замечания

1. **БД Guard**: Все тесты проверяют, что `TEST_DATABASE_URL` указывает на `pc_support_test`
2. **Cleanup**: Перед каждым тестом выполняется `TRUNCATE ... RESTART IDENTITY CASCADE`
3. **Migrations**: Миграции применяются один раз на сессию через фикстуру `run_migrations`
4. **Agent**: WSAgent запускается in-process с патченным config для использования тестовых модулей

## Известные проблемы и исправления

### Исправленные ошибки

1. ✅ **Импорты в test_integration_p0.py** - исправлен импорт `test_helpers`
2. ✅ **Импорты в test_modules** - добавлен путь к `pc_agent` перед импортом `BaseCollector`
3. ✅ **Pytest сбор тестов** - создан `pytest.ini` для исключения `test_modules` из автоматического сбора

### Требует внимания

⚠️ **Права на схему public** - в PostgreSQL 15+ требуется явно выдать права на схему public:

```bash
# Вариант 1: Использовать скрипт (требует sudo):
cd server/tests
sudo ./fix_permissions.sh

# Вариант 2: Вручную через суперпользователя:
sudo -u postgres psql -d pc_support_test <<EOF
GRANT CREATE ON SCHEMA public TO chatbot;
GRANT USAGE ON SCHEMA public TO chatbot;
ALTER SCHEMA public OWNER TO chatbot;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chatbot;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chatbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatbot;
EOF
```

**Проверка прав:**
```bash
PGPASSWORD=chatbot psql -h 192.168.100.17 -p 5432 -U chatbot -d pc_support_test -c "SELECT has_schema_privilege('chatbot', 'public', 'CREATE') as can_create;"
# Должно вернуть: can_create = t (true)
```

Подробные результаты тестирования см. в [TEST_RESULTS.md](TEST_RESULTS.md).

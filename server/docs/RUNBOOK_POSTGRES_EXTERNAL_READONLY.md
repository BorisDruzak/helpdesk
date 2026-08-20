# Runbook: Доступ к PostgreSQL извне (read-only для другого чат-агента)

Цель: разрешить второму чат-агенту подключаться к БД сервера **только на чтение** (SELECT).  
Используется БД `pc_client`, пользователь по умолчанию приложения — `chatbot`.

---

## 1. Параметры PostgreSQL

### 1.1. listen_addresses

PostgreSQL по умолчанию слушает только `localhost`. Нужно разрешить приём подключений на нужном интерфейсе.

**Где искать конфиг:**

- Linux (пакет): часто `/etc/postgresql/<ver>/main/postgresql.conf` или `/var/lib/pgsql/<ver>/data/postgresql.conf`
- ALT Linux: `/var/lib/pgsql/data/postgresql.conf` или через `postgresql-setup`

**Изменить:**

```ini
# Было (по умолчанию):
# listen_addresses = 'localhost'

# Вариант 1: слушать на всех интерфейсах
listen_addresses = '*'

# Вариант 2: только на конкретном IP (безопаснее)
# listen_addresses = 'example.test'
```

После правки — перезапуск PostgreSQL (или `pg_ctl reload`, если параметр допускает reload; `listen_addresses` требует **restart**):

```bash
sudo systemctl restart postgresql
# или
sudo systemctl restart postgresql-15   # подставьте свою версию
```

---

## 2. pg_hba.conf — кто может подключаться

Добавьте правило, разрешающее доступ **только** для read-only пользователя с нужных адресов.

**Где файл:** рядом с `postgresql.conf`, например `/var/lib/pgsql/data/pg_hba.conf` или `/etc/postgresql/<ver>/main/pg_hba.conf`.

**Добавить в конец (подставьте свои значения):**

```text
# Read-only доступ для внешнего чат-агента (IPv4)
# TYPE  DATABASE   USER            ADDRESS              METHOD
host    pc_client  pc_client_ro    <IP_или_подсеть>     scram-sha-256
```

Примеры:

- Один хост: `192.168.1.100/32`
- Подсеть: `192.168.1.0/24`
- Любой хост (только для теста в изолированной сети): `0.0.0.0/0`

Метод `scram-sha-256` — рекомендуемый (пароль передаётся по SCRAM-SHA-256).

Применить без перезапуска:

```bash
sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

---

## 3. Firewall (порт 5432)

Разрешить входящие подключения на порт PostgreSQL (5432) с нужных IP.

**firewalld:**

```bash
# Разрешить с одного IP
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.100" port port="5432" protocol="tcp" accept'

# Или с подсети
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="5432" protocol="tcp" accept'

sudo firewall-cmd --reload
```

**iptables (пример):**

```bash
sudo iptables -A INPUT -p tcp -s 192.168.1.0/24 --dport 5432 -j ACCEPT
# Сохранить правила (зависит от дистрибутива): iptables-save, netfilter-persistent и т.д.
```

**nftables:** добавьте правило для `tcp dport 5432` с нужным `ip saddr`.

---

## 4. Read-only пользователь в БД

Создать пользователя и выдать ему только SELECT по схеме `public` (все таблицы приложения в ней).

**Выполнить от суперпользователя БД (обычно `postgres`):**

```bash
sudo -u postgres psql -d pc_client -f /path/to/server/scripts/create_readonly_user.sql
```

Либо вручную подставить пароль и выполнить SQL из скрипта (см. ниже).

**Скрипт:** `server/scripts/create_readonly_user.sql` — создаёт пользователя `pc_client_ro`, выдаёт ему CONNECT на БД, USAGE и SELECT на схему `public` (все текущие и будущие таблицы).

**Вариант одной командой (подставьте свой пароль вместо `YourStrongPassword`):**

```bash
sudo -u postgres psql -d pc_client -c "
CREATE ROLE pc_client_ro WITH LOGIN PASSWORD 'YourStrongPassword' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE pc_client TO pc_client_ro;
GRANT USAGE ON SCHEMA public TO pc_client_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pc_client_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pc_client_ro;
"
```

Пароль в скрипте-файле — заглушка: замените `REPLACE_WITH_STRONG_PASSWORD` и не коммитьте пароль в репозиторий.

---

## 5. Итоговые данные для подключения (второй агент)

После выполнения шагов 1–4:

| Параметр   | Значение |
|-----------|----------|
| **Host**  | IP или hostname сервера, где крутится PostgreSQL (например `example.test`) |
| **Port**  | `5432` (или другой, если меняли в postgresql.conf) |
| **User**  | `pc_client_ro` |
| **Password** | тот, что задали при создании пользователя |
| **Database** | `pc_client` |

**Строка подключения (для клиентов, ожидающих обычный postgres URL):**

```text
postgresql://pc_client_ro:YOUR_PASSWORD@example.test:5432/pc_client
```

Для asyncpg (Python):

```text
postgresql://pc_client_ro:YOUR_PASSWORD@example.test:5432/pc_client
```

(Тот же URL; asyncpg использует стандартный формат.)

---

## 6. Проверка

С другой машины (или с хоста второго агента):

```bash
psql "postgresql://pc_client_ro:YOUR_PASSWORD@example.test:5432/pc_client" -c "SELECT 1;"
psql "postgresql://pc_client_ro:YOUR_PASSWORD@example.test:5432/pc_client" -c "SELECT COUNT(*) FROM tickets;"
```

Попытка записи должна завершаться ошибкой:

```bash
psql "..." -c "DELETE FROM tickets LIMIT 1;"
# ERROR: permission denied for table tickets
```

---

## 7. Устранение неполадок (пароль / pg_hba)

**Симптом:** с другого хоста (например 10.10.10.2) при подключении под `pc_client_ro` — «пользователь не прошёл проверку подлинности (пароль)» или «pg_hba.conf нет записи для … без шифрования».

**Причины:** (1) пароль роли не был задан или задан иначе; (2) в `pg_hba.conf` нет правила для вашего IP и пользователя.

**Выполнить на сервере, где запущен PostgreSQL (example.test), от суперпользователя `postgres`.**

### 7.1. Задать/сбросить пароль для pc_client_ro

```bash
sudo -u postgres psql -d pc_client -c "ALTER ROLE pc_client_ro PASSWORD '1.Abcdef';"
```

Если роли `pc_client_ro` ещё нет — создать и выдать права:

```bash
sudo -u postgres psql -d pc_client -c "
CREATE ROLE pc_client_ro WITH LOGIN PASSWORD '1.Abcdef' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE pc_client TO pc_client_ro;
GRANT USAGE ON SCHEMA public TO pc_client_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pc_client_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pc_client_ro;
"
```

### 7.2. Добавить в pg_hba.conf правило для вашего IP

Файл: `/var/lib/pgsql/data/pg_hba.conf` или `/etc/postgresql/<ver>/main/pg_hba.conf`. Добавить **в конец** (для клиента 10.10.10.2):

```text
# Доступ read-only с хоста 10.10.10.2 (без SSL — сервер не настроен на SSL)
host    pc_client  pc_client_ro    10.10.10.2/32    scram-sha-256
```

Если сервер старый и выдаёт ошибку про scram-sha-256, попробовать:

```text
host    pc_client  pc_client_ro    10.10.10.2/32    md5
```

Перезагрузить конфиг PostgreSQL:

```bash
sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

### 7.3. Проверка с клиента (10.10.10.2)

```bash
psql "postgresql://pc_client_ro:1.Abcdef@example.test:5432/pc_client" -c "SELECT 1;"
psql "postgresql://pc_client_ro:1.Abcdef@example.test:5432/pc_client" -c "SELECT COUNT(*) FROM tickets;"
```

Через Python (psycopg):

```python
import psycopg
conn = psycopg.connect("postgresql://pc_client_ro:1.Abcdef@example.test:5432/pc_client")
print(conn.execute("SELECT 1").fetchone())
print(conn.execute("SELECT COUNT(*) FROM tickets").fetchone())
conn.close()
```

**Примечание:** SSL на сервере не включён — подключаться без `sslmode` (или `sslmode=disable`). Не использовать `sslmode=require`, пока сервер не настроен на SSL.

---

## 8. Безопасность (кратко)

- Ограничьте в `pg_hba.conf` и firewall только нужные IP/подсети (например `10.10.10.2/32`), не открывайте 5432 в интернет без необходимости.
- Используйте стойкий пароль для `pc_client_ro`, храните его в секретах второго агента (переменные окружения, vault), не в коде.
- Пароль в логах не выводить; в конфиге второго агента использовать переменную окружения (например `READONLY_DATABASE_URL`).

---

## Связанные документы

- [DATABASE.md](DATABASE.md) — схема БД, таблицы, миграции.
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — аутентификация сервера (основной пользователь `chatbot`).

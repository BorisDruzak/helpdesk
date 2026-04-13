# Аутентификация и безопасность — Protocol V3

## Обзор

PC Agent использует **Bearer-токен аутентификацию** при подключении к серверу. Токен передаётся в handshake при установлении WebSocket соединения. Сервер валидирует токен и может закрыть соединение с кодом `4003` при невалидной аутентификации.

## Источники токена

Агент проверяет наличие токена в следующем порядке:

| № | Источник | Описание |
|---|----------|----------|
| 1 | **ENV `AUTH_TOKEN`** | Переменная окружения. Наивысший приоритет. При наличии сохраняется в БД агента. |
| 2 | **Таблица `auth_tokens`** | Основной персистентный источник. Хранит токены в SQLite `storage.db`. |
| 3 | **identity.json** | Legacy. Токен в поле `token`. Не рекомендуется — основной источник теперь БД. |

### Переменная окружения AUTH_TOKEN

```bash
# Запуск с токеном из ENV (для CI, systemd, headless)
export AUTH_TOKEN="your_jwt_or_bearer_token"
python ws_agent.py --no-gui
```

**Важно:**
- При наличии `AUTH_TOKEN` токен автоматически сохраняется в таблицу `auth_tokens` для последующих запусков.
- Используйте для автоматизированных развёртываний (systemd, Docker, CI).

### Таблица auth_tokens (БД)

Токены хранятся в `data/storage.db` в таблице `auth_tokens`:

- `token` — уникальный токен (UNIQUE)
- `device_id` — UUID агента
- `is_active` — флаг активности (1 = активен)
- `created_at`, `last_used_at` — метки времени

**API:**
- `DatabaseManager.save_auth_token(token, device_id)` — сохранить/обновить токен
- `DatabaseManager.get_auth_token(device_id)` — получить активный токен
- `DatabaseManager.clear_auth_token(device_id)` — очистить токен при ошибке авторизации

Подробнее: [DATABASE.md](DATABASE.md#таблица-auth_tokens).

### identity.json (legacy)

Структура файла `data/identity.json`:
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "machine_id": "550e8400-e29b-41d4-a716-446655440000",
  "install_id": "11111111-2222-4333-8444-555555555555",
  "machine_id_source": "windows_machine_guid",
  "token": null
}
```

- **machine_id** — канонический стабильный идентификатор устройства. Именно он используется как `device_id` в handshake и как ключ в локальной таблице `auth_tokens`.
- **uuid** — обратнос совместимый алиас, должен совпадать с `machine_id`.
- **install_id** — вторичный идентификатор конкретной инсталляции. Не используется как primary auth identity и может меняться при переустановке или удалении `identity.json`.
- **machine_id_source** — откуда получен machine seed (`windows_machine_guid`, `linux_machine_id`, `env`, `fallback_file`).
- **token** — legacy-поле; основной persistent storage токена остаётся в SQLite.

### Каноническая identity-модель

Начиная с production identity v1 агент использует схему:

- `machine_id` — каноническая identity устройства;
- `install_id` — secondary identity конкретной установки;
- top-level `device_id` в Protocol V3 всегда равен `machine_id`.

Это означает:

1. Удаление `identity.json` больше не должно создавать новый логический агент на том же устройстве.
2. При повторной регистрации после удаления `identity.json` агент должен прийти с тем же `machine_id`, но с новым `install_id`.
3. Сервер может использовать `install_id` только для диагностики, аудита, controlled reprovision и UI summary, но не как источник auth identity.

### Как агент получает machine_id

Приоритет источников стабильного `machine_id`:

1. `PC_AGENT_MACHINE_ID` — явный override для тестов и управляемых инсталляций;
2. Windows: `HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid`;
3. Linux: `/etc/machine-id` или `/var/lib/dbus/machine-id`;
4. fallback file вне `identity.json`, если системный источник недоступен.

`identity.json` больше не является источником machine identity. Он хранит только локальный снимок уже вычисленного `machine_id` и текущий `install_id`.

## Handshake и аутентификация

При установлении WebSocket соединения агент отправляет handshake:

```json
{
  "type": "handshake",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "payload": {
    "uuid": "device_uuid",
    "machine_id": "device_uuid",
    "install_id": "install_uuid",
    "machine_id_source": "windows_machine_guid",
    "hostname": "my-pc",
    "os": "Linux",
    "agent_version": "3.0.0",
    "db_schema_version": 9,
    "toolset_hash": "a1b2c3d4e5f6",
    "tools_count": 10,
    "modules": ["system", "screen"],
    "modules_inventory": [...]
  }
}
```

**Критично:**
- Токен передаётся в top-level поле `token`.
- `device_id` и `payload.machine_id` должны описывать одно и то же устройство.
- `payload.install_id` передаётся как secondary metadata и не должен использоваться сервером как primary identity.
- При отсутствии токена поле `token` может быть `null` — сервер зарегистрирует попытку подключения.

## Обработка ошибок аутентификации

Сервер может закрыть WebSocket с кодом **4003** при невалидном токене:

- Агент логирует: `Ошибка аутентификации при handshake`
- Если GUI **не** включен: токен очищается в памяти и в БД, запрашивается ввод через консоль.
- Если GUI включен: показывается диалог авторизации, токен не очищается автоматически.

## Поведение при отсутствии токена

**Агент не блокирует запуск**, если токена нет:

1. Агент подключается к серверу.
2. Сервер регистрирует попытку подключения (например, в `pending_connections`).
3. Администратор может выдать токен через панель сервера.
4. Пользователь вводит токен через GUI или ENV и переподключается.

## GUI и диалог авторизации

При `ui.autostart_gui: true`:

- До запуска WebSocket показывается диалог ввода логина/пароля или токена.
- Токен проверяется через `GET /api/agents` с заголовком `Authorization: Bearer {token}`.
- При успехе (200/404) токен сохраняется в БД через `save_auth_token_sync`.
- Агент запускается с уже загруженным токеном.

## device_id, machine_id и install_id

**Protocol V3 (identity v1):**

- `device_id` всегда равен каноническому `machine_id`;
- `machine_id` должен быть стабильным UUID и переживать удаление `identity.json`;
- `install_id` тоже UUID, но допускает смену при переустановке/перерегистрации инсталляции;
- IdentityManager валидирует оба значения, но primary identity сервера строится только по `machine_id`.

Подробнее: [core/identity.py](../core/identity.py).

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `AUTH_TOKEN` | Bearer-токен для аутентификации. Приоритет над БД и identity.json. |

## Рекомендации по безопасности

1. **Production:** используйте WSS (WebSocket over TLS) и HTTPS для API.
2. **Токены:** предпочтительно JWT с временем жизни; ротация при необходимости.
3. **Хранение:** `auth_tokens` в SQLite — обеспечьте права доступа к `data/storage.db`.
4. **identity.json:** не храните чувствительные данные; UUID допустим.
5. **Логирование:** не логируйте полный токен; достаточно префикса (первые 12 символов).

## Ссылки

- [PROTOCOL_V3.md](PROTOCOL_V3.md) — протокол WebSocket
- [DATABASE.md](DATABASE.md) — таблица auth_tokens
- [README.md](README.md) — быстрый старт

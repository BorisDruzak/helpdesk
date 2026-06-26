# Аутентификация и безопасность — Protocol V3

## Обзор

PC Agent использует **Bearer-токен аутентификацию** при подключении к серверу. Токен передаётся в handshake при установлении WebSocket соединения. Сервер валидирует токен и может закрыть соединение с кодом `4003` при невалидной аутентификации.

Requester account-session tokens are separate from the machine Bearer token. For admin-approved other-account login, the agent receives the session token once by polling `/api/registry/agent/account-login-requests/{request_id}`; the server stores only a durable encrypted delivery envelope until that poll atomically marks the request delivered.

## Источники токена

Агент проверяет наличие токена в следующем порядке:

| № | Источник | Описание |
|---|----------|----------|
| 1 | **ENV `AUTH_TOKEN`** | Переменная окружения. Наивысший приоритет. При наличии сохраняется в БД агента. |
| 2 | **Таблица `auth_tokens`** | Основной персистентный источник. Хранит токены в SQLite `storage.db`; lookup идёт сначала по каноническому `machine_id`, а затем по legacy secondary ID (`install_id`, исторический `uuid`) для controlled migration. |
| 3 | **identity.json** | Legacy. Токен в поле `token`. Не рекомендуется — основной источник теперь БД. |

Для Windows portable/release launcher действует дополнительный локальный fallback: если агент стартует из отдельного `data_root` (например `pc_agent/dist/data`) без собственного токена, launcher может импортировать активный токен из primary install `%LOCALAPPDATA%\PCClientAgent\data`, но только при совпадающем `machine_id`.

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

**Migration rule:**
- После перехода на canonical `machine_id` агент при чтении локального токена обязан проверять цепочку `machine_id -> install_id -> legacy uuid`.
- Если активный токен найден под legacy install-based ID, агент локально дублирует его под канонический `machine_id`, чтобы следующий запуск уже шёл без fallback.

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
4. Если локальная БД ещё хранит токен под legacy install-based ID, агент должен корректно мигрировать его на канонический `machine_id` без запроса нового токена у пользователя.

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

### Controlled migration legacy install-based token -> machine_id

Во время перехода со старой install-based identity на canonical `machine_id` допустим специальный серверный путь:

- в записи токена в БД сервера `device_id` ещё равен legacy `install_id`;
- агент в top-level `device_id` и `payload.machine_id` уже передаёт канонический `machine_id`;
- `payload.install_id` совпадает с `device_id` токена.

В этом случае сервер во время handshake имеет право один раз перепривязать активный token binding с legacy `install_id` на canonical `machine_id`, записать это в runtime audit и продолжить handshake без ручного перевыпуска токена. Это миграционный сценарий, а не новая постоянная identity-модель.

Перед такой перепривязкой сервер проверяет stored device fingerprint для target `machine_id`, если он уже есть в БД, и обновляет токен только если он всё ещё привязан к исходному provisioning/legacy `device_id`. При fingerprint mismatch сервер закрывает handshake с **4003** и не меняет `agent_tokens.device_id`; агент должен пройти обычный recovery/provisioning flow, а не продолжать с перепривязанным токеном.

## Обработка ошибок аутентификации

Сервер может закрыть WebSocket с кодом **4003** при невалидном токене:

- Агент логирует: `Ошибка аутентификации при handshake`
- Если GUI **не** включен: токен очищается в памяти и в БД, после чего запускается automatic reprovision через `POST /api/connection_request`.
- Если GUI включен: токен тоже очищается, но агент уходит в тот же GUI-driven connection request flow; ручной ввод raw token больше не является обязательным сценарием восстановления.
- Server-side observer now exposes this path through `agent_runtime_audit`: invalid/revoked token and handshake auth failures project as `root_kind=agent_auth`, while connection-request/token-delivery/fingerprint steps project as `root_kind=device_provisioning`. Debug from the server with `observer/search?q=invalid_token` or `observer/search?q=connection_request`.
- If the server has no explicit `server_config.connection_policy`, provisioning defaults to manual approval. Automatic `accept_all` issuance requires an explicit policy or `ALLOW_INSECURE_DEV_DEFAULTS=true` in local insecure dev.

## Поведение при отсутствии токена

**Агент не блокирует запуск**, если токена нет:

1. Агент подключается к серверу.
2. Сервер регистрирует попытку подключения (например, в `pending_connections`).
3. Администратор может выдать токен через панель сервера.
4. Пользователь вводит токен через GUI или ENV и переподключается.

### Архивированное устройство и повторный provisioning

Если сервер отклоняет connection request с причиной `DEVICE_ARCHIVED`, агент должен:

- показать пользователю понятное сообщение об архивированном устройстве;
- не создавать «вечную» локальную блокировку через `connection_rejected.flag`;
- позволить повторный provisioning после административного восстановления устройства или смены identity на новом устройстве.

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
Security update 2026-05-23:
- Agents no longer obtain machine tokens through unauthenticated `POST /api/login`. That endpoint is admin-only server-side compatibility.
- Automatic reprovisioning uses `POST /api/connection_request`. In manual policy mode the server returns `request_id` and one-time `poll_secret`; the agent keeps them in memory and sends both on heartbeat/status polling.
- If the same `device_id` already has an active server-side agent token, manual no-token `POST /api/connection_request` is treated as already authorized and returns no raw token or poll credentials. The old token must be revoked before intentional reprovision.
- If the server returns `POLL_SECRET_REQUIRED` or `INVALID_POLL_SECRET`, the agent treats the old pending request as unusable and creates a fresh request. Raw tokens and poll secrets must not be logged.

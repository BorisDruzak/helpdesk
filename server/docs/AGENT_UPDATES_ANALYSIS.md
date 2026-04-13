# Анализ: production-ready обновление агента через сервер

**Дата обновления:** 2026-04-13  
**Цель:** зафиксировать текущее production-состояние remote self-update после hardening launcher/API/UI и описать, что считается обязательной проверкой перед релизом.

---

## 1. Что теперь считается канонической схемой

Обновление агента в production идёт не через замену работающего `exe` "на месте", а через связку:

1. Сервер хранит versioned build-артефакты и выдаёт их по защищённому HTTP download.
2. Сервер создаёт materialized operation `agent_update` и кладёт команду `update` в `device_outbox`.
3. Агент скачивает артефакт, пишет `pending_update.json`, отправляет `command_result=status=success` со стадией `scheduled` и инициирует **graceful shutdown** с exit code `42`.
4. Launcher, живущий отдельно от основного бинаря агента, видит `pending_update.json` или exit `42`, применяет update через staging, делает `--verify`, публикует новую версию или выполняет rollback.
5. После следующего handshake агент сообщает серверу итог последней попытки self-update:
   - success: `applied_update_version`, `last_update_operation_id`
   - failure: `failed_update_version`, `failed_update_operation_id`, `failed_update_reason`, `failed_update_at`, `failed_update_message`
6. Только после этого сервер финализирует `agent_update` операцию как `succeeded` или `failed`.

Это значит, что реальным подтверждением обновления считается **не момент постановки команды**, а **следующий handshake новой или откатившейся версии**.

---

## 2. Что уже доведено до production-ready уровня

### 2.1 Сервер

| Компонент | Статус | Что важно |
|-----------|--------|-----------|
| `POST /api/agent_builds/upload` | ✅ | Только `admin`, upload ZIP/tar.gz, валидация `archive_type`, запись метаданных в БД. |
| `GET /api/agent_builds` | ✅ | Требует auth, отдаёт build metadata для UI: `artifact_filename`, `archive_type`, `mime_type`, `sha256`, `size`. |
| `GET /api/agent_builds/{target}/{channel}/{version}/download` | ✅ | Bearer auth, `ETag`, `Content-Disposition`, audit download. |
| `POST /api/devices/{device_id}/agent/update` | ✅ | Создаёт `agent_update`, кладёт `update` в outbox, принимает `reason`, отдаёт operation object. |
| `POST /api/agents/update_bulk` | ✅ | Массовый rollout с canary-gate, audit, optional `reason`, per-device operations. |
| `GET /api/devices/{device_id}/agent/update_diagnostics` | ✅ | Возвращает статус устройства, update summary, recent operations, timeline runtime audit и problem logs. |
| Handshake finalization | ✅ | Операция закрывается только на handshake success/failure-report от launcher/агента. |
| SLA для `agent_update` | ✅ | Увеличены `accepted/execution` timeout'ы под длительный update-flow. |

### 2.2 Агент

| Компонент | Статус | Что важно |
|-----------|--------|-----------|
| Приём команды `update` | ✅ | Проверка роли, download URL, `sha256`, `archive_type`, optional `reason`. |
| Download артефакта | ✅ | Bearer из device token, проверка `sha256` и размера. |
| `pending_update.json` | ✅ | Хранит `operation_id`, `requested_by`, `requested_reason`, target/channel/version и путь к артефакту. |
| Shutdown под update | ✅ | Вместо жёсткого `os._exit()` используется управляемый shutdown path с exit code `42`. |
| Handshake report | ✅ | На новом подключении агент сообщает последний success/failure update-result. |

### 2.3 Launcher

| Компонент | Статус | Что важно |
|-----------|--------|-----------|
| Versioned install layout | ✅ | `install_root/versions/<version>/`, а не in-place замена текущего бинаря. |
| `apply_update()` | ✅ | Распаковка в staging, backup БД, `--verify`, publish новой версии, rollback при fail. |
| `update_history.json` | ✅ | Хранит success/failure историю с `operation_id`, причиной и временем. |
| Обработка failed pending | ✅ | Битый/неприменимый `pending_update.json` архивируется в `last_failed_pending_update.json` и не ретраится бесконечно. |
| Cleanup policy | ✅ | Чистятся старые downloads/backups, чтобы update-flow не разрастался бесконтрольно. |

### 2.4 Admin UI

В `http://192.168.100.17:8666/admin` раздел Agent Updates теперь включает:

- загрузку билдов;
- запуск single-device update;
- bulk/canary rollout;
- confirm modal с причиной действия;
- живую диагностику выбранного устройства;
- summary последнего update-state;
- recent operations по `agent_update`;
- timeline runtime audit;
- problem logs по устройству/hostname;
- отображение ошибок запроса и ошибок последней неуспешной попытки update.

---

## 3. Что теперь считается обязательным для прода

### 3.1 Инварианты релизной схемы

- Всегда запускать агент через launcher, а не напрямую бинарём версии.
- Не считать `command_result scheduled` подтверждением успешного обновления.
- Финализировать `agent_update` только после handshake success/failure-report.
- Не ретраить один и тот же битый `pending_update.json` бесконечно.
- Для массового rollout использовать canary-first.
- В UI и API обязательно передавать `reason` для ручных rollout-операций, когда это осмысленно.

### 3.2 Обязательные проверки перед выкладкой

1. Upload build и list build metadata.
2. Single-device update с новым `operation_id`.
3. Переход операции: `queued/running` -> `succeeded` только после handshake.
4. Негативный сценарий: verify failure или invalid pending -> операция становится `failed`, причина видна в diagnostics/UI.
5. Canary rollout и затем bulk rollout с подтверждением.
6. Проверка admin UI: confirm modal, diagnostics, timeline, logs, error rendering.

---

## 4. Остаточные риски и что контролировать в эксплуатации

- `SERVER_PUBLIC_BASE_URL` обязан быть доступен с устройства агента, иначе download-stage упадёт до применения update.
- Подпись бинарей и/или manifest signature остаётся желательной следующей ступенью hardening, если будет нужен более строгий supply-chain контроль.
- Если устройство нестабильно по сети, важнее смотреть не только operation status, но и timeline/problem logs в diagnostics.
- Для реального production rollout сначала выпускать build в `beta/dev` или через canary на ограниченный пул устройств.

---

## 5. Где смотреть детали

- API и wire contract: [AGENT_UPDATES_API.md](AGENT_UPDATES_API.md)
- Launcher/apply/rollback: [../../pc_agent/docs/SELF_UPDATE.md](../../pc_agent/docs/SELF_UPDATE.md)
- Handshake/report fields: [../../pc_agent/docs/PROTOCOL_V3.md](../../pc_agent/docs/PROTOCOL_V3.md)
- Навигация по модулям: [CODEMAP.md](CODEMAP.md), [../../pc_agent/docs/CODEMAP.md](../../pc_agent/docs/CODEMAP.md)

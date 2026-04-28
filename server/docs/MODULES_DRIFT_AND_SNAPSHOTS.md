# Modules Drift Detection and Toolset Snapshots

## 1. Drift Indicator в modules.html

Drift indicator показывает расхождение между состоянием модуля в БД (`device_modules`) и фактическим наличием tools в toolset snapshot.

### Состояния drift:

1. **✅ OK** (`driftStatus === 'ok'`)
   - Модуль активен (`m.active === true`)
   - И tools присутствуют в toolset (`hasTools === true`)
   - Индикатор: ✅ (зеленая галочка)

2. **⚠️ Active but tools missing** (`driftStatus === 'active_no_tools'`)
   - Модуль активен (`m.active === true`)
   - Но tools отсутствуют в toolset (`hasTools === false`)
   - Индикатор: ⚠️ (желтый треугольник)
   - Tooltip: "Active but tools missing"
   - **Причина**: Модуль помечен как активный, но его tools не загружены в registry агента

3. **⚠️ Tools present but module not active** (`driftStatus === 'tools_no_active'`)
   - Модуль не активен (`m.active === false`)
   - Но tools присутствуют в toolset (`hasTools === true`)
   - Индикатор: ⚠️ (желтый треугольник)
   - Tooltip: "Tools present but module not active"
   - **Причина**: Модуль деактивирован, но его tools все еще в registry (возможно, не был вызван rebuild registry)

### Логика расчета drift:

```javascript
// В renderDeviceDetails() (modules.html:647-662)
const toolsByModule = toolsetData.tools_by_module || {};
const modulesWithDrift = modulesData.modules.map(m => {
    const hasTools = toolsByModule[m.module_name] && toolsByModule[m.module_name].length > 0;
    let driftStatus = null;
    
    if (m.active && !hasTools) {
        driftStatus = 'active_no_tools';  // ⚠️
    } else if (!m.active && hasTools) {
        driftStatus = 'tools_no_active';  // ⚠️
    } else if (m.active && hasTools) {
        driftStatus = 'ok';  // ✅
    }
    
    return { ...m, driftStatus, toolsCount: hasTools ? toolsByModule[m.module_name].length : 0 };
});
```

### Источники данных:

- `modulesData.modules` - из `/api/devices/{device_id}/modules` (таблица `device_modules`)
- `toolsetData.tools_by_module` - из `/api/devices/{device_id}/toolset` (таблица `device_toolset_snapshots`)

---

## 2. Обновление device_toolset_snapshots

### Когда обновляется:

1. **При command_result для list_tools** (автоматически)
   - Файл: `server/websocket/command_result_components.py`
   - Триггер: Агент возвращает результат команды `list_tools`
   - Процесс:
     1. Извлекает `tools_list` из `payload.data.observations.tools`
     2. Сортирует tools (для консистентного hash)
     3. Вычисляет `toolset_hash_server` (SHA256, первые 16 символов)
     4. Вызывает `insert_snapshot_if_not_exists()` (идемпотентно)
     5. Обновляет `devices.current_toolset_hash`, `current_toolset_snapshot_id` и `last_toolset_refresh_at`
     6. **Commit транзакции**

2. **При handshake** (автоматически, если toolset_hash изменился)
   - Файл: `server/websocket/agent_handshake.py`
   - Триггер: Агент подключается и отправляет handshake с `toolset_hash`
   - Процесс:
     1. Сравнивает `agent_toolset_hash` с `device.current_toolset_hash`
     2. Если отличается или отсутствует → enqueue `list_tools` (с rate-limit 10 минут)
     3. Когда `list_tools` выполнится → snapshot обновится (см. пункт 1)

3. **При Sync Modules** (вручную через UI)
   - Файл: `server/modules/handlers.py:1179-1219`
   - Триггер: Пользователь нажимает "Sync Modules" в modules.html
   - Процесс:
     1. Enqueue `list_installed_modules` (для синхронизации `device_modules`)
     2. **Enqueue `list_tools`** (для обновления `device_toolset_snapshots`) ← **ИСПРАВЛЕНО**
     3. Когда `list_tools` выполнится → snapshot обновится (см. пункт 1)

4. **После agent-side lifecycle events** (автоматически)
   - Файл: `server/websocket/outbox_ingest_components.py`
   - Триггер: агент после install/activate/remove/rollback пересобирает runtime registry и отправляет `tools_changed`; `module_state_changed` работает как fallback-сигнал convergence.
   - Процесс:
     1. `module_state_changed` обновляет `device_modules` из embedded snapshot.
     2. `tools_changed` или `module_state_changed` ставит `list_tools` с debounce по pending operation.
     3. Когда `list_tools` выполнится → `device_toolset_snapshots` обновится (см. пункт 1).
   - Ожидаемый результат: auto-install/reconcile install обновляет toolset snapshot без reconnect и без ручного Sync Modules.

### КРИТИЧНО: Commit транзакции

После обновления snapshot **обязательно** вызывается `await session.commit()` внутри post-process слоя `command_result`.

Без commit изменения не сохраняются в БД!

### Идемпотентность:

`insert_snapshot_if_not_exists()` использует UNIQUE constraint на `(device_id, toolset_hash)`:
- Если snapshot с таким hash уже существует → возвращает существующий `snapshot_id`
- Если hash новый → создает новый snapshot
- Повторные вызовы с тем же hash безопасны (не создают дубликаты)

---

## 3. Проверка обновления snapshots

### SQL запрос для проверки:

```sql
-- Последний snapshot для устройства
SELECT 
    snapshot_id,
    device_id,
    toolset_hash,
    tool_count,
    captured_at,
    agent_version
FROM device_toolset_snapshots
WHERE device_id = 'your-device-id'
ORDER BY captured_at DESC
LIMIT 1;

-- Все snapshots для устройства (история изменений)
SELECT 
    snapshot_id,
    toolset_hash,
    tool_count,
    captured_at
FROM device_toolset_snapshots
WHERE device_id = 'your-device-id'
ORDER BY captured_at DESC;
```

### Логи для отладки:

Ищите в логах сервера:
- `[command_result] synced toolset snapshot from list_tools:` - snapshot обновлен
- `[ToolsetSnapshotsRepo] Created snapshot:` - новый snapshot создан
- `[ToolsetSnapshotsRepo] Snapshot already exists:` - snapshot уже существует (идемпотентность)

---

## 4. Troubleshooting

### Проблема: Snapshot не обновляется после Sync Modules

**Причина**: До исправления `handle_sync_modules` отправляла только `list_installed_modules`, но не `list_tools`.

**Решение**: Исправлено - теперь отправляются обе команды.

### Проблема: Snapshot не обновляется после list_tools

**Проверьте**:
1. Есть ли `await session.commit()` в post-process слоя `command_result`
2. Есть ли ошибки в логах при обработке `command_result`
3. Возвращает ли агент корректный формат для `list_tools`:
   ```json
   {
     "status": "success",
     "data": {
       "observations": {
         "tools": [...]
       }
     }
   }
   ```

### Проблема: Drift показывает ⚠️, но модуль работает

**Причина**: Toolset snapshot устарел. Модуль был активирован, но snapshot не обновлен.

**Решение**: Нажмите "Sync Modules" для принудительного обновления snapshot.

### Проблема: `device_modules` пустой, хотя auto-install уже сработал

**Причина**: server-side inventory теперь обновляется в двух местах:
1. из `module_state_changed` через `modules_snapshot`;
2. из `command_result` команды `list_installed_modules`.

Если пусто и после ручного `Sync Modules`, значит нужно смотреть server post-process для `outbox_ingest_components.py` и `command_result_components.py`, а не только enqueue/delivery path.

---

## 5. Builtin vs managed (Этап 10 Playbook)

Для разделения drift по источнику инструментов в snapshot/tools поддерживается поле **origin** у каждого tool (в данных от агента в `list_tools`):

- **builtin** — встроенные инструменты агента (не из модулей).
- **managed** — инструменты из установленных/управляемых модулей.

Правила:

- **Drift-алгоритм**: автоматические действия (например, авто-установка/синхронизация) выполняются только по инструментам с `origin: managed`. Инструменты с `origin: builtin` отображаются только информационно и не триггерят автоматику.
- **UI/API**: при наличии origin в toolset можно выводить отдельные секции drift по builtin и по managed.

Контракт: см. `PLAYBOOK_TOOLS_CONTRACT.md` (поле origin), `PLAYBOOK_STAGES_7_12.md` (этап 10).



## Update 2026-03-11

### Observability
- Device modules view now correlates:
  - actual installed modules (`device_modules`)
  - desired state (`device_desired_modules`)
  - latest toolset snapshot
  - recent module operations
- `GET /api/devices/{device_id}/modules/debug` now surfaces mismatch categories between desired, actual and snapshot state.
- `POST /api/devices/{device_id}/modules/reconcile` is now part of the primary UI flow.

### Rollback convergence (2026-03-11)

- Agent rollback emits `module_state_changed` right after registry rebuild.
- Server rollback updates desired state to the previous active version with `reason=manual_rollback`.
- Expected result: actual state, desired state and debug mismatch views converge without a manual sync step.
## Convergence Guarantees

- After a module lifecycle operation, the server schedules a follow-up inventory and toolset refresh.
- `desired state` is updated immediately for bulk installs and for deletion of the last known module version.
- Expected outcome: `Desired vs Actual`, `Debug mismatch`, and the toolset block should converge without an operator-triggered sync in normal online scenarios.

# Runbook: Drift Recovery модульной системы

## Что такое drift

Расхождение (drift) — ситуация, когда `device_desired_modules` (желаемое состояние) не совпадает с `device_modules` (фактическое состояние от агента).

Типичные причины:
- Агент был офлайн во время install/remove операции.
- Ручное удаление папки модуля на агенте.
- Ошибка установки (SHA mismatch, проблемы платформы).
- Баг в синхронизации.

---

## Диагностика

### 1. Проверить diff через API

```bash
TOKEN=$(curl -s -X POST http://SERVER:PORT/api/ui_login \
  -H "Content-Type: application/json" \
  -d '{"login": "admin", "password": "admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -s "http://SERVER:PORT/api/devices/DEVICE_ID/modules/desired_diff" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Интерпретация поля `diff_status`:
- `ok` — норма
- `missing` — агент не установил модуль (или установил, но данные не дошли)
- `version_mismatch` — установлена другая версия
- `not_removed` — модуль ещё не удалён

### 2. Проверить фактические данные в БД

```sql
-- Desired state устройства
SELECT module_name, desired_version, state, reason, updated_at
FROM device_desired_modules
WHERE device_id = 'DEVICE_ID'
ORDER BY module_name;

-- Actual state устройства
SELECT module_name, version, state, active, last_seen_at, source, last_error_code
FROM device_modules
WHERE device_id = 'DEVICE_ID'
ORDER BY module_name, version;
```

### 3. Проверить debug info

```bash
curl -s "http://SERVER:PORT/api/devices/DEVICE_ID/modules/debug" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Восстановление

### Сценарий 1: Модуль отсутствует на агенте (missing)

Причина: агент был офлайн или install упал.

**Автоматически:** reconcile engine повторит install при следующем запуске (до 5 минут).

**Вручную:**
```bash
# Принудительный немедленный reconcile
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/reconcile" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Сценарий 2: Версия не совпадает (version_mismatch)

Причина: установлена другая версия. Reconcile не сработал из-за ограничений.

**Вручную:** переустановить с `replace_if_exists: true`:
```bash
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/install" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"module_name": "MODULE", "version": "TARGET_VERSION", "replace_if_exists": true}' \
  | python3 -m json.tool
```

### Сценарий 3: Модуль есть, но не отражён в desired (лишний)

Причина: установлен вручную или через legacy API без записи в desired_modules.

**Вариант A:** Принять текущее состояние — вручную создать запись desired=installed:
```bash
# Через install API — это создаст desired=installed
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/install" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"module_name": "MODULE", "version": "VERSION"}' | python3 -m json.tool
```

**Вариант B:** Удалить лишний модуль:
```bash
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/remove" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"module_name": "MODULE", "force": true}' | python3 -m json.tool
```

### Сценарий 4: Аварийный rollback модуля

Агент хранит текущую и предыдущую версии (current+prev). Для rollback:

```bash
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/activate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"module_name": "MODULE", "version": "PREV_VERSION"}' | python3 -m json.tool
```

После rollback обновите desired state:
```bash
curl -s -X POST "http://SERVER:PORT/api/devices/DEVICE_ID/modules/install" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"module_name": "MODULE", "version": "PREV_VERSION"}' | python3 -m json.tool
```

---

## Периодический мониторинг drift

```sql
-- Устройства с drift (desired != actual)
SELECT 
    ddm.device_id,
    ddm.module_name,
    ddm.desired_version,
    ddm.state as desired_state,
    dm.version as actual_version,
    dm.state as actual_state,
    dm.last_seen_at
FROM device_desired_modules ddm
LEFT JOIN device_modules dm ON (
    dm.device_id = ddm.device_id 
    AND dm.module_name = ddm.module_name 
    AND dm.active = true
)
WHERE 
    (ddm.state = 'installed' AND (dm.id IS NULL OR dm.version != ddm.desired_version))
    OR
    (ddm.state = 'absent' AND dm.id IS NOT NULL)
ORDER BY ddm.device_id, ddm.module_name;
```

---

## Когда reconcile НЕ запускается автоматически

1. Модуль отсутствует в реестре сервера (`modules` таблица) → reconcile пропускает его с `skipped`.
2. ОС устройства несовместима с платформами модуля → `skipped`.
3. Устройство удалено из `devices` → `skipped`.

В этих случаях необходима ручная диагностика.

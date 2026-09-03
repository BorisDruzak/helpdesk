# Module Creation Guide

Полный практический гайд по созданию модулей и atomic tool'ов в текущей модульной системе `pc_client`.

Этот документ нужен для двух аудиторий:

- человеку, который руками проектирует и публикует модуль;
- нейросети или внешнему API-клиенту, который генерирует payload для module workbench / save / validate.

Документ описывает не только "как заполнить поля", но и "зачем именно так устроена система".

## 1. С чего начать

Сначала прочитайте канон:

- `server/docs/MODULE_AUTHORING_RULES.md`
- `server/docs/REGISTRY_PUBLICATION_RULES.md`
- `server/docs/RUNTIME_EXECUTION_CONTRACT.md`
- `server/docs/MODULES_API.md`

Этот guide не заменяет канон, а раскладывает его в пошаговый рабочий процесс.

## 2. Базовая модель

### 2.1 Что такое module

`module` — это не "большой скрипт". Это:

- pack доставки;
- единица versioning;
- единица ownership;
- capability bundle;
- контейнер для одного или нескольких atomic tool'ов.

Примеры module families:

- `network_basic`
- `browser_checks`
- `vendor_acme_support`

### 2.2 Что такое tool

`tool` — это атомарное типизированное действие.

Примеры:

- `dns.resolve`
- `network.ping`
- `tcp.connect`
- `http.request`
- `system.service_status`

Правильный tool:

- делает одно логическое действие;
- имеет строгий input/output contract;
- возвращает структурированный результат;
- по возможности идемпотентен для diagnostics.

### 2.3 Что такое canonical tool id

Canonical tool id всегда semantic-only.

Правильно:

- `dns.resolve`
- `network.ping`
- `screen.collect`

Неправильно:

- `network_basic.resolve_dns`
- `toolpack1.httpcheck`

Причина проста: canonical id должен обозначать capability, а не место хранения.

### 2.4 Что такое alias

Alias — это compatibility bridge.

Он нужен для:

- старых UI;
- legacy playbook;
- migration path.

Alias не должен быть source of truth для:

- аналитики;
- classification;
- no-code редактора;
- runtime policy;
- playbook design.

## 3. Когда создавать новый модуль, а когда новый tool

Создавайте новый tool, если:

- появляется новое атомарное действие;
- текущий tool становится слишком широким;
- нужно отдельно типизировать вход/выход;
- нужно отдельно строить policy или decision logic.

Создавайте новый module family, если:

- появляется новый capability bundle;
- нужны свои versioning / ownership / rollout;
- группа tool'ов логически живёт вместе и обычно доставляется пакетом.

Не создавайте tool вида:

- `network.diagnose_everything`
- `browser.fix_and_collect`
- `system.magic_repair`

Не создавайте module ради одного огромного "комбайна", если систему можно выразить несколькими atomic tool'ами.

## 4. Domain vocabulary

### 4.1 Core сущности

- `module` = доставка и версия
- `tool` = контракт и исполнение
- `preferred version` = версия module family, которую сервер считает целевой
- `rollout policy` = правило, как preferred version распространяется на устройства
- `desired state` = что должно быть на устройстве
- `actual state` = что реально установлено на устройстве

### 4.2 Tool kinds

- `diagnostic`
- `remediation`

Для `diagnostic` normal default:

- `idempotent=true`
- `side_effects=false`
- `risk_level=safe_read` или `sensitive_read`

Для `remediation` нормальны:

- `side_effects=true`
- более жёсткая policy
- consent / elevated execution

### 4.3 Lifecycle

- `experimental`
- `stable`
- `deprecated`
- `removed`

## 5. Reserved namespaces

Сразу проверяйте namespace.

Reserved core namespaces:

- `dns.*`
- `network.*`
- `tcp.*`
- `http.*`
- `tls.*`
- `system.*`
- `service.*`
- `file.*`
- `process.*`
- `browser.*`

Их можно публиковать только при `owner_scope=core|platform|builtin`.

Vendor/public модули должны использовать свой namespace:

- `myorg.*`
- `vendor_x.*`
- `acme.*`

Если capability не является частью core-пространства, не занимайте reserved namespace.

## 6. Из чего состоит модуль

У модуля есть два уровня описания:

1. module-level contract
2. tool-level contract

### 6.1 Module-level fields

Минимально важные поля:

- `module_name`
- `version`
- `module_api_version`
- `owner_scope`
- `description`
- `platforms`
- `requirements`
- `optional_requirements`
- `min_agent_version`
- `entrypoint`
- `tools`

### 6.2 Tool-level fields

Каждый tool обязан иметь:

- `tool_name` / canonical id
- `method_name`
- `description`
- `contract_version`
- `params_schema`
- `output_schema`
- `metadata`
- `dependencies`
- `lifecycle`
- `error_codes`
- `artifact_types`
- `redaction`
- `resources`
- `user_function_body`

## 7. Пошаговый процесс для человека

Ниже — основной человеческий workflow через admin UI.

### Шаг 1. Определите capability

Сначала сформулируйте capability одним коротким предложением.

Плохо:

- "модуль для всего сетевого"

Хорошо:

- "набор диагностических tool'ов для DNS, ping и TCP connectivity"

### Шаг 2. Решите, какой будет module family

Пример:

- family: `network_basic`
- версия: `1.0.0`

Спросите себя:

- какие tool'ы действительно идут вместе;
- нужна ли у них общая поставка;
- должны ли они обновляться одним пакетом.

### Шаг 3. Решите namespace и ownership

Примеры:

- `dns.resolve` при `owner_scope=core`
- `acme.support.echo` при `owner_scope=vendor`

Если вы не core/platform-owner, не используйте reserved namespace.

### Шаг 4. Откройте React workbench

Основной UI:

- `http://example.test:8666/app/admin/modules`
- React-панель `webapp/src/features/modules/modules-panel.tsx`

Backend:

- `GET /api/modules/workbench`
- `GET /api/modules/workbench/{module_name}/{version}`
- `POST /api/modules/workbench/validate`
- `POST /api/modules/workbench/save`
- `POST /api/modules/upload`

Внутри страницы `Модули` теперь есть четыре подтемы:

- `Разработка модулей` — основной human-friendly wizard для создания нового модуля
- `Список модулей` — реестр опубликованных версий, delete и import ZIP-архива
- `Редактор модулей` — advanced-режим для ручной доводки manifest/source
- `Модули на устройствах` — установка и проверка rollout на конкретных устройствах

Практическое правило:

- если модуль создаётся с нуля, начинайте с `Разработка модулей`
- если модуль уже собран внешним builder'ом или переносится из legacy-пакета, начинайте с import ZIP в `Список модулей`
- если нужен тонкий ручной контроль над manifest/source, открывайте `Редактор модулей`

### Шаг 5. Заполните blueprint модуля

Поля:

- `Имя модуля`
- `Версия`
- `Описание`
- `Owner scope`
- `Module API version`
- `Entrypoint`
- `Min agent version`
- `Platforms`
- `Requirements / optional requirements`

Рекомендации:

- `version` используйте как semver
- `module_api_version` обычно начинается с `1.0.0`
- `entrypoint` по умолчанию оставляйте `module:register`, если не меняете builder/runtime path
- `platforms` задавайте честно
- `platforms` выбирайте из UI-платформ (`any`, `linux`, `win32`, `darwin`), а не вписывайте произвольные значения
- `requirements` и `optional_requirements` удобнее и безопаснее вводить по одному значению в строке
- если вы не уверены в `min_agent_version`, лучше оставить пусто, чем публиковать ложное ограничение

Пример module blueprint:

```json
{
  "module_name": "network_basic",
  "version": "1.0.0",
  "module_api_version": "1.0.0",
  "owner_scope": "core",
  "description": "Basic diagnostic tools for DNS, ping, TCP connectivity and routing.",
  "platforms": ["any"],
  "requirements": [],
  "optional_requirements": [],
  "min_agent_version": "3.1.0",
  "entrypoint": "module:register"
}
```

### Шаг 6. Добавьте tool

В `Tool studio` создайте tool через:

- пустой diagnostic template;
- или готовый template (`dns.resolve`, `network.ping`, `tcp.connect`, `http.request`, и т.д.).

Заполните:

- `Canonical tool id`
- `Method`
- `Contract version`
- `Lifecycle`
- `Описание`
- `Aliases`
- `Error codes`
- `Params schema`
- `Output schema`
- `Metadata`
- `Dependencies`
- `Artifact types`
- `Redaction`
- `Resources`
- `Код atomic tool-фрагмента`

Практика:

- для типового diagnostic tool обычно достаточно wizard + template, без ручного JSON-редактора
- advanced editor нужен, когда вы доводите импортированный архив, правите сложные schema или сознательно выходите за рамки обычного wizard-пути

### Шаг 7. Сначала соберите schema через blueprint, потом при необходимости редактируйте JSON

`params_schema` и `output_schema` обязательны.

Нормальный путь в текущем UI — не печатать schema с нуля как raw JSON, а сначала собрать её строками:

```text
hostname:string! | Имя хоста для проверки
timeout_sec:integer | Таймаут запроса в секундах
use_tcp:boolean | Принудительно использовать TCP
```

Правила blueprint-строки:

- формат: `name:type! | Описание`
- `!` означает обязательное поле
- поддерживаются типы: `string`, `integer`, `number`, `boolean`, `object`, `array[string]`, `array[integer]`, `array[number]`, `array[boolean]`, `array[object]`
- после каждой правки UI пересобирает JSON schema и сразу показывает локальную ошибку, если строка невалидна

Raw JSON schema остаётся как fallback, но используйте его только если:

- нужна сложная вложенная структура, которую blueprint уже плохо выражает
- нужно вручную добавить `enum`, `minLength`, `pattern` и другие расширенные ограничения
- вы редактируете архив, восстановленный из существующего published package

Пример `params_schema`:

```json
{
  "type": "object",
  "properties": {
    "hostname": { "type": "string", "minLength": 1 },
    "record_type": {
      "type": "string",
      "enum": ["A", "AAAA", "CNAME", "MX", "TXT"]
    }
  },
  "required": ["hostname"],
  "additionalProperties": false
}
```

Пример `output_schema`:

```json
{
  "type": "object",
  "properties": {
    "hostname": { "type": "string" },
    "answers": {
      "type": "array",
      "items": { "type": "string" }
    },
    "resolver": { "type": "string" }
  },
  "required": ["hostname", "answers"]
}
```

### Шаг 8. Заполните metadata

Пример:

```json
{
  "domain": "network",
  "platforms": ["any"],
  "risk_level": "safe_read",
  "requires_consent": false,
  "timeout_sec": 15,
  "idempotent": true,
  "side_effects": false,
  "allow_roles": ["admin", "support"],
  "scopes": ["network", "diagnostics"],
  "origin": "managed",
  "tool_kind": "diagnostic"
}
```

Что означает:

- `risk_level` — насколько опасно выполнение;
- `requires_consent` — нужен ли отдельный пользовательский consent;
- `idempotent` — можно ли безопасно повторять;
- `side_effects` — меняет ли tool систему;
- `tool_kind` — diagnostic или remediation.

### Шаг 9. Заполните dependencies

Пример:

```json
{
  "min_agent_version": "3.1.0",
  "required_binaries": [],
  "required_python_packages": [],
  "required_services": [],
  "required_permissions": []
}
```

Dependencies нужны, чтобы:

- сервер мог оценить compatibility до запуска;
- агент мог отказать предсказуемо и машиночитаемо;
- validate/smoke не публиковал формально "установимый", но фактически нерабочий module.

### Шаг 10. Опишите redaction

Пример:

```json
{
  "enabled": true,
  "redact_headers": true,
  "redact_env": true,
  "redact_fields": ["authorization", "cookie", "token", "password", "secret", "api_key"],
  "allow_raw_sensitive_data": false
}
```

Это особенно важно для:

- HTTP / proxy / browser diagnostics;
- env vars;
- headers dumps;
- cookies;
- auth tokens.

### Шаг 11. Укажите resources

Пример:

```json
{
  "max_runtime_sec": 30,
  "max_stdout_bytes": 65536,
  "max_stderr_bytes": 65536,
  "max_artifact_count": 4,
  "max_artifact_bytes": 5242880,
  "max_subprocess_count": 2,
  "allowed_filesystem_scope": [],
  "allowed_external_hosts": []
}
```

Это страховка от tool'ов, которые:

- зависают;
- распухают по output;
- кладут агент subprocess-ами;
- тащат слишком тяжёлые артефакты.

### Шаг 12. Напишите user function body

Это тело atomic tool-фрагмента.

Хороший body:

- короткий;
- делает одну вещь;
- возвращает словарь, совпадающий с `output_schema`;
- не прячет побочные эффекты;
- не делает лишнюю оркестрацию;
- не полагается на неописанные зависимости.

Плохой body:

- тащит несколько несвязанных шагов;
- пишет в систему, хотя `side_effects=false`;
- возвращает произвольный текст вместо structured output;
- silently swallows error conditions.

### Шаг 13. Запустите validate

Кнопка:

- `Проверить`

Backend:

- `POST /api/modules/workbench/validate`

Что делает validate:

- собирает пакет в памяти;
- нормализует manifest;
- валидирует contract;
- проверяет ownership conflicts;
- делает preflight;
- делает smoke load/register/list_tools;
- возвращает preview без публикации.

До `save/publish` validate должен быть зелёным.

### Шаг 14. Сохраните модуль

Кнопка:

- `Сохранить модуль`

Backend:

- `POST /api/modules/workbench/save`

`save`:

- снова валидирует;
- собирает ZIP;
- пишет в registry;
- может назначить preferred version;
- может инициировать rollout по текущей policy.

### Шаг 15. Назначьте preferred version

Если модуль готов к использованию, у family должна быть preferred version.

Это важно, потому что:

- `run_tool` ориентируется на preferred version;
- auto-install / auto-update ориентируются на preferred version;
- UI показывает preferred version как server source of truth.

### Шаг 16. Проверьте install/rollout

После публикации проверьте:

- module виден в списке families;
- нужная версия отмечена как preferred;
- install на устройство работает;
- `run_tool` идёт через эту версию;
- если rollout mode = `installed_devices`, уже установленные устройства получают новый desired version и reconcile.

### Шаг 17. Практические сценарии, проверенные на живом агенте

Ниже два сценария, которые уже были прогнаны через UI и реальный локальный агент.

#### 17.1 `disk_space_audit` — модуль через wizard UI

Когда подходит:

- нужна быстрая безопасная диагностика локальных ресурсов
- не нужен внешний builder и не нужен ZIP-import

Почему этот сценарий хороший:

- `platforms=["any"]`, потому что `psutil.disk_partitions()` и `psutil.disk_usage()` работают кроссплатформенно
- зависимость оформлена честно через `requirements: psutil`
- output остаётся структурированным: список дисков, байты, проценты, warnings
- tool не падает целиком из-за одного недоступного mount point, а возвращает частичный результат и предупреждения

Оптимизация:

- не делайте hard fail на первом `PermissionError`
- dedupe разделы по `(device, mountpoint)`, иначе на некоторых системах будут дубли
- сортируйте результат по `mountpoint`, чтобы UI и diff были стабильными

#### 17.2 `internet_speed_probe` — модуль через ZIP-import

Когда подходит:

- модуль уже собран локально builder'ом
- код удобнее редактировать как обычный Python source и потом импортировать ZIP
- нужно перенести существующий или legacy-пакет в registry, а потом открыть его в editor

Почему этот сценарий хороший:

- import идёт через `Список модулей -> ZIP архив`
- имя и версия могут быть подсказаны из файла вроде `internet_speed_probe-1.0.0.zip`
- после upload сервер делает preflight/smoke и только потом сохраняет версию
- модуль сразу можно открыть в editor и увидеть reconstructed manifest/source

Оптимизация:

- не тяните тяжёлые speedtest-клиенты без крайней необходимости
- ограничивайте размер download/upload payload и `timeout_sec`, чтобы tool был быстрым и предсказуемым
- лучше вернуть частичные метрики (`latency_ms`, `download_mbps`, `upload_mbps`, `warnings`), чем падать на первой недоступной test-точке
- явно декларируйте внешние хосты и Python dependencies, если модуль выходит в интернет

## 8. Пошаговый процесс для LLM или API-клиента

Ниже — тот же workflow, но в machine-friendly виде.

### Шаг 1. Определите intent

LLM должна сначала ответить на вопросы:

1. Что делает capability?
2. Это diagnostic или remediation?
3. Нужен новый module family или достаточно нового tool в существующем family?
4. Какой canonical id?
5. Какой owner_scope допустим?
6. Какой input/output contract?

### Шаг 2. Выберите namespace

Правило:

- если capability core-domain и ownership central — reserved namespace допустим;
- иначе используйте vendor namespace.

### Шаг 3. Сгенерируйте structured payload

LLM не должна генерировать "архив как чёрный ящик".

LLM должна генерировать:

- module blueprint;
- список tools;
- schemas;
- metadata;
- dependencies;
- redaction;
- resources;
- `user_function_body` для каждого tool.

### Шаг 4. Отправьте validate

Первый вызов всегда:

- `POST /api/modules/workbench/validate`

LLM должна разобрать ответ:

- локальные ошибки;
- server-side validation errors;
- ownership conflicts;
- preflight warnings;
- publish readiness.

### Шаг 5. Исправьте payload

LLM должна исправлять payload итеративно до состояния:

- `publish_ready=true`
- нет conflicts
- нет schema ошибок

### Шаг 6. Только потом save

После успешного validate:

- `POST /api/modules/workbench/save`

### Шаг 7. При необходимости назначьте preferred version

Если сохраняем новую боевую версию:

- либо передайте `set_preferred=true` при `save`;
- либо вызовите `PATCH /api/modules/{module_name}/preferred`.

## 9. Канонический payload для workbench

Ниже — форма payload, с которой должен работать и UI, и AI-клиент.

```json
{
  "module_name": "network_basic",
  "version": "1.0.0",
  "module_api_version": "1.0.0",
  "owner_scope": "core",
  "description": "Basic diagnostic tools for DNS, ping, TCP connectivity and routing.",
  "platforms": ["any"],
  "requirements": [],
  "optional_requirements": [],
  "min_agent_version": "3.1.0",
  "entrypoint": "module:register",
  "tools": [
    {
      "tool_name": "dns.resolve",
      "aliases": ["network_basic.resolve_dns"],
      "method_name": "resolve_dns",
      "description": "Resolve DNS records for a hostname.",
      "params_schema": {
        "type": "object",
        "properties": {
          "hostname": { "type": "string" },
          "record_type": { "type": "string", "enum": ["A", "AAAA", "CNAME"] }
        },
        "required": ["hostname"],
        "additionalProperties": false
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "hostname": { "type": "string" },
          "answers": { "type": "array", "items": { "type": "string" } },
          "resolver": { "type": "string" }
        },
        "required": ["hostname", "answers"]
      },
      "presets": [],
      "capabilities": [],
      "metadata": {
        "domain": "network",
        "platforms": ["any"],
        "risk_level": "safe_read",
        "requires_consent": false,
        "timeout_sec": 15,
        "idempotent": true,
        "side_effects": false,
        "allow_roles": ["admin", "support"],
        "scopes": ["network", "diagnostics"],
        "origin": "managed",
        "tool_kind": "diagnostic"
      },
      "contract_version": "1.0.0",
      "dependencies": {
        "min_agent_version": "3.1.0",
        "required_binaries": [],
        "required_python_packages": [],
        "required_services": [],
        "required_permissions": []
      },
      "lifecycle": "stable",
      "error_codes": ["VALIDATION_ERROR", "DNS_NXDOMAIN", "TIMEOUT"],
      "artifact_types": [],
      "redaction": {
        "enabled": true,
        "redact_headers": true,
        "redact_env": true,
        "redact_fields": ["authorization", "cookie", "token", "password", "secret", "api_key"],
        "allow_raw_sensitive_data": false
      },
      "resources": {
        "max_runtime_sec": 15,
        "max_stdout_bytes": 65536,
        "max_stderr_bytes": 65536,
        "max_artifact_count": 0,
        "max_artifact_bytes": 0,
        "max_subprocess_count": 1,
        "allowed_filesystem_scope": [],
        "allowed_external_hosts": []
      },
      "user_function_body": "hostname = str(kwargs.get('hostname') or '').strip()\nif not hostname:\n    raise ValueError('hostname is required')\nreturn {'hostname': hostname, 'answers': [], 'resolver': ''}"
    }
  ]
}
```

## 10. Что должен вернуть tool

Runtime contract каноничен и единый.

В transport-compatible ответе structured result живёт в `data.result` и имеет envelope:

```json
{
  "status": "ok",
  "output": {
    "hostname": "example.com",
    "answers": ["93.184.216.34"],
    "resolver": "8.8.8.8"
  },
  "error": null,
  "artifacts": [],
  "metrics": {
    "duration_ms": 54,
    "attempt": 1,
    "request_id": "..."
  },
  "changed": false,
  "confidence": 1.0
}
```

Правило:

- `stdout/stderr` не API;
- `output` должен соответствовать `output_schema`;
- `error.code` должен быть стабильным и машиночитаемым;
- `artifacts` должны идти через общий artifact pipeline.

## 11. Артефакты

Если tool возвращает не только структурированный output, но и артефакты, описывайте их явно.

Хорошие kinds:

- `screenshot`
- `headers_dump`
- `log_excerpt`
- `pcap_summary`
- `cert_chain`

У артефакта важны:

- `kind`
- `mime`
- `sensitivity`
- `retention_policy`

Не пихайте большие дампы внутрь `output`.

## 12. Декомпозиция архива обратно в код

Да, система умеет раскладывать опубликованный архив обратно в структуру модуля.

Workbench detail / validate preview показывают:

- extracted text files из архива;
- `manifest.json`;
- `module.py`;
- найденные `@exposed_tool` функции;
- reconstruction strategy:
  - `markers`
  - `ast`
  - `raw`

Это полезно для:

- редактирования существующих модулей;
- миграции legacy archive в новый contract;
- AI-assisted refactoring;
- ручного аудита того, что реально опубликовано.

Ограничение:

- если в архиве нет читаемого Python source, полного восстановления structured code body может не быть.

## 13. Частые ошибки

### Ошибка 1. Canonical id связан с module name

Плохо:

- `network_basic.resolve_dns`

Хорошо:

- `dns.resolve`

### Ошибка 2. Tool слишком широкий

Плохо:

- один tool и DNS проверяет, и HTTP ходит, и proxy чинит

Хорошо:

- разбить на `dns.resolve`, `network.ping`, `http.request`, `browser.check_proxy`

### Ошибка 3. Нет строгой schema

Плохо:

- `params_schema={}`
- `output_schema={}`
- всё поведение только в prose

Хорошо:

- обязательные поля и enums заданы явно

### Ошибка 4. Побочные действия не задекларированы

Плохо:

- tool меняет систему, но `side_effects=false`

Хорошо:

- remediation явно помечена

### Ошибка 5. Нет error taxonomy

Плохо:

- `{"error": "something went wrong"}`

Хорошо:

- `{"code": "DNS_NXDOMAIN", "message": "...", "retryable": false, "category": "network.dns"}`

### Ошибка 6. Секреты утекли в output или artifact

Всегда:

- проектируйте `redaction`;
- не возвращайте raw tokens / cookies / auth headers по умолчанию.

## 14. Recommended authoring checklist

Перед публикацией проверьте:

- canonical id semantic-only
- namespace допустим
- один tool = одна ответственность
- `params_schema` и `output_schema` заданы
- `contract_version` заполнен
- `metadata` полный
- `dependencies` честные
- `redaction` описан
- `resources` описаны
- `error_codes` заданы
- `tool_kind` корректный
- validate зелёный
- ownership conflicts отсутствуют
- smoke load/register/list_tools проходит

## 15. Recommended release checklist

Перед назначением preferred version:

- validate прошёл
- save прошёл
- module виден в registry
- tool виден в catalog
- install на тестовое устройство проходит
- `run_tool` возвращает канонический envelope
- output соответствует schema
- artifacts, если есть, корректно оформлены

## 16. Recommended prompt for LLM

Если модуль пишет LLM, хороший prompt должен требовать:

1. сначала определить module family и tool list;
2. выбрать canonical ids;
3. предложить `params_schema` и `output_schema`;
4. описать metadata/dependencies/redaction/resources;
5. сгенерировать `user_function_body`;
6. выдать JSON payload для `POST /api/modules/workbench/validate`;
7. не публиковать до успешного validate.

Пример:

```text
Create a managed diagnostic module family for DNS and TCP checks.
Use semantic canonical ids only.
Do not use reserved namespaces unless owner_scope allows it.
Return:
1. module blueprint,
2. tools array,
3. full JSON payload for POST /api/modules/workbench/validate,
4. short rationale for each tool.
All tools must be typed, idempotent, side_effect free, and use explicit error codes.
```

## 18. Recommended prompt for editing an existing module

```text
Open module family X version Y.
Keep canonical ids stable unless there is a contract-level reason to change them.
Preserve aliases only for compatibility.
Return:
1. proposed changes,
2. changed payload,
3. migration risks,
4. whether contract_version or module version must be bumped.
```

## 19. FAQ

### Можно ли редактировать модуль прямо в UI

Да. Для этого и существует module workbench:

- module blueprint;
- tool studio;
- template-driven authoring;
- validate-before-publish;
- archive decomposition обратно в код.

### Можно ли редактировать уже опубликованный архив

Да, если из архива можно восстановить manifest/source fragments.

### Нужно ли всегда делать ZIP руками

Нет. Нормальный путь — structured payload -> validate -> save, а сервер сам собирает пакет.

ZIP-import нужен для другого сценария:

- модуль уже собран builder'ом
- модуль приходит извне как готовый пакет
- нужно быстро занести архив в registry и потом открыть его в editor

То есть `save` — путь для authoring from scratch, а `upload` — путь для готового архива.

### Когда лучше wizard, а когда ZIP-import

Используйте wizard, если:

- модуль создаётся впервые
- у вас 1-3 tool'а и типовой diagnostic/remediation контракт
- хочется меньше raw JSON и больше встроенной валидации

Используйте ZIP-import, если:

- у вас уже есть готовый `manifest.json` и `module.py`
- модуль собирается отдельным скриптом или внешним генератором
- нужно перенести или проверить уже собранный пакет

### Нужно ли человеку знать весь runtime internals

Нет. Но нужно понимать:

- module = delivery/versioning;
- tool = contract/action;
- preferred version = server truth;
- validate/save/upload/install/run_tool = обязательная цепочка.

## 20. Где смотреть код

Ключевые entrypoints:

- `server/modules/handlers.py`
- `server/modules/workbench_service.py`
- `server/utils/module_builder.py`
- `server/utils/module_manifest.py`
- `server/tools/service.py`
- `shared/tool_contracts.py`
- `pc_agent/core/registry.py`
- `pc_agent/core/orchestrator.py`
- `pc_agent/docs/MODULES.md`

## 21. Самое важное в одном блоке

Запомнить нужно пять вещей:

1. canonical tool id всегда semantic-only;
2. module и tool — разные сущности;
3. tool обязан быть typed и атомарным;
4. validate обязателен до save/publish;
5. preferred version на сервере — источник истины для auto-install и rollout.

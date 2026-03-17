# Анализ: атомарные модули агента, костяк, веб-форма, импорты

**Дата:** 2026-03-03

Документ описывает результаты анализа создания атомарных модулей для агента: универсальный костяк, идея веб-формы «только код функции», оптимизация процесса и ограничения по импортам/зависимостям.

---

## 1. Что сделано

- Создан **атомарный модуль `ip_address`**: узнаёт IP-адрес машины (только stdlib `socket`).
- Модуль упакован в ZIP, загружен на сервер, установлен на агента, вызван `ip_address.get_ip` — результат `{"ip": "192.168.100.17", "ok": true}`.
- Цепочка проверена: сборка → upload (preflight + smoke) → install на устройство → run_tool.

**Расположение модуля:** `pc_agent/modules_packages/ip_address/` (manifest.json, module.py).

---

## 2. Универсальный костяк модуля (пакет для install_module_package)

Любой модуль-пакет, который агент загружает из `modules_store` (ZIP с сервера), должен содержать **обязательную основу**:

### 2.1 Структура каталога

```
<module_name>/
├── manifest.json   # обязателен
└── module.py       # обязателен
```

### 2.2 manifest.json — обязательные поля

- **module_name** — уникальное имя модуля (совпадает с каталогом).
- **module_version** — версия в формате X.Y.Z.
- **entrypoint** — точка входа, по умолчанию `"module:register"`.

Опционально: `description`, `requirements`, `optional_requirements`, `notes`.

### 2.3 module.py — обязательный минимум

1. **Импорты от агента** (при загрузке из `modules_store` путь к пакету добавляется в `sys.path`, поэтому импорты как у встроенных модулей):

   ```python
   from modules.base_module import BaseCollector
   from core.registry import exposed_tool   # если нужны tools
   ```

2. **Класс-коллектор** — наследник `BaseCollector`:
   - `@property name(self) -> str` — имя модуля (обычно то же, что `module_name`).
   - `async def collect(self) -> Dict[str, Any]` — минимальная реализация (может возвращать `{}`).

3. **Функция `register()`** — вызывается по entrypoint `module:register`:
   - возвращает **один экземпляр** класса-коллектора (или обёртки над функцией).

4. **Инструменты (опционально)** — методы класса, помеченные `@exposed_tool(...)`; имя в API будет `<module_name>.<tool_name>` (например, `ip_address.get_ip`).

**Минимальный костяк (без инструментов):**

```python
from typing import Dict, Any
from modules.base_module import BaseCollector

class MyCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "my_module"

    async def collect(self) -> Dict[str, Any]:
        return {}

def register():
    return MyCollector()
```

**С одним инструментом (как ip_address):**

```python
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class MyCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "my_module"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(
        name="do_something",
        description="Описание",
        risk_level="safe_readonly",
    )
    async def do_something(self) -> Dict[str, Any]:
        return {"ok": True}

def register():
    return MyCollector()
```

Без этого костяка загрузчик агента (`load_module_from_path` + entrypoint) не сможет получить экземпляр `BaseCollector` и зарегистрировать модуль.

---

## 3. Веб-страница создания модулей: «только код атомарной функции»

### 3.1 Идея

Пользователь вводит **только тело одной функции** (например, «узнать IP»), без импортов агента, без класса и без `register()`. Сервер или отдельный сервис:

1. Валидирует код (безопасность, синтаксис).
2. Подставляет его в **шаблон костяка** (имя модуля, имя инструмента, описание берутся из формы).
3. Собирает `manifest.json` + `module.py`.
4. Запускает preflight (smoke_check_module) в sandbox.
5. Только при успехе — сохраняет ZIP и/или отправляет команду установки на агента.

Так процесс становится проще и с понятными ошибками (валидация → шаблон → smoke → только потом «модуль принят»).

### 3.2 Как сделать подстановку кода в шаблон

- **Шаблон** — строка с плейсхолдером, например `{{USER_FUNCTION_BODY}}` или `{{ATOMIC_CODE}}`.
- Пользовательский код должен:
  - быть телом **async-функции**, возвращающей `Dict[str, Any]`;
  - не содержать объявления самой функции (только тело), либо объявление одной async-функции с фиксированным именем, например `async def run(...) -> Dict[str, Any]:`.
- Сервер генерирует полный `module.py`:
  - либо подставляет тело в метод инструмента класса-коллектора;
  - либо оборачивает в function-based модуль (одна `async def run()`), тогда загрузчик агента использует `FunctionWrapper` (для пакетов это возможно, если в пакете есть функция `run` и entrypoint вызывает её или loader распознаёт тип).

Ограничение: сейчас **пакетный** путь (ZIP с manifest + module.py) всегда ожидает **класс** и `register()`. Путь **install_module_code** поддерживает и класс, и одну функцию `run` (CodeValidator + DynamicModuleLoader). Значит:

- **Вариант A (веб → пакет):** форма генерирует полный класс + `register()` из шаблона, подставляя пользовательский код в один метод с `@exposed_tool`. Имя модуля и инструмента задаются в форме.
- **Вариант B (веб → install_module_code):** форма генерирует только код с одной `async def run()`; агент получает команду `install_module_code` с этим кодом. Тогда костяк на стороне агента уже есть (CodeValidator + FunctionWrapper). Но для install_module_code нужны права admin и включённый `allow_remote_code`; установка идёт в `dynamic_modules`, а не в modules_store.

Для «максимально простой формы» логичнее **Вариант A**: одна текстовая область «код функции», поля «имя модуля», «имя инструмента», «описание»; сервер собирает полный модуль по шаблону, прогоняет smoke и только при успехе сохраняет/раздаёт пакет.

### 3.3 Пример шаблона (серверная подстановка)

Псевдошаблон для генерации `module.py`:

```python
# Сгенерировано из веб-формы. Имя модуля: {{MODULE_NAME}}
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return "{{MODULE_NAME}}"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(
        name="{{TOOL_NAME}}",
        description="{{TOOL_DESCRIPTION}}",
        risk_level="safe_readonly",
    )
    async def _tool(self) -> Dict[str, Any]:
        # --- начало пользовательского кода ---
        {{USER_FUNCTION_BODY}}
        # --- конец пользовательского кода ---

def register():
    return _Collector()
```

Правило: `{{USER_FUNCTION_BODY}}` должен быть набором строк, образующих тело функции (return и т.д.), без `async def`. Либо форма принимает одну async-функцию и парсер вытаскивает только тело.

---

## 4. Импорты и дополнительные библиотеки

### 4.1 Текущее поведение

- **Модуль-пакет (ZIP):** при загрузке путь к распакованному каталогу модуля (например, `data/modules_store/ip_address/1.0.0`) добавляется в `sys.path`. Импорты вида `from modules.base_module import BaseCollector` и `from core.registry import exposed_tool` работают, потому что агент запускается из своего окружения, где уже есть `modules` и `core`.
- **Внешние зависимости (pip):** в коде модуля можно писать `import mss`, `import pydantic` и т.д. Они **будут работать только если** эти пакеты уже установлены в **том же окружении**, в котором запущен процесс агента (тот же интерпретатор, тот же venv). В manifest.json поле `requirements` носит информационный характер — агент **не** устанавливает их автоматически при установке модуля.
- **Скомпилированный агент (PyInstaller и т.д.):** при сборке в один исполняемый файл в него попадают только те модули, которые импортированы из основного кода агента. Динамически загружаемый модуль (из ZIP) выполняется в том же процессе, но его `import mss` будет искать `mss` в sys.path. В собранном приложении sys.path обычно содержит только пути из бандла; сторонних пакетов там нет. Поэтому **без доработок** модули с произвольными `pip`-зависимостями в скомпилированном агенте **не будут работать**.

### 4.2 Как сделать, чтобы дополнительные библиотеки работали

1. **Не собирать агент в один бинарник** — запускать как `python -m pc_agent` или через venv; тогда пользователь ставит зависимости в этот venv (вручную или по списку из manifest).
2. **Явно включать популярные зависимости в сборку** — в spec PyInstaller добавить hiddenimports для тех пакетов, которые разрешены для модулей (например, `mss`, `pydantic`). Минус: раздувание бинарника и фиксированный набор.
3. **Отдельный процесс/sandbox для модулей** — загрузка и выполнение кода модуля в дочернем процессе с своим venv, где установлены зависимости из manifest; общение с агентом через RPC/очередь. Большая доработка архитектуры.
4. **При установке модуля на агенте проверять requirements и выводить предупреждение** или отказывать, если пакет не установлен в окружении агента — чтобы ошибка была явной («установите mss в окружении агента»).

Для веб-формы «только код функции» разумно **ограничить допустимые импорты** (например, только stdlib + белый список), тогда вопрос дополнительных библиотек снимается для «простых» атомарных модулей. Либо явно документировать: «модули с внешними зависимостями работают только в окружении, где эти пакеты установлены».

---

## 5. Оптимизация и упрощение процесса

- **Атомарный модуль без лишнего:** как в ip_address — один инструмент, минимум полей в manifest, без зависимостей при возможности (stdlib).

---

## 6. Ссылки

- Модули агента: `pc_agent/docs/MODULES.md`
- API модулей сервера: `server/docs/MODULES_API.md`
- Валидатор кода (class/function): `pc_agent/core/validator.py`
- Загрузчик (пакет из пути): `pc_agent/core/loader.py` — `load_module_from_path`
- Smoke-check при upload: `pc_agent/scripts/smoke_check_module.py`, `server/modules/handlers.py` (upload)
- Пример атомарного модуля: `pc_agent/modules_packages/ip_address/`

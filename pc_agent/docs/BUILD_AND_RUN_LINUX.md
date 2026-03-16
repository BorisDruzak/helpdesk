# Сборка и запуск агента на Linux (launcher + обновления)

Агент собирается через PyInstaller: **launcher** (один исполняемый файл) и **agent** (onedir). Launcher запускает текущую версию из `install_root/versions/<ver>/`, при выходе с кодом 42 или наличии `pending_update.json` применяет обновление (см. [SELF_UPDATE.md](SELF_UPDATE.md)).

## Сборка (из корня репозитория)

Требуется Python 3.12 и PyInstaller в venv агента:

```bash
cd /var/chat_bot/pc_client
./pc_agent/venv/bin/pip install pyinstaller   # если ещё не установлен
./pc_agent/venv/bin/pyinstaller pc_agent/pyinstaller_launcher_linux.spec --noconfirm
./pc_agent/venv/bin/pyinstaller pc_agent/pyinstaller_agent_linux.spec --noconfirm
```

Результат:
- `dist/launcher` — бинарник launcher
- `dist/pc_agent/` — onedir (исполняемый `pc_agent` и каталог `_internal`)

## Layout установки (install_root + data_root)

По умолчанию:
- **install_root:** `~/.local/opt/pcclient-agent` (или `PC_AGENT_INSTALL_ROOT`)
- **data_root:** `~/.local/share/pcclient-agent` (или `PC_AGENT_DATA_DIR`)

Структура install_root:
- `launcher` — исполняемый файл
- `current.json` — `{"version":"3.0.0","previous":null}`
- `versions/3.0.0/` — содержимое `dist/pc_agent/` (исполняемый `pc_agent` и `_internal/`)

Пример разложения (для теста в `.run`):

```bash
INSTALL=".run/agent_install"
DATA=".run/agent_data"
mkdir -p "$INSTALL/versions/3.0.0"
cp dist/launcher "$INSTALL/launcher" && chmod +x "$INSTALL/launcher"
cp -r dist/pc_agent/* "$INSTALL/versions/3.0.0/"
echo '{"version":"3.0.0","previous":null}' > "$INSTALL/current.json"
```

## Подготовка data_root и токен

1. Создать identity с UUID устройства:
   ```bash
   mkdir -p "$DATA"
   echo '{"uuid":"<UUID>"}' > "$DATA/identity.json"
   ```
   UUID можно сгенерировать: `python3 -c "import uuid; print(uuid.uuid4())"`

2. Сервер должен быть запущен. Запросить токен:
   ```bash
   curl -s -X POST http://127.0.0.1:8666/api/login \
     -H "Content-Type: application/json" \
     -d '{"uuid":"<UUID>"}'
   ```
   В ответе: `"token": "..."`.

3. Один раз запустить агент с переменной `AUTH_TOKEN`, чтобы токен сохранился в БД агента (`storage.db`):
   ```bash
   PC_AGENT_DATA_DIR="$DATA" PC_AGENT_INSTALL_ROOT="$INSTALL" \
   PC_AGENT_WS_URL=ws://127.0.0.1:8666/ws PC_AGENT_API_URL=http://127.0.0.1:8666/api \
   AUTH_TOKEN="<полученный_токен>" \
   "$INSTALL/versions/3.0.0/pc_agent"
   ```
   После сообщения «Токен из ENV сохранен в БД агента» и handshake можно остановить (Ctrl+C). Дальше launcher будет брать токен из БД.

## Запуск через launcher

```bash
PC_AGENT_DATA_DIR="$DATA" PC_AGENT_INSTALL_ROOT="$INSTALL" \
PC_AGENT_WS_URL=ws://127.0.0.1:8666/ws PC_AGENT_API_URL=http://127.0.0.1:8666/api \
"$INSTALL/launcher" --data-dir "$DATA" --install-root "$INSTALL"
```

Launcher читает `current.json`, запускает `versions/<version>/pc_agent` с нужными env; при выходе 42 или наличии `pending_update.json` выполняет установку обновления и перезапуск.

## Проверка «агент онлайн»

- В логах агента: `✅ Получен handshake_ack от сервера` — подключение успешно.
- Список устройств и статус online: `GET /api/devices` (требует UI-авторизации, например токен после `POST /api/ui_login`).

## Краткая последовательность (E2E)

1. Запустить сервер: `python3 scripts/run_server.py`
2. Собрать launcher и агент (команды выше), разложить в `install_root`, создать `data_root` и `identity.json`
3. Запросить токен: `POST /api/login` с `uuid` из identity
4. Один раз запустить бинарник агента с `AUTH_TOKEN=...` для сохранения токена в БД
5. Запускать агент через launcher; проверять handshake в логах

Остановка сервера: `python3 scripts/stop_server.py`.

## Запуск «прямо из dist» (без отдельного install_root)

Если нужно запустить лаунчер из каталога `dist/` после сборки:

1. Подготовить layout в `dist/`:
   ```bash
   cd /var/chat_bot/pc_client
   mkdir -p dist/versions/3.0.0
   cp -r dist/pc_agent/* dist/versions/3.0.0/
   echo '{"version":"3.0.0","previous":null}' > dist/current.json
   mkdir -p dist/data
   ```

2. Запуск (из корня репозитория или из dist):
   ```bash
   PC_AGENT_DATA_DIR="$(pwd)/dist/data" PC_AGENT_INSTALL_ROOT="$(pwd)/dist" \
   PC_AGENT_WS_URL=ws://127.0.0.1:8666/ws PC_AGENT_API_URL=http://127.0.0.1:8666/api \
   ./dist/launcher --data-dir dist/data --install-root dist
   ```

Либо запустить бинарник агента напрямую с GUI (без лаунчера):
   ```bash
   PC_AGENT_DATA_DIR=dist/data PC_AGENT_WS_URL=ws://127.0.0.1:8666/ws PC_AGENT_API_URL=http://127.0.0.1:8666/api \
   ./dist/pc_agent/pc_agent --gui
   ```

## GUI не отображается

- **DISPLAY:** при SSH или без графической сессии проверьте `echo $DISPLAY`; при необходимости экспортируйте `DISPLAY=:0` или запускайте с локального X/Wayland.
- **Плагины Qt (xcb):** при запуске из собранного бинарника (`dist/pc_agent/pc_agent`) Qt может не найти платформенный плагин. Задайте путь к плагинам PySide6 перед запуском:
  ```bash
  export QT_PLUGIN_PATH="/var/chat_bot/pc_client/pc_agent/venv/lib64/python3/site-packages/PySide6/Qt/plugins"
  ./dist/pc_agent/pc_agent --gui
  ```
  (путь замените на свой к venv или системной установке PySide6/Qt/plugins).
- **Лаунчер и --gui:** Linux-лаунчер по умолчанию передаёт агенту `--gui`. Если окно не появляется, проверьте логи агента (в data_root или консоль при прямом запуске `pc_agent --gui`).

# Webapp Cutover Checklist

Финальный operational cutover для нового `webapp` не должен зависеть от ручной памяти. Этот документ фиксирует, по каким правилам legacy `/login`, `/admin`, `/support` вообще могут стать default entrypoints для `/app/*`, и что нужно проверить перед полным переключением.

## Правила активации

- `/login` переключается на `/app/login` только если:
  - `WEBAPP_CUTOVER_LOGIN_ENABLED=true`;
  - собранный bundle реально присутствует в `webapp/dist`.
- `/support` переключается на `/app/support` только если:
  - `WEBAPP_CUTOVER_SUPPORT_ENABLED=true`;
  - `WEBAPP_CUTOVER_LOGIN_ENABLED=true`;
  - собранный bundle реально присутствует в `webapp/dist`.
- `/admin` переключается на `/app/admin` только если:
  - `WEBAPP_CUTOVER_ADMIN_ENABLED=true`;
  - `WEBAPP_CUTOVER_LOGIN_ENABLED=true`;
  - собранный bundle реально присутствует в `webapp/dist`.
- `?legacy=1` всегда имеет приоритет над cutover и должен оставлять доступ к legacy shell.
- Если prerequisites не выполнены, сервер не делает half-switch и оставляет legacy route рабочим.
- Начиная с финального cutover `WEBAPP_CUTOVER_*` включены по умолчанию в `server/config.py`; для rollback используйте явный `WEBAPP_CUTOVER_LOGIN_ENABLED=false`, `WEBAPP_CUTOVER_SUPPORT_ENABLED=false`, `WEBAPP_CUTOVER_ADMIN_ENABLED=false` в `server/.env`.

Каноничный preflight:

```powershell
python scripts/check_webapp_cutover.py --json
```

## Локальный signoff перед выкладкой

1. Поднять frontend toolchain:

```powershell
python scripts/bootstrap_web_toolchain.py
```

2. Пересобрать bundle:

```powershell
pnpm --dir webapp run build
```

3. Прогнать релевантные локальные проверки:

```powershell
python -m pytest server/tests/test_static_pages_handlers.py -v --tb=short
python scripts/verify_workspace.py
```

4. Проверить preflight отчёт:

```powershell
python scripts/check_webapp_cutover.py --json
```

## Remote signoff после release

1. Выложить текущий commit штатным release flow.
2. Прогнать live signoff helper:

```powershell
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
```

3. Убедиться, что helper подтвердил:
  - `/app -> /app/admin`;
  - `GET /api/web/session/me`;
  - рабочие `/app/admin` и `/app/support`;
  - raw redirects `/login`, `/admin`, `/support` находятся в согласованном режиме:
    - либо ещё legacy shell до полного cutover;
    - либо уже `/app/*` после полного cutover;
  - raw escape `/login?legacy=1`, `/admin?legacy=1`, `/support?legacy=1`;
  - русский `lang/title`;
  - отсутствие `console/page errors`.
4. Поверх helper сделать browser MCP-check, если менялся UI.
5. После проверки остановить remote server, если не нужен живой стенд.

## Targeted legacy cleanup

- Пока `/ticket`, публичная очередь и публичный browser ticket не перенесены, legacy shell полностью не удаляется.
- Новые внутренние entrypoints не должны жёстко прибивать пользователя к `_shell=...`; они должны идти через логические `/admin` или `/support`, чтобы default-route switch уважал текущую cutover policy.
- Уже нормализованный пример: `server/ticket.html` теперь ведёт в `/admin`, а не в pinned legacy shell.
- Сами legacy shell-ссылки теперь должны использовать `?legacy=1`, а не version-pinned `_shell=...`, чтобы fallback оставался стабильным даже после следующего deploy.
- Удаление `server/login.js`, `server/support.js`, `server/admin.js` и связанных HTML/CSS допустимо только после стабильного remote signoff и явного решения о завершении migration window.

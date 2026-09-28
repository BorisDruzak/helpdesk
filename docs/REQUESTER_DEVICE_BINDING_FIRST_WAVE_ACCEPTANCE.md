# Requester Registration & Device Binding — отчёт проверки 29.09.2026

Запрошенные регистрация тестового пользователя, обновление локального агента и тест в браузере выполнены. Полная приёмка First Wave пока открыта: пользователь ещё не подтвердил вручную отображение и кнопки tray установленной версии 3.2.78. Успешный native IPC не заменяет эту визуальную проверку.

## Проверенный код и артефакты

| Объект | Значение |
|---|---|
| Endpoint Windows runtime SHA | `0f5cc69fff8a603eb829189bf0ddfdccc26580aa` |
| Endpoint HTTP provider / Helpdesk pin | `61acfde9401a51fc7e3006733721ee1c2be12b4b` |
| Endpoint OpenAPI / pinned OpenAPI SHA256 | `e0161970a2f08dcc80fc333676319c2018065743d74f880da160404115b6cdec` |
| Endpoint проверенная миграция | `0036_device_binding` |
| Helpdesk implementation SHA | `ecb68704edd750e6deac3a495fb90d5a8f44465a` |
| Helpdesk проверенная миграция | `146` |
| Windows Agent | `3.2.78`, `EndpointAgent-3.2.78-x64.msi` |
| MSI SHA256 | `9d47348bfb3a61b92aa3f2e6188e36cc6da1636477525c25d0a5ae0761f755f2` |
| Runtime tree SHA256 | `79316ee4184e8138b4a5c232ea2d4eef12be92393d9f2076969775ba89dae632` |
| Staging Setup SHA256 | `015955fb2822ed3677e4567a08fb7a3843f9a373af57738d09c3bf6801a0a7a8` — unsigned, только staging |
| Helpdesk accepted release archive SHA256 | `470d44dc474e52a970da29f0cdc411c9cdd8cc2824b390b47d51d729980dbd8f` |
| Accepted webapp archive SHA256 | `10d6574c28030c5b7443cd4fac0af95a8cb60afb78ff2bdfdab1fa35971e1b33` |
| CI summary SHA256 | `f0f74502f27b51eb2b4c53e7bf3004525a0ce04d4c23e308f71f727efad1e41d` |
| Webapp content digest, совпал с выгрузкой установленного bundle | `0cf7a1d3d9042e662d98de8b61ed50add8249d51bfdf18a02a14ed74abfda4a7` |

Windows-only исправления 0f5 не меняют принятый HTTP/OpenAPI-контракт 61acfde. Эти ревизии намеренно указаны отдельно.

Draft PR: [Endpoint #37](https://github.com/BorisDruzak/endpoint_platform/pull/37), [Helpdesk #38](https://github.com/BorisDruzak/helpdesk/pull/38). Ветки `codex/requester-device-binding-first-wave` синхронизированы с remote; изменения не merged и не развёрнуты в production.

Дополнительные исправления, выявленные реальным браузером:

- `5f4379cadb84a2c2736c064e6e1815aa287db827`, `fix(diagnostics): retain safe intent keys in support launchers`: launcher передавал только params и получал 400 без создания операции. Все три вызывающих UI теперь используют существующий actor/ticket idempotency key; ошибочная попытка сохраняет намерение, принятие операции его завершает.
- `ecb68704edd750e6deac3a495fb90d5a8f44465a`, `fix(registry): expose possession source in administrator claim review`: Admin показывает источник кода, действующего/заявленного владельца и причину конфликта; замена проходит через существующее окно причины и аудит. Регрессия с уже подтверждённой заявкой проверена до и после исправления.

## Проверки

| Проверка | Фактический результат |
|---|---|
| Helpdesk full exact-SHA CI | [36473600061](https://github.com/BorisDruzak/helpdesk/actions/runs/36473600061), success; 18 обязательных слоёв |
| Helpdesk PR CI | [36473604721](https://github.com/BorisDruzak/helpdesk/actions/runs/36473604721), success, тот же SHA |
| Endpoint exact-SHA / PR CI | [36410772204](https://github.com/BorisDruzak/endpoint_platform/actions/runs/36410772204) / [36410709668](https://github.com/BorisDruzak/endpoint_platform/actions/runs/36410709668), success; 648 passed |
| `npm --prefix webapp test` | 491 passed |
| `npm --prefix webapp run build` | passed |
| Clean export, ROOT-only PYTHONPATH, `python -m pytest <export>/server/tests -m no_db -q` | 896 passed, 1 skipped |
| Scripts / migration-schema CI | 268 / 5 passed |
| PostgreSQL tickets / observer / agent-runtime / web-API CI | 372 / 90 / 29 / 303 passed |
| Browser fixtures | 31 passed; fixtures не заменяют live browser |
| Реальный pinned provider + Gateway WSS contract CI | 2 passed, без mock fallback |
| Windows focused package/runtime | 149 passed, 1 skipped; runtime 39 passed |
| Windows расширенный прогон | 568 passed, 5 failed, 1 skipped — не зелёный: 4 существующих Setup-теста обращаются к реальному SCM и получают SERVICE_NOT_RUNNING; ALT-тест использует недоступный на Windows os.fchmod |
| `python scripts/verify_workspace.py --workspace .` / `git diff --check` | passed |
| `python scripts/release_candidate_preflight.py --workspace . --commit ecb68704edd750e6deac3a495fb90d5a8f44465a --allow-local-dirty` | passed, accepted exact-SHA bundle |

Registration, challenge TTL/revoke/replay/atomic redeem/throttle/scope/redaction, Registry idempotency/conflicts, optional-device forms, отказ от произвольного person/device и requester visibility проверены целевыми тестами и PostgreSQL CI. Read-only review после исправления P2 не выявил подтверждённых блокеров. Локальные промежуточные no-DB отказы от старого ignored build и PYTHONPATH устранены чистым export; расширенные Windows отказы не скрыты.

## Реальный браузер и native agent

Локальный ADMIN-2: тестовый пользователь `binding.browser.260929.136f7d`, устройство `2ca2f974-4620-4b5f-a6c1-2615c4bc544a`. Регистрация login/password/repeat, профиль, настоящий IPC challenge, anonymous fragment → login → возврат, authenticated redeem 200, primary binding, немедленное «Мои устройства» прошли. Код и пароль не сохранены в отчёте/аргументах/файлах; fragment удалён, sessionStorage пуст.

Windows VM `192.168.101.120`, DESKTOP-9ST5HO2: Yandex Browser в интерактивной Limited session 1 с проверкой TLS. Пользователь `binding.vm.260929.d8f53d`, устройство `09b55626-30fa-4a21-8b41-41024a3a85d5`. Та же полная цепочка прошла в браузере самой VM. Page errors: 0. Результат: `temp/device-binding-vm-native-browser-result.json`, снимок: `temp/device-binding-vm-native-browser.png`.

Конфликтные отдельные пользователи проверены на обоих компьютерах. На VM `binding.vmconflict.260929.a30aaa` получил pending_admin_review, «Мои устройства» остались пустыми, прямое чтение чужого устройства вернуло 404. Исходный владелец сохранился. Admin показывает разные действующего и заявленного владельцев, источник «Код привязки Endpoint», конфликт и требование отдельного решения с причиной. Окно причины открыто и отменено; передача владельца не подтверждалась.

| Обращение | Сценарий и результат |
|---|---|
| T-000035 | Обычное обращение без устройства, переписка/статусы/решение/подтверждённое закрытие/оценка 5 |
| T-000036 | Локальный primary device; queue/SLA/assigned/in_progress, support chat, waiting_on_user, requester reply, resume, bounded diagnostic, resolved, requester closed, разрешённый reopen, повторное решение/закрытие, оценка 5 |
| T-000037 | Явное «Без компьютера» при существующем primary: create 200, request_device_scope=none, оба device/ref NULL подтверждены БД, support tools пусты |
| T-000038 | Primary Windows VM: обычная форма, queue/SLA/assigned/in_progress, support message, diagnostic succeeded, waiting_on_user, requester reply, resume, resolved, requester close 200; БД status=closed, device_id и endpoint_device_ref равны UUID VM |

Локальная операция `f1c3458e-8541-5691-b092-517ff58553be`: POST 202 с idempotency_key, затем succeeded; свежая native completion `df4c96ab-68bd-45cd-8c37-aea05302790d`, context.diagnostic.collect, succeeded.

VM операция `9869bc6a-af7b-563c-ab45-e1245d68e2ec`: support workspace показывает succeeded. На VM свежая completion `cf6b4d9f-231c-4089-ba36-bc3b223a62a6`, context.diagnostic.collect, succeeded, `2026-09-28T20:28:44.345987+00:00`. Корреляция по VM/capability/time window; это не утверждение о выполненном прямом DB join operation↔command. Старый маркер 27.09 не использовался как доказательство.

Действующая policy для этой ограниченной диагностики показывает низкий риск и «Согласие не требуется». Существующие consent/authorization guards не ослаблялись; запуск был явным действием поддержки.

## Восстановление после теста

- **Локальный ADMIN-2:** по запросу пользователя оставлен пакет 3.2.78/source0f5. Исходные protected enrollment, CA, policy, storage/security DB, completions и canary status восстановлены и сравнены с защищённой копией без вывода содержимого. Временный origin удалён; Agent/Updater Stopped/Stopped — исходное состояние.
- **Windows VM:** пакет 3.2.78 удалён штатным MSI, исходный 3.2.75/source `bcb7d88b73eb60e411883a9dd5519c618b48f78e` установлен канонической canary-процедурой. Baseline MSI SHA256 `cb7fc440961e77f8600445f4ec0228fddf11ae6e55a3fdf61e1b6fd6266a1312`. Исходные credential/identity/CA восстановлены и сравнены без вывода; original origin был отсутствующим и снова отсутствует. Временная scheduled task и отдельные browser runtime tools удалены. Agent/Updater Stopped/Stopped; первоначально Agent был Running, но после validation оставлен остановленным по operating contract. Пакеты, защищённые резервные копии и диагностическая история сохранены.
- **Linux staging:** перед восстановлением сохранены дополнительные protected acceptance-final dumps. Исходные dumps из `/var/backups/device-binding-first-wave-20260928` проверены и восстановлены только в staging DB; оригинальные env равны backup, scoped acceptance secret удалён. Исходные релизы Endpoint `abdd5c7ef596` и Helpdesk `bd3090bd72633a83be5e5f83a894ac959306cf74`, схемы `0035_policy_sensor_health` / `145`. Все три службы inactive/dead. Тестовые новые пользователи и T-000036/37/38 отсутствуют после restore. Отчёт операции `temp/device-binding-staging-restore.log`, exit 0.

Исходные dump SHA256: Endpoint `373eddcaf48f73e7fb3daae686f1677b18905fc278d33f1cfff6e993a6388f0d`, Helpdesk `715338969625b83fdd70d1009a53370b3d3842c12ef23a860b4d30c7e36befb2`. Резервные копии сохранены для восстановления; секреты не выгружались в workspace.

## Ограничения и остаточный gate

Ручная визуальная проверка tray 3.2.78 — display/copy/refresh/open — ещё не подтверждена. Пользователь ранее подтвердил значок и окно 3.2.77, но сообщил «Код недоступен»; это не доказательство приёмки 3.2.78. Полный `/goal` не отмечен завершённым.

При установке VM ранее кратко подключалась к своему исходному production enrollment до остановки и перевода на staging. Production код/конфигурация/БД не развёртывались и не менялись; утверждать неизменность production telemetry нельзя.

Первая immutable Helpdesk ecb-сборка использовала server/venv при systemd root-venv и получила 203EXEC. Служба остановлена, выполнен канонический повторный deploy в отдельный accepted-bundle-v2 с верным путём, runtime и digest проверены. Ошибочная сборка не является принятой.

Две остановки VM browser fixture были дефектами тестовой обёртки: UTF-8 чтение и лишнее чтение защищённого origin из Limited session. Они исправлены только во временном fixture; ACL и production runtime не менялись. При возврате VM wrapper успешно установил 3.2.75; последующая неверная проверка LASTEXITCODE была исправлена, защищённые данные восстановлены отдельным проверенным продолжением.

Итог проверки сохранён в канонических PLANS.md и этом отчёте отдельным документационным изменением; код приёмки/CI остаётся frozen ecb68704. Пользовательское изменение AGENTS.md сохранено. Нет production deployment, bulk rollout или заявления о готовности unsigned Setup к публичной публикации.

На снимке «Мои устройства» VM карточка показывает «Агент unknown» и «Активность не определена». Установленная версия и успешная свежая диагностика подтверждены отдельно через provenance и native completion; заполнение этих UI-метаданных этим отчётом не подтверждается.

**The implementation does not restore legacy Helpdesk Agent pairing. Endpoint proves device possession; Helpdesk Registry owns Person↔Device binding. ALT Linux Agent binding acceptance was intentionally excluded from First Wave.**

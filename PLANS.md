# PLANS.md - создание обращения пользователем

## Цель

Исправить UX создания обращения в кабинете пользователя: пользователь выбирает категорию, заполняет форму и нажимает создание на одной форме. Подсказки базы знаний не показываются до создания обращения; они остаются в уже созданном обращении с чатом.

## Анализ ошибки шага 2

Старый UI разрывал валидацию на три места: локальные обязательные поля показывались только при переходе "К проверке", server preview был спрятан за отдельной кнопкой "Проверить обращение", а финальный create мог вернуть общий alert без привязки к конкретному полю. Из-за этого пользователь видел "ошибка" или недоступную кнопку, но не понимал, что именно исправлять.

Конкретные источники ошибки:

- не выбрана категория обращения;
- не заполнены обязательные или условно видимые поля формы;
- неверный формат или значение поля: число, min/max, длина текста, pattern, email, url, недопустимый option;
- не заполнены данные обращения за другого сотрудника: сотрудник или причина;
- политика профиля/контакта/устройства: неполный профиль, нет контакта, нет однозначного основного устройства, форма недоступна без устройства;
- server preview блокирует создание: нет маршрута, нарушена политика обработки, требуется уточнение диагностик/согласований;
- create API возвращает `VALIDATION_ERROR` или другой backend error после повторной проверки payload.

## Объем текущего выполнения

1. [x] Перестроить порядок создания обращения.
   - Сначала выбор категории обращения и заполнение полей формы.
   - Отдельный встроенный шаг "Описание" убран.
   - Если описание нужно конкретной форме, оно приходит только из конструктора формы как обычное поле формы.
   - Подсказки остаются только после создания обращения в форме обращения с чатом.

2. [x] Встроить понятную проверку в заполнение формы.
   - Отдельный шаг "Проверка" убран.
   - Кнопка "Создать обращение" находится на форме и запускает локальную валидацию, server preview и create.
   - Ошибки обязательных/условных полей показываются прямо у полей и в status-сообщении.
   - Server `details.fields` / `field_errors` / `errors` отображаются на форме, а поле получает `aria-invalid`.
   - Preview blockers показываются внутри формы и не отправляют create-запрос.

3. [x] Убрать необходимость переключения между этапами.
   - После удаления отдельного review-шагa переключение этапов больше не требуется.
   - Категорию можно изменить прямо на форме до создания обращения.

4. [x] Сохранять прогресс создания обращения.
   - Незавершенное обращение сохраняется как черновик со статусом `draft`.
   - Черновик восстанавливается после перехода на другие вкладки кабинета и возврата к созданию обращения.
   - После успешного создания обращения черновик удаляется.

## Проверка

- [x] `pnpm --dir webapp exec vitest run src/pages/requester/new-request-page.test.tsx --reporter=dot` - 14 passed.
- [x] `pnpm --dir webapp exec tsc --noEmit` - passed.
- [x] `pnpm --dir webapp run build` - passed.
- [x] `pnpm --dir webapp exec playwright test tests/requester-workspace.spec.ts -g "requester create flow|requester on-behalf|requester dynamic multi-select" --reporter=line` - 3 passed after rebuilding `webapp/dist` for the fixture server.
- [x] `python scripts/test_web_first_registration_localization.py` - 9 passed.
- [x] `git diff --check` - passed, only CRLF warnings.
- [x] `python scripts/verify_workspace.py` - passed.
- [x] `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` - passed; remote stand updated to commit `4e79d34b64efc20788c2be729a0bd6e77980dc4d`, smoke health returned 200.
- [x] `python artifacts\browser_live_validation\requester-cabinet-f9267606-20260621T-live-final\requester_cabinet_live_check.py --base-url https://192.168.100.17:9443 --run-id requester-inline-validation-4e79d34b-20260623T033120Z --artifact-dir artifacts\browser_live_validation\requester-create-inline-validation-4e79d34b-20260623T032521Z --insecure-tls` - passed; screenshots: `00-single-form-initial.png`, `01-no-category-inline-error.png`, `02-required-field-inline-error.png`; verified no old review/suggestion step, category error inline, required field errors inline, and no preview/create/knowledge requests before local validation passes.
- [x] `python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 stop server` and `python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 stop control` - remote services stopped after live validation.

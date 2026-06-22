# PLANS.md - создание обращения пользователем

## Цель

Исправить UX создания обращения в кабинете пользователя: пользователь сначала выбирает категорию и заполняет форму обращения, затем проверяет данные и отправляет обращение. Подсказки не должны появляться до создания обращения в этом цикле.

## Объем текущего выполнения

1. [x] Перестроить порядок создания обращения.
   - Первый шаг: выбор категории обращения и заполнение полей формы.
   - Убрать отдельный встроенный шаг "Описание".
   - Если описание нужно конкретной форме, оно должно приходить только из конструктора формы как обычное поле формы.
   - Второй рабочий шаг: проверка перед отправкой.
   - Подсказки остаются только после создания обращения в форме обращения с чатом.

2. [ ] Планируется отдельно: понятная диагностика ошибок заполнения и отправки.
   - В этом цикле не реализуется.
   - После изменения порядка отдельно разобрать кейс, где интерфейс показывает общий сбой, но не объясняет конкретную ошибку заполнения.

3. [x] Добавить переключение между этапами создания обращения.
   - Этапы кликабельные.
   - Назад к форме можно перейти всегда.
   - Переход к проверке требует валидно заполненную форму.

4. [x] Сохранять прогресс создания обращения.
   - Незавершенное обращение сохраняется как черновик со статусом `draft`.
   - Черновик восстанавливается после перехода на другие вкладки кабинета и возврата к созданию обращения.
   - После успешного создания обращения черновик удаляется.

## Проверка

- [x] `pnpm --dir webapp exec vitest run src/pages/requester/new-request-page.test.tsx --reporter=dot` - 13 passed.
- [x] `pnpm --dir webapp exec tsc --noEmit --pretty false` - passed.
- [x] `pnpm --dir webapp build` - passed.
- [x] `pnpm --dir webapp exec playwright test tests/requester-workspace.spec.ts -g "requester create flow|requester on-behalf flow|requester dynamic multi-select"` - 3 passed.
- [x] `git diff --check` - no whitespace errors, only CRLF warnings.
- [x] `python scripts/verify_workspace.py` - passed.
- [x] Deploy committed state to stand: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` - remote smoke passed on `https://192.168.100.17:9443/api/health`.
- [x] Live browser validation on `https://192.168.100.17:9443/app/requester/new` after deploy - passed.
  - Evidence: `artifacts/browser_live_validation/requester-create-wizard-8f0c381c-20260623T024816/live-report.json`.
  - Screenshots: `00-initial-category-form.png`, `01-details-filled-draft.png`, `02-review-step.png`, `03-stepper-back-to-form.png`, `04-my-requests-navigation.png`, `05-restored-review-draft.png`, `06-restored-details-draft.png`.
  - Confirmed: first step is "Категория и форма"; built-in "Описание" and pre-submit "Подсказки" are absent; stepper switches both ways; draft has `status: "draft"` and restores after navigation to "Мои обращения"; `/api/knowledge/suggest` is not called before ticket creation; browser console/page/network errors are empty.

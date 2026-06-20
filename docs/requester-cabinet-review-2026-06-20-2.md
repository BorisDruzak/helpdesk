# Requester cabinet review

## Корректировки по проверке исполнения

### Проверка 2026-06-20 — range `bf86765541eea23674effea747fbd48779d1c5bd..d6507f800fdd8306943a4523982b50d8d172ab46`

**Head commit:** `d6507f800fdd8306943a4523982b50d8d172ab46` — `tests: stabilize webapp publish flows`.

**Вердикт:** новых проверенных расхождений по кабинету пользователя не найдено. Коммит меняет только frontend test expectations для admin publish flows: выбор формы перед публикацией в реестр и ожидание вызова publish-preview перед проверкой баннера. Requester routes, requester-visible русская локализация, dynamic request-form runtime, profile builder/runtime, shared UI components и Tailwind requester layout в этом диапазоне не менялись.

**Проверенные файлы:**

- `PLANS.md`
- `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`
- `webapp/src/pages/admin/request-template-studio-page.test.tsx`

**Проверенные наблюдения:**

1. `webapp/src/features/forms-builder/forms-builder-panel.test.tsx` теперь явно открывает форму `Печать / принтер` и ждёт, что поле `Ключ формы` получит значение `printer`, перед проверкой доступности кнопки `Опубликовать в реестр`. Это стабилизирует admin test flow и не меняет runtime кабинета пользователя.
2. `webapp/src/pages/admin/request-template-studio-page.test.tsx` теперь сначала подтверждает POST `/api/web/admin/request-studio/publish-preview`, затем ждёт баннер `Safe publish preview` с timeout 5000 мс. Это стабилизирует async ожидание в admin Studio test и не добавляет requester-visible строк.
3. Ранее зафиксированные проблемы терминологии/traceability остаются открытыми до отдельного исправления, но этот диапазон новых requester-scope проблем не добавил.

**Приоритет:** P3 для этой записи проверки; дополнительное исправление по проверенному диапазону не требуется.

# Guided Request Studio v2 — итоговая приёмка

Коммит: `f529ff048e975edda322211f0ad159ed6c075a3f`. P0–P10 завершены с явно разрешённой отсрочкой Sonar. Production не изменён.

## Этапы

| Этап | Коммит | Результат |
|---|---|---|
| P0 | `ef5b1db21e0693b8d5edacd8997f127704b7fbf6` | PASS_RECORDED_STAGE |
| P1 | `651b6e54f649961919df02b759a7be2ce88c9659` | PASS_RECORDED_STAGE |
| P2 | `8733dccb0409e1b0a58ddaf2d09be42a7485514a` | PASS_RECORDED_STAGE |
| P3 | `84dc6be2a6a4ec370868cad386296c5df84d3c45` | PASS_RECORDED_STAGE |
| P4 | `ebb3255ad1a0c126851d2d5f7158f817845221a8` | PASS_RECORDED_STAGE |
| P5 | `8bc7566ebbdda63b72e67e25116d76a2be7079d1` | PASS_RECORDED_STAGE |
| P6 | `956dd71396696b8f00868e22eb8d622b1964fe03` | PASS_RECORDED_STAGE |
| P7 | `fd9df7ae459b31d3e033240b019a1aec1bd45a11` | PASS_RECORDED_STAGE |
| P8 | `b0e508508d7825734e47d71d9599731f73c5818f` | PASS_RECORDED_STAGE |
| P9 | `1802ba24c6e9ce2cf280270e11ad1674495788aa` | PASS_RECORDED_STAGE |
| P10 | `f529ff048e975edda322211f0ad159ed6c075a3f` | COMPLETE_WITH_USER_SONAR_DEFERRAL |

## AC01–AC20

| Критерий | Требование | Результат и доказательство |
|---|---|---|
| AC01 | В Студии по умолчанию каталог всех типов, поиск, дерево категорий с произвольной вложенностью, статусы, primary «Создать сценарий». | PASS: Exact CI catalog regressions; installed V machine/Russian type search at four viewports |
| AC02 | Административный мастер строго пошаговый, на экране текущий шаг вместо всего сразу. | PASS: Exact CI wizard steps; installed V current step only |
| AC03 | В редакторе открыт только один selected block, остальное навигация; live preview скрываемый. | PASS: Exact CI single selected editor; installed V one block and one field editor |
| AC04 | «Расширенные настройки» ЛОКАЛЬНО внутри каждого поля и блока, НЕТ дополнительной вкладки/страницы/глобального advanced mode. | PASS: Exact CI local advanced controls; installed V local advanced and focus |
| AC05 | Страница формы имеет один вопрос или группу, сценарий 30+ вопросов не делает UI непригодным. | PASS: Exact CI 32-question keyboard/navigation cases; longform browser12 and installed D |
| AC06 | Condition/branch вычисляется сервером, conditional required и hidden stale answers работают. | PASS: Exact PostgreSQL conditions/hidden-required tests; installed E back/answer pruning DB proof |
| AC07 | У поля несколько совместимых ролей и правильная серверная проверка process mapping. | PASS: Exact backend role/process-mapping validation; installed D/H policy facts match |
| AC08 | Инструкция + «Помогло?» -> self-resolution без тикета либо запрос тикета. | PASS: Installed A/E self-resolution without ticket; B/C/D/F canonical ticket outcomes |
| AC09 | Diagnostic unavailable приводит к fallback; нет фиктивного успешного Endpoint результата и pre-ticket dispatch. | PASS: Installed A-F unavailable fallback; H four typed failures; unchanged global operation/link counters |
| AC10 | Приоритет/queue/SLA/согласования определяются существующими серверными политиками. | PASS: Installed D/H matched validated facts, canonical priority and actual SLA deadlines; real queue checks in exact CI |
| AC11 | Preview/simulate не создают тикета, операций, согласований или уведомлений. | PASS: Installed G/H/J/V preserve all ten tickets, session/version history and side-effect counters |
| AC12 | Double submit создаёт ровно 1 ticket, session становится ticket_created. | PASS: Installed F two submits one ticket; read-only DB count delta exactly one |
| AC13 | Actor/tenant scoping, 403/404 без утечек, revision conflicts и pinned sessions. | PASS: Installed G auditor/foreign-owner 403/404 and I pinned sessions; exact CI conflicts and TTL. Existing single-instance DB isolation; independent multi-tenant deployment not tested |
| AC14 | Health=ok не маскирует publish blockers графа/маршрута/SLA/закрытия. | PASS: Installed J healthOK with four independent publication blockers and focused correction controls; draft restored |
| AC15 | Diff + one-use token + revalidation + immutable version; rollback контролируем. | PASS: Installed I publishes V3 while V2 session remains pinned; exact CI one-use tokens/revalidation/immutable versions/restore-as-new-version |
| AC16 | Legacy forms, /help, agent, сервисы, тикеты и API продолжают работать. | PASS: Exact CI legacy forms/API/DTO17types/agent29/help redirect; no installed-agent release acceptance claimed |
| AC17 | Сценарий принтера A–J проходит через браузер без JSON/экспертных страниц. | PASS_WITH_CONTROLLED_API_FIXTURE_SETUP: Actual installed A-J browser outcomes and read-only DB proofs PASS. J broken-transition negative fixture was prepared through canonical draft API; blocker/focus verified in the real browser. Main scenario authoring uses the UI; no JSON editor is required in the user flow |
| AC18 | 1366×768/1920×1080 browser PASS, keyboard/accessibility, no body overflow, loading/empty/error. | PASS: Actual V four viewports; longform browser12 including slash/keyboard; exact CI loading/empty/error/retry cases |
| AC19 | Additive migrations/rollback, backend/frontend/E2E/CI green; Semgrep/coverage/Sonar не ослаблены. | PASS_WITH_USER_SONAR_DEFERRAL: Exact full CI18 plus Endpoint contract; exact Semgrep and frontend coverage; unchanged backend coverage source-equivalent. Migration147 and isolated147-146-147 drill. Sonar expressly deferred by user; no quality-gate PASS |
| AC20 | Нет включения сценариев и развёртывания на production без отдельного согласования владельца. | PASS: Draft PR only; no main merge/production deployment; synthetic scenario archived and staging service inactive |

## API

| Метод | Новый маршрут |
|---|---|
| GET | `/api/web/admin/request-studio/catalog` |
| POST | `/api/web/admin/request-studio/categories` |
| PUT | `/api/web/admin/request-studio/categories/{identifier}` |
| DELETE | `/api/web/admin/request-studio/categories/{identifier}` |
| POST | `/api/web/admin/request-studio/scenarios` |
| GET | `/api/web/admin/request-studio/scenarios/{identifier}` |
| PUT | `/api/web/admin/request-studio/scenarios/{identifier}/draft` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/archive` |
| GET | `/api/web/admin/request-studio/scenarios/{identifier}/versions` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/simulate` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/readiness` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/publish-preview` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/publish` |
| POST | `/api/web/admin/request-studio/scenarios/{identifier}/rollback-draft` |
| POST | `/api/web/requester/request-scenarios/sessions` |
| GET | `/api/web/requester/request-scenarios/sessions/{identifier}` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/answer` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/advance` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/back` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/step-preview` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/finish` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/ticket-preview` |
| POST | `/api/web/requester/request-scenarios/sessions/{identifier}/submit` |

Четыре прежних Studio API сохранены. Миграция146→147 добавляет пять таблиц: request_studio_categories, request_studio_scenarios, request_studio_scenario_versions, request_studio_drafts, request_studio_sessions. Откат удаляет новые сценарии/сессии; использовать проверенный backup/restore, а не откатывать пилот поверх сохранённой истории.

## Проверки и границы

Полный CI18 и Endpoint contracts PASS; frontend112 файлов/663 теста; fixture browser106; реальные staging A–J/V PASS. Закрыты10 принадлежащих пилоту тикетов, сценарий архивирован, версии/сессии сохранены, staging inactive. Реальных Endpoint операций пилот не создал.

- Sonar PR gate not computed; Community Build lacks PR analysis
- Frontend line66.91% against commissioning67.78%; no threshold lowered or Sonar verdict inferred
- Prior CI runner PostgreSQL absence not independently observed; canonical best-effort cleanup step succeeded
- Canonical staging installer rebuilt committed source; exact CI archive reuse is reserved for production
- Existing single-instance actor/database boundary tested; independent multi-tenant deployment and installed agents not tested

- J broken-transition negative fixture prepared through canonical draft API; real browser proves blocker/focus. User-facing scenario authoring requires no JSON editor

## Безопасное включение

1. Stop before production deployment or enablement at the agreed approval boundary; retain verified backup and existing protected confirmation secret
2. Resolve deferred Sonar PR analysis on an approved capable edition and evaluate the unchanged gates before any production admission
3. Use the reviewed production release and exact accepted archive; migrate additively with verified rollback/restore procedure
4. Enable reviewed real scenarios only after owner approval, valid category visibility and routing/SLA/approval/closure readiness
5. Perform bounded requester/support checks, monitor canonical audit and processing, and use reviewed rollback if acceptance fails

Полные receipts и SHA256 сохранены локально в artifacts/studio-f529ff04-final-acceptance.json. Проверенный runtime SHA указан выше; документальная фиксация результатов сохраняет эту проверенную версию приложения.

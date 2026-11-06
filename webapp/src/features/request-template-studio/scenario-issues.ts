import type { ScenarioDraftDefinition } from "./scenario-contract";

export type ScenarioApiIssue = { code: string; path: string; message?: string };

export function scenarioIssueText(issue: ScenarioApiIssue, definition?: ScenarioDraftDefinition): string {
  const parts = issue.path.replace(/^definition\./, "").split(".");
  const indexed = (value?: string) => value !== undefined && /^\d+$/.test(value);
  const block = parts[0] === "blocks" ? indexed(parts[1]) ? definition?.blocks?.[Number(parts[1])] : definition?.blocks?.find(item => item.id === parts[1]) : undefined;
  const fieldIndex = parts.indexOf("fields");
  const field = block?.kind === "form_page" && fieldIndex >= 0 ? indexed(parts[fieldIndex + 1]) ? block.fields[Number(parts[fieldIndex + 1])] : block.fields.find(item => item.key === parts[fieldIndex + 1]) : undefined;
  const labels: Record<string, string> = { title: block ? "Название шага" : "Название сценария", label: "Текст вопроса или варианта", description: "Описание", body: "Текст инструкции", service_code: "Раздел каталога", category_id: "Категория", offering_full_code: "Услуга каталога", transitions: "Переходы", to: "Следующий шаг", fields: "Вопросы", options: "Варианты ответа", entry_points: "Входы из каталога", entry_block_id: "Начало маршрута", first_response_minutes: "Срок первого ответа", resolution_minutes: "Срок решения", queue_code: "Очередь", request_template_key: "Тип обращения", value: "Значение условия", priority: "Приоритет ветви" };
  const location = [block ? `Шаг «${block.title}»` : parts[0] === "blocks" && indexed(parts[1]) ? `Шаг ${Number(parts[1]) + 1}` : null,
    field ? `Вопрос «${field.label}»` : null,
    labels[parts.at(-1) ?? ""] ?? (parts[0] === "processing" ? "Обработка карты" : "Настройки сценария")].filter(Boolean).join(" · ");
  const reasons: Record<string, string> = {
    attachment_target_invalid: "Подключите настройку SLA или маршрута к обычному блоку карты.",
    duplicate_attachment: "У блока уже есть настройка этого типа. Оставьте одну настройку SLA и одну настройку маршрута.",
    modifier_flow_target: "Связь настройки не является переходом заявки. Направьте переход к обычному блоку.",
    invalid_processing_source: "Выберите один совместимый источник настройки: профиль карты либо опубликованное правило услуги.",
    unconnected_catalog_entry: "Вход из каталога ещё не подключён. Потяните связь от его правой точки к первому блоку или удалите вход.",
    entry_limit: "Допускается не больше 64 входов из каталога.",
    missing_fallback: "Не настроен запасной переход «Иначе». Ветки по ответам могут быть настроены, но нужен отдельный путь, если ни одно условие не выполнено. В «Куда идти дальше» раскройте «Иначе» и выберите следующий шаг.",
    unknown_target: "Следующий шаг удалён или отсутствует. Выберите существующий шаг.",
    invalid_fallback_order: "Поставьте переход «Иначе» после условных веток.",
    ambiguous_precedence: "Для пересекающихся условий задайте разные приоритеты веток.",
    cycle: "Обнаружен замкнутый маршрут. Уберите переход, возвращающий к предыдущему шагу.",
    unreachable_block: "К шагу нет пути от начала сценария. Соедините его с маршрутом.",
  };
  return `${location}: ${reasons[issue.code] ?? issue.message ?? "Проверьте настройки этого поля или шага."}`;
}

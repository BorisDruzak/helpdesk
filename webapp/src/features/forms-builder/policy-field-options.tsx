import { useId } from "react";

export const resolutionChoices = [
  ["fixed_remote", "Исправлено удалённо", "Поддержка устранила причину без выезда."],
  ["workaround_provided", "Предложено временное решение", "Сотрудник может продолжить работу с обходным решением."],
  ["external_issue", "Проблема во внешней системе", "Причина находится за пределами обслуживаемой системы."],
  ["user_error", "Ошибка при работе", "Причина связана с действиями пользователя."],
  ["duplicate", "Повторное обращение", "Та же проблема уже зарегистрирована."],
  ["cannot_reproduce", "Проблема не повторилась", "Поддержка не смогла воспроизвести неисправность."],
];
export const visibilityChoices = [
  ["ticket_code", "Номер обращения", "Номер, по которому можно найти обращение."],
  ["title", "Тема обращения", "Краткое название проблемы."],
  ["description", "Описание обращения", "Описание, которое сотрудник отправил в поддержку."],
  ["public_messages", "Переписка с сотрудником", "Сообщения, предназначенные для заявителя."],
  ["public_status", "Статус для сотрудника", "Понятное сотруднику название текущего этапа."],
  ["attachments_public", "Общедоступные вложения", "Файлы, к которым у сотрудника есть доступ."],
  ["expected_due_at", "Плановый срок решения", "Дата и время ожидаемого завершения работ."],
];
export const hiddenFieldNames: Record<string, string> = {
  internal_notes: "Внутренние заметки", internal_comments: "Внутренние комментарии",
  internal_queue_comments: "Комментарии группы поддержки", ola_details: "Внутренние сроки поддержки",
  raw_diagnostics: "Подробные результаты диагностики", latest_operations: "Последние действия диагностики",
};
export const publicStatusNames: Record<string, string> = {
  new: "Обращение принято", queued: "В очереди", assigned: "Исполнитель назначен", in_progress: "В работе",
  waiting_user: "Ожидается ответ сотрудника", waiting_approval: "Ожидается согласование", resolved: "Решение предложено", closed: "Обращение закрыто", canceled: "Обращение отменено",
};
export function policyFieldName(key: string) {
  return visibilityChoices.find(item => item[0] === key)?.[1] ?? hiddenFieldNames[key] ?? "Дополнительное ранее настроенное поле";
}

// This is a view of the existing canonical array, including values unknown to this UI.
export function PolicyFieldOptions({ title, help, value, choices, onChange }: {
  title: string; help: string; value: unknown; choices: string[][]; onChange: (values: string[]) => void;
}) {
  const id = useId();
  const selected = Array.isArray(value) ? value.map(String) : [];
  const unknown = selected.filter(key => !choices.some(item => item[0] === key));
  return <fieldset className="space-y-3 rounded-lg border p-3 lg:col-span-full" aria-describedby={`${id}-help`}>
    <legend className="font-semibold">{title}</legend><p id={`${id}-help`} className="text-xs text-slate-600">{help}</p>
    {choices.map(([key, label, explanation], index) => <label key={key} className="flex items-start gap-2 text-sm">
      <input type="checkbox" className="mt-1" aria-label={`${title}: ${label}`} aria-describedby={`${id}-${index}`} checked={selected.includes(key)} onChange={event => onChange(event.target.checked ? [...new Set([...selected, key])] : selected.filter(item => item !== key))} />
      <span>{label}<span id={`${id}-${index}`} className="block text-xs text-slate-600">{explanation}</span></span>
    </label>)}
    {unknown.length > 0 && <p className="text-xs text-slate-600">Дополнительные ранее настроенные значения сохранены: {unknown.length}. Изменение этого списка их не удаляет.</p>}
  </fieldset>;
}

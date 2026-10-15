import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioSimulation } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioSimulationTrace } from "./scenario-simulation-trace";

const groups: Record<string, string> = { queue: "участники очереди", assignee: "исполнитель", watchers: "наблюдатели", requester: "сотрудник" };
function deadline(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? "Не определён" : new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(date); }
export function ScenarioProcessingResult({ result, definition }: { result: ScenarioSimulation; definition?: ScenarioDraftDefinition }) {
  const processing = result.processing;
  if (!processing) return null;
  const fields = (definition?.blocks || []).flatMap(block => block.kind === "form_page" ? block.fields : []);
  const branch = [...result.state.history, result.current_step?.id || result.state.current_block_id].filter(Boolean).map(id => definition?.blocks?.find(item => item.id === id)?.title || "Шаг сценария");
  function display(key: string, value: unknown) {
    const field = fields.find(item => (item.process_mapping?.fact_key || item.key) === key);
    function one(item: unknown): string { return field?.options?.find(option => option.value === item)?.label || (item === true ? "Да" : item === false ? "Нет" : item === null ? "Не знаю" : typeof item === "string" || typeof item === "number" ? String(item) : "Проверенный контекст"); }
    return Array.isArray(value) ? value.map(one).join(", ") : one(value);
  }
  return <section aria-label="Результат серверной проверки обработки" className="min-w-0 space-y-3 rounded border p-3">
    <h4 className="font-semibold">Результат серверной проверки обработки</h4>
    <p className="break-words">{branch.join(" → ")}</p>
    <p>Приоритет: {processing.priority.priority_class}</p>
    <p>Приоритет рассчитан сервером по проверенным ответам и действующей политике.</p>
    {processing.priority.reason && <AdvancedDisclosure title="Расширенные настройки"><p className="break-words">Основание расчёта: {processing.priority.reason}</p></AdvancedDisclosure>}
    <p>Очередь: {processing.routing.queue_title || processing.routing.queue_code || "Не определена"}</p>
    <p>Первый ответ: {processing.sla.first_response_min ? `${processing.sla.first_response_min} мин.` : "Не определён"}</p>
    <p>Срок выполнения: {processing.sla.resolution_min ? `${processing.sla.resolution_min} мин.` : "Не определён"}</p>
    {processing.sla.first_response_due_preview && <p>Ответить до: {deadline(processing.sla.first_response_due_preview)}</p>}
    {processing.sla.resolution_due_preview && <p>Решить до: {deadline(processing.sla.resolution_due_preview)}</p>}
    {processing.ola?.ack_min || processing.ola?.processing_min ? <p>Подтверждение поддержки: {processing.ola.ack_min ?? "не определено"} мин.; обработка: {processing.ola.processing_min ?? "не определено"} мин.</p> : <p>Внутренние сроки поддержки не настроены.</p>}
    <p>{processing.approval.required ? "Потребуется согласование" : "Согласование не требуется"}</p>
    <ScenarioSimulationTrace result={result} definition={definition} />
    {processing.closure && <p>{processing.closure.requires_public_summary && processing.closure.requires_resolution_code ? "При закрытии обязательны итог для сотрудника и код решения." : processing.closure.requires_public_summary ? "При закрытии обязателен итог для сотрудника." : processing.closure.requires_resolution_code ? "При закрытии обязателен код решения." : "Дополнительные требования закрытия не заданы политикой."}</p>}
    {processing.notification && <div><p>Уведомления не отправлялись. Правила для групп: {processing.notification.recipient_groups.map(group => groups[group]).filter(Boolean).join(", ") || "не заданы"}.</p>
      {processing.notification.channels.filter(item => item.enabled).map(item => <p key={item.channel}>Канал {item.channel}: отправка не выполнялась, доступность доставки требует проверки подключённого провайдера.</p>)}
    </div>}
    <h4 className="font-semibold">Проверенные ответы для обработки</h4>
    <dl className="space-y-2">{Object.entries(processing.validated_facts || {}).map(([key, value]) => <div key={key} className="min-w-0 break-words"><dt className="font-medium">{fields.find(item => (item.process_mapping?.fact_key || item.key) === key)?.label || "Проверенный факт"}</dt><dd>{display(key, value)}</dd></div>)}</dl>
  </section>;
}

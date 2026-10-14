import { useEffect, useRef, useState } from "react";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";

const labels: Record<ScenarioPolicyKind, string> = { priority: "Приоритет по ответам", routing: "Маршрут и очередь", sla: "Сроки обслуживания", ola: "Внутренние сроки поддержки", approval: "Согласование", notification: "Уведомления", closure: "Закрытие обращения", visibility: "Видимость обращения" };
const descriptions: Record<ScenarioPolicyKind, string> = {
  priority: "Как масштаб проблемы, срочность и важность влияют на приоритет. Значение рассчитывает сервер по ответам сотрудника.",
  routing: "В какую очередь и к какой группе поддержки попадёт обращение.",
  sla: "За какое время поддержка должна ответить и решить проблему. Сроки рассчитывает сервер по действующим правилам.",
  ola: "Сроки выполнения внутренних этапов работы поддержки.",
  approval: "Когда нужно согласование и кто должен согласовать обращение.",
  notification: "Кого и о каких событиях уведомлять.",
  closure: "Какие данные и подтверждения нужны, чтобы завершить обращение.",
  visibility: "Какие поля и статусы созданного обращения видит сотрудник. Это не публикация услуги в каталоге.",
};
export function ScenarioProcessing({ definition, disabled, onChange, focusPolicy }: { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: ScenarioDraftDefinition) => void; focusPolicy?: ScenarioPolicyKind }) {
  const policyRef = useRef<HTMLSelectElement>(null);
  const [policies, setPolicies] = useState<Record<string, AdminHelpdeskPolicyItem[]> | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { if (policies && focusPolicy) policyRef.current?.focus(); }, [policies, focusPolicy]);
  useEffect(() => {
    let active = true;
    setError(false); setPolicies(null);
    void fetchHelpdeskModelRegistry().then(data => { if (active) setPolicies(data.policies); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [attempt]);
  return <div className="min-w-0 space-y-4">
    <h2 className="text-lg font-semibold">Обработка услуги</h2>
    <p className="text-sm">Эти правила действуют для обращений, созданных через эту услугу. Выбирайте готовое опубликованное правило, только если нужно изменить действующую обработку.</p>
    <p className="text-sm text-slate-500">«Использовать действующие правила» сохраняет серверное наследование. Оно не создаёт недостающие правила: их наличие проверяется перед публикацией.</p>
    {focusPolicy && <p role="status" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">Проверьте настройку «{labels[focusPolicy]}» ниже, выберите опубликованное правило и сохраните черновик. Затем повторите проверку публикации.</p>}
    {error ? <div role="alert"><p>Не удалось загрузить политики обработки.</p><Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку политик</Button></div> : !policies ? <p role="status">Загрузка политик обработки…</p> : <div className="grid min-w-0 gap-4">
      {(Object.keys(labels) as ScenarioPolicyKind[]).sort((a, b) => Number(b === focusPolicy) - Number(a === focusPolicy)).map(kind => {
        const choices = (policies[kind] || []).filter((item, index, items) => item.is_active && !!item.published_at && items.findIndex(other => other.code === item.code && other.is_active && !!other.published_at) === index);
        const code = definition.process_binding.policy_refs?.[kind] || "";
        return <div key={kind} className={`min-w-0 rounded border p-3 ${kind === focusPolicy ? "border-amber-400 bg-amber-50" : ""}`}>
          <label>{labels[kind]}<Select ref={kind === focusPolicy ? policyRef : undefined} disabled={disabled} value={code} onChange={event => {
            const refs = { ...definition.process_binding.policy_refs };
            if (event.target.value) refs[kind] = event.target.value; else delete refs[kind];
            onChange({ ...definition, process_binding: { ...definition.process_binding, policy_refs: refs } });
          }}><option value="">Использовать действующие правила</option>
            {code && !choices.some(item => item.code === code) && <option value={code}>Выбранная политика недоступна</option>}
            {choices.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}
          </Select></label>
          <p className="mt-2 text-sm text-slate-500">{descriptions[kind]}</p>
          {!choices.length && <p className="mt-2 text-sm">Нет опубликованных правил для выбора. Если проверка сообщает об отсутствии правила, администратор должен сначала настроить и опубликовать его в Helpdesk.</p>}
          {code && !choices.some(item => item.code === code) && <p role="alert">Выберите опубликованную политику перед публикацией сценария.</p>}

        </div>;
      })}
    </div>}
    <section aria-label="Ответы для обработки" className="space-y-2"><h3 className="font-semibold">Ответы для обработки</h3>
      {(definition.blocks || []).flatMap(block => block.kind === "form_page" ? block.fields : []).filter(field => field.process_mapping?.roles?.some(role => role !== "display_only")).map(field => <div key={field.key} className="rounded border p-3"><p>{field.label}</p><p>Ответ передаётся выбранным политикам и проверяется сервером в тестовом прогоне.</p><AdvancedDisclosure title="Расширенные настройки"><p className="break-all">Проверенный факт: {field.process_mapping?.fact_key || field.key}</p><p className="break-all">Роли: {field.process_mapping?.roles?.join(", ")}</p></AdvancedDisclosure></div>)}
    </section>
  </div>;
}

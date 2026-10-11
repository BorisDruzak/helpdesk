import { useEffect, useState } from "react";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";

const labels: Record<ScenarioPolicyKind, string> = { priority: "Приоритет по ответам", routing: "Маршрут и очередь", sla: "Сроки обслуживания", ola: "Внутренние сроки поддержки", approval: "Согласование", notification: "Уведомления", closure: "Закрытие обращения", visibility: "Видимость обращения" };
export function ScenarioProcessing({ definition, disabled, onChange }: { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: ScenarioDraftDefinition) => void }) {
  const [policies, setPolicies] = useState<Record<string, AdminHelpdeskPolicyItem[]> | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false); setPolicies(null);
    void fetchHelpdeskModelRegistry().then(data => { if (active) setPolicies(data.policies); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [attempt]);
  return <div className="min-w-0 space-y-4">
    <h2 className="text-lg font-semibold">Обработка обращения</h2>
    <p>Выберите действующие политики. Их проверяет и выполняет существующий серверный механизм Helpdesk. Наследование сохраняет настройки услуги и шаблона.</p>
    {error ? <div role="alert"><p>Не удалось загрузить политики обработки.</p><Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку политик</Button></div> : !policies ? <p role="status">Загрузка политик обработки…</p> : <div className="grid min-w-0 gap-4 md:grid-cols-2">
      {(Object.keys(labels) as ScenarioPolicyKind[]).map(kind => {
        const choices = (policies[kind] || []).filter((item, index, items) => item.is_active && !!item.published_at && items.findIndex(other => other.code === item.code && other.is_active && !!other.published_at) === index);
        const code = definition.process_binding.policy_refs?.[kind] || "";
        return <div key={kind} className="min-w-0 rounded border p-3">
          <label>{labels[kind]}<Select disabled={disabled} value={code} onChange={event => {
            const refs = { ...definition.process_binding.policy_refs };
            if (event.target.value) refs[kind] = event.target.value; else delete refs[kind];
            onChange({ ...definition, process_binding: { ...definition.process_binding, policy_refs: refs } });
          }}><option value="">Наследовать настройки услуги и шаблона</option>
            {code && !choices.some(item => item.code === code) && <option value={code}>Выбранная политика недоступна</option>}
            {choices.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}
          </Select></label>
          {code && !choices.some(item => item.code === code) && <p role="alert">Выберите опубликованную политику перед публикацией сценария.</p>}
          <AdvancedDisclosure title="Расширенные настройки"><p className="break-all">Ссылка политики: {code || "наследование"}</p><p className="break-all">Шаблон: {definition.process_binding.request_template_key}</p></AdvancedDisclosure>
        </div>;
      })}
    </div>}
    <section aria-label="Ответы для обработки" className="space-y-2"><h3 className="font-semibold">Ответы для обработки</h3>
      {(definition.blocks || []).flatMap(block => block.kind === "form_page" ? block.fields : []).filter(field => field.process_mapping?.roles?.some(role => role !== "display_only")).map(field => <div key={field.key} className="rounded border p-3"><p>{field.label}</p><p>Ответ передаётся выбранным политикам и проверяется сервером в тестовом прогоне.</p><AdvancedDisclosure title="Расширенные настройки"><p className="break-all">Проверенный факт: {field.process_mapping?.fact_key || field.key}</p><p className="break-all">Роли: {field.process_mapping?.roles?.join(", ")}</p></AdvancedDisclosure></div>)}
    </section>
  </div>;
}

import { Select } from "../../components/ui/select";
import type { ScenarioBranchProcessing, ScenarioDraftDefinition } from "./scenario-contract";
import { ProcessingFactsEditor } from "./scenario-processing-facts";

export function ScenarioBranchProcessingEditor({ definition, value, disabled, onChange }: { definition: ScenarioDraftDefinition; value?: ScenarioBranchProcessing | null; disabled: boolean; onChange: (next: ScenarioBranchProcessing) => void }) {
 if (definition.schema_version !== 3) return null;
 return <fieldset disabled={disabled} className="min-w-0 space-y-3 rounded border p-3"><legend className="px-1 font-medium">Как обрабатывать обращение при выполнении этого условия?</legend>
  <label className="block">Направление обращения<Select value={value?.route ?? ""} onChange={event => onChange({ ...value, route: event.target.value || null })}><option value="">Сохранить ранее выбранное или значение карты</option>{value?.route && !definition.processing?.routes[value.route] && <option value={value.route}>Направление больше не найдено</option>}{Object.entries(definition.processing?.routes ?? {}).map(([key, route]) => <option key={key} value={key}>{route.title}</option>)}</Select></label>
  <label className="block">Профиль SLA ветки<Select value={value?.sla_profile ?? ""} onChange={event => onChange({ ...value, sla_profile: event.target.value || null })}><option value="">Сохранить ранее выбранный или значение карты</option>{value?.sla_profile && !definition.processing?.sla_profiles[value.sla_profile] && <option value={value.sla_profile}>Профиль больше не найден</option>}{Object.entries(definition.processing?.sla_profiles ?? {}).map(([key, profile]) => <option key={key} value={key}>{profile.title} · ответ {profile.first_response_minutes} мин., решение {profile.resolution_minutes} мин.</option>)}</Select></label>
  <label className="block">Согласование руководителем<Select value={value?.approval_required == null ? "" : String(value.approval_required)} onChange={event => onChange({ ...value, approval_required: event.target.value === "" ? null : event.target.value === "true" })}><option value="">Сохранить действующее правило</option><option value="true">Требуется</option><option value="false">Не требуется</option></Select></label>
  <p className="text-xs text-slate-500">Назначения применятся при создании обращения. Последующая ветка может заменить каждое значение отдельно; источник виден в проверке карты.</p>
 </fieldset>;
}
export { ProcessingFactsEditor };

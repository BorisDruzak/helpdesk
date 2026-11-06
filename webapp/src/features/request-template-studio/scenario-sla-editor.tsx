import { useEffect, useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import { ProcessingFactsEditor } from "./scenario-processing-facts";
import { newKey } from "./scenario-builder-model";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioSlaProfile } from "./scenario-contract";
type SlaBlock = Extract<ScenarioBlock, { kind: "sla" }>;
export function ScenarioSlaEditor({ block, definition, disabled, onChange }: { block: SlaBlock; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const [policies, setPolicies] = useState<AdminHelpdeskPolicyItem[]>([]), [error, setError] = useState(false);
  useEffect(() => { let active = true; if (!definition.processing) void fetchHelpdeskModelRegistry().then(data => { if (active) setPolicies((data.policies.sla ?? []).filter(item => item.is_active && !!item.published_at)); }).catch(() => { if (active) setError(true); }); return () => { active = false; }; }, [!!definition.processing]);
  const update = (next: SlaBlock) => onChange({ ...definition, blocks: definition.blocks?.map(item => item.id === block.id ? next : item) });
  const profile = block.sla_profile ? definition.processing?.sla_profiles[block.sla_profile] : undefined;
  function profileChange(value: ScenarioSlaProfile) { if (definition.processing && block.sla_profile) onChange({ ...definition, processing: { ...definition.processing, sla_profiles: { ...definition.processing.sla_profiles, [block.sla_profile]: value } } }); }
  return <fieldset disabled={disabled} className="space-y-4" aria-label="Редактор блока SLA"><p className="text-sm text-slate-500">Применяется автоматически на пройденном пути. Вопросы и инструкции сотруднику здесь не показываются.</p>
    <ProcessingFactsEditor value={block.processing_facts} disabled={disabled} onChange={processing_facts => update({ ...block, processing_facts })} />
    {definition.processing ? <><label className="block">Профиль SLA<Select value={block.sla_profile ?? ""} onChange={event => update({ ...block, sla_profile: event.target.value || null, policy_ref: null })}><option value="">Сохранить действующие сроки</option>{Object.entries(definition.processing.sla_profiles).map(([key, value]) => <option key={key} value={key}>{value.title}</option>)}</Select></label>
    <Button variant="outline" onClick={() => { const key = newKey("sla"); onChange({ ...definition, processing: { ...definition.processing!, sla_profiles: { ...definition.processing!.sla_profiles, [key]: { title: "Новый профиль SLA", first_response_minutes: 30, resolution_minutes: 480, time_basis: "calendar" } } }, blocks: definition.blocks?.map(item => item.id === block.id ? { ...block, sla_profile: key, policy_ref: null } : item) }); }}>Создать профиль SLA</Button>
    {profile && <section className="space-y-3 rounded border p-3"><label>Название профиля<Input value={profile.title} maxLength={300} onChange={event => profileChange({ ...profile, title: event.target.value })} /></label>{([['first_response_minutes', 'Первый ответ, минут'], ['resolution_minutes', 'Решение, минут']] as const).map(([key, label]) => <label key={key} className="block">{label}<Input type="number" min={1} value={profile[key]} onChange={event => profileChange({ ...profile, [key]: Number(event.target.value) })} /></label>)}<p className="text-xs text-slate-500">{profile.time_basis === "business" ? "Сроки по рабочему календарю услуги" : "Календарные сроки"}. Профиль общий для ссылающихся на него SLA-блоков этой карты.</p></section>}</> : <><label className="block">Действующее правило SLA<Select value={block.policy_ref ?? ""} onChange={event => update({ ...block, policy_ref: event.target.value || null, sla_profile: null })}><option value="">Не менять сроки услуги</option>{policies.map(policy => <option key={policy.code} value={policy.code}>{policy.title}</option>)}</Select></label>{error && <p role="alert">Не удалось загрузить правила SLA. Уже выбранное правило сохранено.</p>}</>}
  </fieldset>;
}

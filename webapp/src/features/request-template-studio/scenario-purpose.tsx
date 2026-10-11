import { useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; onChange: (value: ScenarioDraftDefinition) => void };
export function ScenarioPurpose({ definition, catalog, disabled, existing, onChange }: Props) {
  const [search, setSearch] = useState("");
  const offerings = catalog.offerings.filter(item => item.request_template_key && (item.public_title + item.full_code).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const selected = catalog.offerings.find(item => item.full_code === definition.offering_full_code);
  const choices = selected && !offerings.includes(selected) ? [selected, ...offerings] : offerings;
  return <fieldset disabled={disabled} className="min-w-0 space-y-4">
    <legend className="mb-4 text-lg font-semibold">Категория и назначение</legend>
    <label className="block">Название сценария<Input value={definition.title} maxLength={300} onChange={event => onChange({ ...definition, title: event.target.value })} /></label>
    <label className="block">Описание<textarea className="field-base mt-1 w-full min-w-0 rounded-md border p-3" rows={3} maxLength={2000} value={definition.description ?? ""} onChange={event => onChange({ ...definition, description: event.target.value })} /></label>
    {!existing && <label className="block">Поиск услуги<Input value={search} onChange={event => setSearch(event.target.value)} placeholder="Найдите услугу по названию" /></label>}
    <label className="block">Услуга<Select disabled={existing} value={definition.offering_full_code} onChange={event => {
      const offering = catalog.offerings.find(item => item.full_code === event.target.value);
      if (offering?.request_template_key && offering.service_code) onChange({ ...definition, service_code: offering.service_code, offering_full_code: offering.full_code, category_id: null, process_binding: { request_template_key: offering.request_template_key } });
    }}><option value="">Выберите услугу</option>{choices.map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>
    <label className="block">Категория<Select value={definition.category_id ?? ""} onChange={event => onChange({ ...definition, category_id: event.target.value || null })}><option value="">Без категории</option>{catalog.categories.filter(item => item.service_code === definition.service_code && item.lifecycle_status !== "archived").map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
    <AdvancedDisclosure title="Расширенные настройки" description="Идентификатор создаётся автоматически и сохраняется вместе с черновиком.">
      <label className="block">Ключ сценария<Input disabled={existing} value={definition.scenario_key} pattern="[a-z0-9][a-z0-9_-]*" maxLength={100} onChange={event => onChange({ ...definition, scenario_key: event.target.value })} /></label>
      <p className="break-all text-sm">Шаблон обращения: {definition.process_binding.request_template_key || "выберите услугу"}</p>
    </AdvancedDisclosure>
  </fieldset>;
}

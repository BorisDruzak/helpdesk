import { useRef, useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioCatalog, ScenarioCategory } from "./scenario-api";
import { ScenarioCategoryForm } from "./scenario-category-form";
import { ScenarioOfferingForm } from "./scenario-offering-form";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const ignoreDirty = () => {};
type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; onChange: (value: ScenarioDraftDefinition) => void; onCategoryDirty?: (dirty: boolean) => void; onCategoryOpen?: (open: boolean) => void; onCategoryCreated?: () => Promise<void> };
export function ScenarioPurpose({ definition, catalog, disabled, existing, onChange, onCategoryDirty = ignoreDirty, onCategoryOpen, onCategoryCreated }: Props) {
  const [search, setSearch] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [creatingOffering, setCreatingOffering] = useState(false);
  const [createdOfferings, setCreatedOfferings] = useState<AdminServiceCatalogOffering[]>([]);
  const latest = useRef({ definition, onChange }); latest.current = { definition, onChange };
  const [createdCategories, setCreatedCategories] = useState<ScenarioCategory[]>([]);
  const categories = [...catalog.categories, ...createdCategories.filter(item => !catalog.categories.some(saved => saved.id === item.id))];
  function closeCategory() { setCreatingCategory(false); onCategoryOpen?.(false); }
  const allOfferings = [...catalog.offerings, ...createdOfferings.filter(item => !catalog.offerings.some(saved => saved.full_code === item.full_code))];
  const offerings = allOfferings.filter(item => item.request_template_key && (item.public_title + item.full_code).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const selected = allOfferings.find(item => item.full_code === definition.offering_full_code);
  const service = catalog.services.find(item => item.code === definition.service_code);
  const serviceCategories = categories.filter(item => item.service_code === definition.service_code && item.lifecycle_status !== "archived");
  const choices = selected && !offerings.includes(selected) ? [selected, ...offerings] : offerings;
  return <fieldset disabled={disabled} className="min-w-0 space-y-4">
    <legend className="mb-4 text-lg font-semibold">Категория и назначение</legend>
    <label className="block">Название сценария<Input value={definition.title} maxLength={300} onChange={event => onChange({ ...definition, title: event.target.value })} /></label>
    <label className="block">Описание<textarea className="field-base mt-1 w-full min-w-0 rounded-md border p-3" rows={3} maxLength={2000} value={definition.description ?? ""} onChange={event => onChange({ ...definition, description: event.target.value })} /></label>
    {!existing && <label className="block">Поиск услуги<Input value={search} onChange={event => setSearch(event.target.value)} placeholder="Найдите услугу по названию" /></label>}
    <label className="block">Услуга<Select disabled={existing || creatingCategory || creatingOffering} value={definition.offering_full_code} onChange={event => {
      const offering = allOfferings.find(item => item.full_code === event.target.value);
      if (offering?.request_template_key && offering.service_code) onChange({ ...definition, service_code: offering.service_code, offering_full_code: offering.full_code, category_id: null, publish_offering: createdOfferings.some(item => item.full_code === offering.full_code), process_binding: { request_template_key: offering.request_template_key } });
    }}><option value="">Выберите услугу</option>{choices.map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>
    <p className="text-sm">Раздел: <strong>{service?.public_title ?? "определится после выбора услуги"}</strong></p>
    <label className="block">Подкатегория<Select disabled={!definition.service_code || creatingCategory || creatingOffering} value={definition.category_id ?? ""} onChange={event => onChange({ ...definition, category_id: event.target.value || null })}><option value="">В основном разделе</option>{serviceCategories.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
    {!definition.service_code ? <p className="text-sm text-slate-500">Сначала выберите услугу — её раздел и подкатегории появятся здесь.</p> : !serviceCategories.length && <p className="text-sm text-slate-500">В разделе «{service?.public_title}» пока нет подкатегорий. Услуга уже видна в этом разделе; при необходимости создайте подкатегорию ниже.</p>}
    {!disabled && !existing && !creatingCategory && !creatingOffering && <Button variant="secondary" onClick={() => { setCreatingOffering(true); onCategoryOpen?.(true); }}>Создать услугу здесь</Button>}
    {creatingOffering && <ScenarioOfferingForm catalog={catalog} initialServiceCode={definition.service_code} onDirty={onCategoryDirty} onCancel={() => { setCreatingOffering(false); onCategoryOpen?.(false); }} onDone={async saved => {
      setCreatedOfferings(items => [...items, saved]);
      const current = latest.current;
      current.onChange({ ...current.definition, service_code: saved.service_code ?? "", offering_full_code: saved.full_code, category_id: saved.service_code === current.definition.service_code ? current.definition.category_id : null, publish_offering: true, process_binding: { request_template_key: saved.request_template_key ?? "" } });
      await onCategoryCreated?.();
      setCreatingOffering(false); onCategoryOpen?.(false);
    }} />}
    {definition.publish_offering && <p role="status">Новая услуга будет опубликована вместе со сценарием после общей проверки.</p>}
    {!disabled && !creatingCategory && !creatingOffering && <Button variant="secondary" disabled={!definition.service_code} onClick={() => { setCreatingCategory(true); onCategoryOpen?.(true); }}>Создать категорию здесь</Button>}
    {creatingCategory && <ScenarioCategoryForm catalog={{ ...catalog, categories }} initialServiceCode={definition.service_code} initialParentId={definition.category_id} onDirty={onCategoryDirty} onCancel={closeCategory} onDone={async saved => {
      setCreatedCategories(items => [...items, saved]);
      onChange({ ...definition, category_id: saved.id });
      closeCategory();
      await onCategoryCreated?.();
    }} />}
    <AdvancedDisclosure title="Расширенные настройки" description="Идентификатор создаётся автоматически и сохраняется вместе с черновиком.">
      <label className="block">Ключ сценария<Input disabled={existing} value={definition.scenario_key} pattern={"[a-z0-9][a-z0-9_\\-]*"} maxLength={100} onChange={event => onChange({ ...definition, scenario_key: event.target.value })} /></label>
      <p className="break-all text-sm">Шаблон обращения: {definition.process_binding.request_template_key || "выберите услугу"}</p>
    </AdvancedDisclosure>
  </fieldset>;
}

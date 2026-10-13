import { useEffect, useRef, useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioCatalog, ScenarioCategory } from "./scenario-api";
import { ScenarioCategoryForm } from "./scenario-category-form";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const ignoreDirty = () => {};
type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; onChange: (value: ScenarioDraftDefinition) => void; focusBinding?: boolean; onCategoryDirty?: (dirty: boolean) => void; onCategoryOpen?: (open: boolean) => void; onCategoryCreated?: () => Promise<void> };
export function ScenarioPurpose({ definition, catalog, disabled, existing, onChange, focusBinding, onCategoryDirty = ignoreDirty, onCategoryOpen, onCategoryCreated }: Props) {
  const bindingRef = useRef<HTMLSelectElement>(null);
  useEffect(() => { if (!focusBinding) return; const select = bindingRef.current; const details = select?.closest("details"); if (details) details.open = true; select?.focus(); }, [focusBinding]);
  const [search, setSearch] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [createdCategories, setCreatedCategories] = useState<ScenarioCategory[]>([]);
  const categories = [...catalog.categories, ...createdCategories.filter(item => !catalog.categories.some(saved => saved.id === item.id))];
  function closeCategory() { setCreatingCategory(false); onCategoryOpen?.(false); }
  const allOfferings = catalog.offerings;
  const offerings = allOfferings.filter(item => item.request_template_key && (item.public_title + item.full_code).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const selected = allOfferings.find(item => item.full_code === definition.offering_full_code);
  const service = catalog.services.find(item => item.code === definition.service_code);
  const serviceCategories = categories.filter(item => item.service_code === definition.service_code && item.lifecycle_status !== "archived");
  const choices = selected && !offerings.includes(selected) ? [selected, ...offerings] : offerings;
  return <fieldset disabled={disabled} className="min-w-0 space-y-4">
    <legend className="mb-4 text-lg font-semibold">Название и раздел</legend><p className="text-sm text-slate-600">Карта объединяет вопросы и действия. Пункт каталога — вход сотрудника в эту карту. Тип создаваемого обращения настраивается в результате.</p>
    <label className="block">Название карты<Input value={definition.title} maxLength={300} onChange={event => onChange({ ...definition, title: event.target.value })} /></label>
    <label className="block">Описание<textarea className="field-base mt-1 w-full min-w-0 rounded-md border p-3" rows={3} maxLength={2000} value={definition.description ?? ""} onChange={event => onChange({ ...definition, description: event.target.value })} /></label>
    <p className="text-sm">Раздел: <strong>{service?.public_title ?? "определится после выбора услуги"}</strong></p>
    <label className="block">Категория карты (необязательно)<Select disabled={!definition.service_code || creatingCategory} value={definition.category_id ?? ""} onChange={event => onChange({ ...definition, category_id: event.target.value || null })}><option value="">В основном разделе</option>{serviceCategories.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
    {!definition.service_code ? <p className="text-sm text-slate-500">Раздел выбирается при создании карты. Привязку к типу обращения можно настроить в результате.</p> : !serviceCategories.length && <p className="text-sm text-slate-500">В разделе «{service?.public_title}» пока нет подкатегорий. Услуга уже видна в этом разделе; при необходимости создайте подкатегорию ниже.</p>}
    {!disabled && !creatingCategory && <Button variant="secondary" disabled={!definition.service_code} onClick={() => { setCreatingCategory(true); onCategoryOpen?.(true); }}>Создать категорию здесь</Button>}
    {creatingCategory && <ScenarioCategoryForm catalog={{ ...catalog, categories }} initialServiceCode={definition.service_code} initialParentId={definition.category_id} onDirty={onCategoryDirty} onCancel={closeCategory} onDone={async saved => {
      setCreatedCategories(items => [...items, saved]);
      onChange({ ...definition, category_id: saved.id });
      closeCategory();
      await onCategoryCreated?.();
    }} />}
    <AdvancedDisclosure title="Расширенные настройки" description="Идентификатор создаётся автоматически и сохраняется вместе с черновиком.">
    {!existing && <label className="block">Поиск типа обращения<Input value={search} onChange={event => setSearch(event.target.value)} placeholder="Найдите услугу по названию" /></label>}
    <label className="block">Тип обращения<Select ref={bindingRef} disabled={existing || creatingCategory} value={definition.offering_full_code} onChange={event => {
      const offering = allOfferings.find(item => item.full_code === event.target.value);
      if (offering?.request_template_key && offering.service_code) onChange({ ...definition, service_code: offering.service_code, offering_full_code: offering.full_code, category_id: null, publish_offering: offering.lifecycle_status === "draft", process_binding: { request_template_key: offering.request_template_key } });
    }}><option value="">Выберите тип обращения</option>{choices.map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>
      <label className="block">Ключ сценария<Input disabled={existing} value={definition.scenario_key} pattern={"[a-z0-9][a-z0-9_\\-]*"} maxLength={100} onChange={event => onChange({ ...definition, scenario_key: event.target.value })} /></label>
      <p className="break-all text-sm">Шаблон обращения: {definition.process_binding.request_template_key || "выберите услугу"}</p>
    </AdvancedDisclosure>
  </fieldset>;
}

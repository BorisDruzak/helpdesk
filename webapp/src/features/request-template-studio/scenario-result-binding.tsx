import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskRequestTemplateItem } from "../forms-builder/api";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioOfferingForm } from "./scenario-offering-form";

export function ScenarioResultBinding({ definition, catalog, disabled, existing, onChange, onTest, onCheck }: {
  definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; onChange: (next: ScenarioDraftDefinition) => void; onTest?: () => void; onCheck?: () => void;
}) {
  const [templates, setTemplates] = useState<AdminHelpdeskRequestTemplateItem[] | null>(null);
  const [loadError, setLoadError] = useState(false), [attempt, setAttempt] = useState(0);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<AdminServiceCatalogOffering[]>([]);
  const latest = useRef(definition); latest.current = definition;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; let active = true; setLoadError(false); void fetchHelpdeskModelRegistry().then(data => { if (active) setTemplates(data.request_templates ?? []); }).catch(() => { if (active) setLoadError(true); }); return () => { active = false; mounted.current = false; }; }, [attempt]);
  const offerings = [...catalog.offerings, ...created.filter(item => !catalog.offerings.some(old => old.full_code === item.full_code))];
  const selected = offerings.find(item => item.full_code === definition.offering_full_code);
  const template = templates?.find(item => item.template_code === definition.process_binding.request_template_key && item.is_active && item.published_at);
  function bind(offering: AdminServiceCatalogOffering) {
    if (!mounted.current || !offering.request_template_key) return;
    onChange({ ...latest.current, service_code: offering.service_code ?? latest.current.service_code, offering_full_code: offering.full_code,
      publish_offering: offering.lifecycle_status === "draft", process_binding: { ...latest.current.process_binding, request_template_key: offering.request_template_key } });
  }
  return <section aria-label="Данные создаваемого обращения" className="space-y-3">
    <label className="block text-sm font-semibold">Тип создаваемого обращения<Select disabled={disabled || existing} value={definition.offering_full_code} onChange={event => { const value = offerings.find(item => item.full_code === event.target.value); if (value) bind(value); }}><option value="">Выберите тип обращения</option>{!selected && definition.offering_full_code && <option value={definition.offering_full_code}>Связанный тип обращения · нет в текущем списке</option>}{offerings.filter(item => item.full_code === definition.offering_full_code || (item.request_template_key && item.lifecycle_status !== "retired" && item.service_code === definition.service_code)).map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>
    <p className="text-xs text-slate-500">Тип обращения определяет шаблон заявки. Эта привязка общая для всех результатов карты{existing ? " и сохраняется у существующей карты" : ""}.</p>
    {!definition.offering_full_code && <p role="status" className="studio-next-help">Выберите тип обращения, чтобы сохранить черновик на сервере. Вопросы и маршрут остаются в редакторе.</p>}
    {loadError && <div role="alert" className="text-sm"><p>Не удалось загрузить название шаблона заявки.</p><Button variant="ghost" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку шаблона</Button></div>}
    <p className="text-sm">Шаблон заявки: <strong>{template?.public_title ?? (definition.process_binding.request_template_key ? "Связан с выбранным типом обращения" : "Не выбран")}</strong></p>
    <div className="rounded-lg border p-3 text-sm"><strong>Действующие политики Helpdesk</strong><p className="mt-1 text-slate-600">Маршрутизация, приоритет, SLA и согласование наследуются от раздела и шаблона. Точный результат по ответам покажет сервер при тестировании.</p></div>
    <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={onTest}>Проверить пример обработки</Button><Button variant="ghost" onClick={onCheck}>Проверить готовность</Button></div>
    {!disabled && !existing && !creating && <Button variant="ghost" onClick={() => setCreating(true)}>Создать новый тип обращения</Button>}
    {creating && <ScenarioOfferingForm catalog={{ ...catalog, offerings }} initialServiceCode={definition.service_code} onDirty={() => {}} onCancel={() => setCreating(false)} onDone={async saved => { if (!mounted.current) return; setCreated(items => [...items, saved]); bind(saved); setCreating(false); }} />}
    <AdvancedDisclosure title="Техническая привязка"><p className="break-all text-xs">Тип: {definition.offering_full_code || "не выбран"}<br />Шаблон: {definition.process_binding.request_template_key || "не выбран"}</p></AdvancedDisclosure>
  </section>;
}

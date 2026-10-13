import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { fetchAdminFormsCatalog, fetchHelpdeskModelRegistry, type AdminHelpdeskRequestTemplateItem } from "../forms-builder/api";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioOfferingForm } from "./scenario-offering-form";
import { addTemplateQuestions } from "./scenario-template-questions";

export function ScenarioResultBinding({ definition, catalog, disabled, existing, onChange, onTest, onCheck, resultBlockId }: {
  definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; onChange: (next: ScenarioDraftDefinition) => void; onTest?: () => void; onCheck?: () => void; resultBlockId?: string;
}) {
  const [templates, setTemplates] = useState<AdminHelpdeskRequestTemplateItem[] | null>(null);
  const [loadError, setLoadError] = useState(false), [attempt, setAttempt] = useState(0);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<AdminServiceCatalogOffering[]>([]);
  const [importing,setImporting]=useState(false),[importError,setImportError]=useState("");
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
  async function importQuestions(){
    if(!resultBlockId||disabled||importing)return;
    const key=latest.current.process_binding.request_template_key,scenarioKey=latest.current.scenario_key;
    setImporting(true);setImportError("");
    try {
      const [forms,registry]=await Promise.all([fetchAdminFormsCatalog(),fetchHelpdeskModelRegistry()]);
      if(!mounted.current)return;
      if(latest.current.scenario_key!==scenarioKey||latest.current.process_binding.request_template_key!==key)throw new Error("Тип обращения изменился. Повторите добавление вопросов.");
      const form=forms.forms?.find(item=>item.key===key),template=registry.request_templates?.find(item=>item.template_code===key&&item.is_active&&item.published_at);
      const schema=registry.form_schemas?.find(item=>item.schema_id===template?.form_schema_id)??registry.form_schemas?.find(item=>item.request_template_code===key||item.form_key===key);
      if(!form&&!schema)throw new Error("Не удалось найти действующую форму выбранного типа обращения.");
      if(!form&&schema?.conditions?.length)throw new Error("В шаблоне есть условные вопросы. Настройте их через редактор формы.");
      onChange(addTemplateQuestions(latest.current,resultBlockId,form?.fields??schema!.fields));
    }catch(failure){if(mounted.current)setImportError(failure instanceof Error?failure.message:"Не удалось добавить вопросы шаблона.");}
    finally{if(mounted.current)setImporting(false);}
  }
  return <section aria-label="Данные создаваемого обращения" className="space-y-3">
    <label className="block text-sm font-semibold">Тип создаваемого обращения<Select disabled={disabled || existing} value={definition.offering_full_code} onChange={event => { const value = offerings.find(item => item.full_code === event.target.value); if (value) bind(value); }}><option value="">Выберите тип обращения</option>{!selected && definition.offering_full_code && <option value={definition.offering_full_code}>Связанный тип обращения · нет в текущем списке</option>}{offerings.filter(item => item.full_code === definition.offering_full_code || (item.request_template_key && item.lifecycle_status !== "retired" && item.service_code === definition.service_code)).map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>
    <p className="text-xs text-slate-500">Тип обращения определяет шаблон заявки. Эта привязка общая для всех результатов карты{existing ? " и сохраняется у существующей карты" : ""}.</p>
    {!definition.offering_full_code && <p role="status" className="studio-next-help">Выберите тип обращения, чтобы сохранить черновик на сервере. Вопросы и маршрут остаются в редакторе.</p>}
    {loadError && <div role="alert" className="text-sm"><p>Не удалось загрузить название шаблона заявки.</p><Button variant="ghost" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку шаблона</Button></div>}
    <p className="text-sm">Шаблон заявки: <strong>{template?.public_title ?? (definition.process_binding.request_template_key ? "Связан с выбранным типом обращения" : "Не выбран")}</strong></p>
    {resultBlockId&&<div className="studio-next-help"><p>Для создания обращения нужны обязательные ответы действующего шаблона. Их можно добавить отдельной страницей перед этим результатом.</p><Button className="h-auto w-full whitespace-normal" disabled={disabled||importing||!definition.process_binding.request_template_key} variant="outline" onClick={()=>void importQuestions()}>{importing?"Загрузка вопросов…":"Добавить обязательные вопросы типа обращения"}</Button>{importError&&<p role="alert">{importError}</p>}</div>}
    <div className="rounded-lg border p-3 text-sm"><strong>Действующие политики Helpdesk</strong><p className="mt-1 text-slate-600">Маршрутизация, приоритет, SLA и согласование наследуются от раздела и шаблона. Точный результат по ответам покажет сервер при тестировании.</p></div>
    <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={onTest}>Проверить пример обработки</Button><Button variant="ghost" onClick={onCheck}>Проверить готовность</Button></div>
    {!disabled && !existing && !creating && <Button variant="ghost" onClick={() => setCreating(true)}>Создать новый тип обращения</Button>}
    {creating && <ScenarioOfferingForm catalog={{ ...catalog, offerings }} initialServiceCode={definition.service_code} onDirty={() => {}} onCancel={() => setCreating(false)} onDone={async saved => { if (!mounted.current) return; setCreated(items => [...items, saved]); bind(saved); setCreating(false); }} />}
    <AdvancedDisclosure title="Техническая привязка"><p className="break-all text-xs">Тип: {definition.offering_full_code || "не выбран"}<br />Шаблон: {definition.process_binding.request_template_key || "не выбран"}</p></AdvancedDisclosure>
  </section>;
}

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskRequestTemplateItem } from "../forms-builder/api";
import { saveOfferingDraft, type AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioCatalog } from "./scenario-api";

const requestTypes = [{ code: "incident", title: "Инцидент", requestType: "incident" }, { code: "request", title: "Общий запрос", requestType: "request" }, { code: "service_request", title: "Запрос услуги", requestType: "service_request" }, { code: "access", title: "Запрос доступа", requestType: "access" }, { code: "software_install", title: "Установка ПО", requestType: "service_request" }, { code: "consultation", title: "Консультация", requestType: "consultation" }];

export function ScenarioOfferingForm({ catalog, initialServiceCode, onDone, onCancel, onDirty }: { catalog: ScenarioCatalog; initialServiceCode: string; onDone: (saved: AdminServiceCatalogOffering) => Promise<void>; onCancel: () => void; onDirty: (dirty: boolean) => void }) {
  const services = catalog.services.filter(item => item.lifecycle_status === "published" && item.visibility === "public");
  const [value, setValue] = useState(() => ({ service_code: services.find(item => item.code === initialServiceCode)?.code ?? services[0]?.code ?? "", title: "", description: "", request_type: "incident", template: "" }));
  const [code] = useState(() => `scenario_${crypto.randomUUID().replaceAll("-", "")}`);
  const initial = useRef(JSON.stringify(value));
  const dirty = JSON.stringify(value) !== initial.current;
  const latestDone = useRef(onDone); latestDone.current = onDone;
  const [templates, setTemplates] = useState<AdminHelpdeskRequestTemplateItem[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  useEffect(() => {
    let active = true;
    setTemplates(null); setLoadError(false);
    void fetchHelpdeskModelRegistry().then(data => {
      if (active) setTemplates(data.request_templates.filter((item, index, items) => item.is_active && !!item.published_at && items.findIndex(other => other.template_code === item.template_code && other.is_active && !!other.published_at) === index));
    }).catch(() => { if (active) setLoadError(true); });
    return () => { active = false; };
  }, [attempt]);
  const template = templates?.find(item => item.template_code === value.template);
  const mutation = useMutation({ mutationFn: async () => {
    if (!template || !services.some(item => item.code === value.service_code) || catalog.offerings.some(item => item.full_code === `${value.service_code}.${code}`)) throw new Error("Offering candidate unavailable");
    const profile = requestTypes.find(item => item.code === value.request_type);
    if (!profile) throw new Error("Request profile unavailable");
    const payload = { service_code: value.service_code, code, public_title: value.title.trim(), short_description: value.description.trim(), request_type: profile.requestType, metadata: { studio_profile: profile.code },
      request_template_key: template.template_code, ticket_type_code: template.ticket_type, lifecycle_status: "draft" as const, visibility: "public" as const };
    const result = await saveOfferingDraft(payload);
    await latestDone.current(result.offering);
  } });
  return <form className="min-w-0 space-y-4 rounded-xl border p-5" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
    <h2 className="text-lg font-semibold">Новая услуга</h2>
    <p>Создайте черновик услуги. Она станет доступна сотрудникам после общей проверки и публикации со сценарием.</p>
    <fieldset disabled={mutation.isPending} className="space-y-4">
      <label className="block">Раздел услуги<Select value={value.service_code} onChange={event => setValue({ ...value, service_code: event.target.value })}><option value="">Выберите опубликованный раздел</option>{services.map(item => <option key={item.code} value={item.code}>{item.public_title}</option>)}</Select></label>
      {!services.length && <p role="alert">Нет опубликованных публичных разделов для новой услуги.</p>}
      <label className="block">Название услуги<Input required maxLength={300} value={value.title} onChange={event => setValue({ ...value, title: event.target.value })} /></label>
      <label className="block">Краткое описание услуги<Input maxLength={2000} value={value.description} onChange={event => setValue({ ...value, description: event.target.value })} /></label>
      <label className="block">Тип запроса<Select value={value.request_type} onChange={event => setValue({ ...value, request_type: event.target.value })}>{requestTypes.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</Select></label>
      {loadError ? <div role="alert"><p>Не удалось загрузить шаблоны обработки.</p><Button variant="outline" onClick={() => setAttempt(count => count + 1)}>Повторить загрузку шаблонов</Button></div> : !templates ? <p role="status">Загрузка шаблонов обработки…</p> : <>
        <label className="block">Шаблон обработки<Select value={value.template} onChange={event => setValue({ ...value, template: event.target.value })}><option value="">Выберите действующий шаблон</option>{templates.map(item => <option key={item.template_code} value={item.template_code}>{item.public_title}</option>)}</Select></label>
        {!templates.length && <p role="alert">Нет опубликованных шаблонов обработки. Подготовьте шаблон в существующем реестре Helpdesk.</p>}
      </>}
      <p className="text-sm">Маршрут, сроки и остальные политики наследуются от раздела и шаблона. Настроить их для сценария можно на этапе обработки.</p>
    </fieldset>
    {mutation.isError && <p role="alert">Не удалось создать черновик услуги. Проверьте настройки и повторите.</p>}
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={mutation.isPending || !value.title.trim() || !value.service_code || !template}>Создать черновик услуги</Button><Button variant="ghost" disabled={mutation.isPending} onClick={() => { if (!dirty || window.confirm("Закрыть услугу без сохранения изменений?")) onCancel(); }}>Отмена</Button></div>
  </form>;
}

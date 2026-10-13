import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioOfferingForm } from "./scenario-offering-form";
import { createScenarioStarter, starterChoices, type ScenarioStarter } from "./scenario-starter";

export function ScenarioCreateDialog({ catalog, offering, onCreate, onClose, onOfferingCreated }: {
  catalog: ScenarioCatalog; offering?: AdminServiceCatalogOffering; onCreate: (draft: ScenarioDraftDefinition) => void; onClose: () => void;
  onOfferingCreated: (offering: AdminServiceCatalogOffering) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState(offering?.public_title ?? "");
  const [section, setSection] = useState(offering?.service_code ? `service:${offering.service_code}` : "");
  const [kind, setKind] = useState<ScenarioStarter>("simple");
  const [code, setCode] = useState(offering?.full_code ?? "");
  const [creatingOffering, setCreatingOffering] = useState(false);
  const [offeringDirty, setOfferingDirty] = useState(false);
  const [created, setCreated] = useState<AdminServiceCatalogOffering[]>([]);
  useEffect(() => { dialog.current?.showModal(); }, []);
  const category = catalog.categories.find(item => item.id === section);
  const serviceCode = category?.service_code ?? (section.startsWith("service:") ? section.slice(8) : "");
  const offerings = [...catalog.offerings, ...created.filter(item => !catalog.offerings.some(old => old.full_code === item.full_code))];
  const choices = offerings.filter(item => item.service_code === serviceCode && !!item.request_template_key && item.lifecycle_status !== "retired");
  const binding = choices.find(item => item.full_code === code);
  function close() { if (!offeringDirty || window.confirm("Закрыть без сохранения нового типа обращения?")) onClose(); }
  return <dialog ref={dialog} aria-labelledby="studio-create-title" className="studio-create-dialog" onCancel={event => { event.preventDefault(); close(); }}>
    <div className="studio-create-dialog__header"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Новая карта</p><h2 id="studio-create-title" className="mt-1 text-2xl font-semibold">С чего начнём?</h2><p className="mt-2 text-sm text-slate-500">Выберите основу. Вопросы и маршрут можно будет изменить прямо на карте.</p></div><Button variant="ghost" aria-label="Закрыть создание карты" onClick={close}>×</Button></div>
    <form onSubmit={event => {
      event.preventDefault();
      if (!title.trim() || !serviceCode || creatingOffering) return;
      const draft = createScenarioStarter(title, kind, serviceCode, category?.id ?? null);
      onCreate(binding ? { ...draft, offering_full_code: binding.full_code, publish_offering: binding.lifecycle_status === "draft", process_binding: { request_template_key: binding.request_template_key! } } : draft);
    }}>
      <div className="studio-create-dialog__body space-y-5">
        <label className="block text-sm font-semibold">Название карты<Input autoFocus required maxLength={300} placeholder="Например, Выдать доступ" value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label className="block text-sm font-semibold">Раздел каталога<Select required disabled={!!offering || creatingOffering} value={section} onChange={event => { setSection(event.target.value); setCode(""); }}><option value="">Выберите раздел</option>{catalog.services.filter(item => item.lifecycle_status !== "retired").map(item => <option key={item.code} value={`service:${item.code}`}>{item.public_title}</option>)}{catalog.categories.filter(item => item.lifecycle_status !== "archived").map(item => <option key={item.id} value={item.id}>{catalog.services.find(service => service.code === item.service_code)?.public_title} / {item.title}</option>)}</Select></label>
        <fieldset><legend className="mb-2 text-sm font-semibold">Способ начала работы</legend><div className="studio-starter-choices">{starterChoices.map(item => <label key={item.kind} className={`studio-starter-choice ${kind === item.kind ? "is-selected" : ""}`}><input type="radio" name="studio-starter" value={item.kind} checked={kind === item.kind} onChange={() => setKind(item.kind)} /><strong>{item.title}</strong><span>{item.description}</span></label>)}</div></fieldset>
        <p className="studio-next-help"><strong>Будет создано: </strong>{starterChoices.find(item => item.kind === kind)?.route}. Это редактируемый черновик.</p>
        {serviceCode && <details><summary className="cursor-pointer text-sm font-semibold">Тип обращения {binding ? `· ${binding.public_title}` : "· можно выбрать в результате"}</summary><div className="mt-3 space-y-3"><p className="text-sm text-slate-500">Определяет шаблон заявки и правила обработки. Для сохранения на сервере нужна эта привязка. Существующие типы используются повторно.</p><label className="block text-sm">Тип создаваемого обращения<Select aria-label="Тип создаваемого обращения" disabled={!!offering || creatingOffering} value={code} onChange={event => setCode(event.target.value)}><option value="">Настроить в блоке «Создать обращение»</option>{choices.map(item => <option key={item.full_code} value={item.full_code}>{item.public_title}</option>)}</Select></label>{!creatingOffering && <Button variant="outline" onClick={() => setCreatingOffering(true)}>Создать новый тип обращения</Button>}</div></details>}
      </div>
      <div className="studio-create-dialog__footer"><span className="text-xs text-slate-500">Черновик не виден сотрудникам</span><div className="flex gap-2"><Button variant="outline" onClick={close}>Отмена</Button><Button type="submit" disabled={!title.trim() || !serviceCode || creatingOffering}>Создать карту →</Button></div></div>
    </form>
    {creatingOffering && <div className="p-6"><ScenarioOfferingForm catalog={{ ...catalog, offerings }} initialServiceCode={serviceCode} onDirty={setOfferingDirty} onCancel={() => setCreatingOffering(false)} onDone={async saved => { setCreated(items => [...items, saved]); setCode(saved.full_code); onOfferingCreated(saved); setCreatingOffering(false); }} /></div>}
  </dialog>;
}

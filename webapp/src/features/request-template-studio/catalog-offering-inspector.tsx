import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fetchHelpdeskModelRegistry } from "../forms-builder/api";
import { saveOfferingDraft } from "../service-catalog/api";
import { fetchScenarioDetail, saveScenario, type ScenarioCatalog, type ScenarioItem } from "./scenario-api";
import type { CatalogService } from "./catalog-service-model";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { OfferingPublication } from "./offering-publication";

const noDirty = () => {};
const tabs = { basic: "Основное", help: "Помощь сотруднику", processing: "Обработка обращения", availability: "Доступность" };
type Tab = keyof typeof tabs;
export function CatalogOfferingInspector({row,data,canEdit,onOpen,onCreate,onClose,onBusy,onDirty=noDirty}: {row:CatalogService;data:ScenarioCatalog;canEdit:boolean;onOpen:(map:ScenarioItem,blockId?:string)=>void;onCreate:(offering:CatalogService["card"]["offering"])=>void;onClose:()=>void;onDirty?:(dirty:boolean)=>void;onBusy?:(busy:boolean)=>void}) {
  const offering = row.card.offering, entry = row.entry;
  const [tab,setTab] = useState<Tab>("basic"), [notice,setNotice] = useState("");
  const [value,setValue] = useState(()=>({title:entry?.title??row.title,description:entry?.description??row.description,category:entry ? entry.category_id??"" : row.categoryId??"",synonyms:(entry?.synonyms??row.synonyms).join("\n"),visibility:entry?.visibility??offering.visibility??"public",enabled:entry?.enabled??true,template:offering.request_template_key??"",requestType:offering.request_type??"incident",target:entry?.target_block_id??""}));
  const pristine = useRef(JSON.stringify(value));
  const dirty = JSON.stringify(value)!==pristine.current;
  const phrases=value.synonyms.split("\n").map(s=>s.trim()).filter(Boolean);
  const phrasesValid=phrases.length<=20&&phrases.every(phrase=>phrase.length<=100);
  useEffect(()=>{onDirty(dirty);return()=>onDirty(false);},[dirty,onDirty]);
  const cache=useQueryClient();
  const detail=useQuery({queryKey:["scenario-entry-settings",row.scenario?.id],queryFn:()=>fetchScenarioDetail(row.scenario!.id),enabled:!!entry&&!!row.scenario});
  const registry=useQuery({queryKey:["studio-catalog-model-registry"],queryFn:fetchHelpdeskModelRegistry,enabled:tab==="processing"});
  const mutation=useMutation({mutationFn:async()=>{
    if(entry){
      const current=detail.data;
      if(!current||!current.draft.definition.entry_points?.some(point=>point.key===entry.key))throw new Error("Entry unavailable");
      const definition:ScenarioDraftDefinition={...current.draft.definition,entry_points:current.draft.definition.entry_points.map(point=>point.key===entry.key?{...point,title:value.title.trim(),description:value.description.trim(),category_id:value.category||null,synonyms:phrases,visibility:value.visibility as "public"|"internal"|"restricted",enabled:value.enabled,target_block_id:value.target}:point)};
      await saveScenario(row.scenario!.id,definition,current.draft.revision);
    }else{
      await saveOfferingDraft({...offering,service_code:offering.service_code!,code:offering.code,public_title:value.title.trim(),short_description:value.description.trim(),request_template_key:value.template,request_type:value.requestType,visibility:value.visibility as "public"|"internal"|"restricted",metadata:{...offering.metadata,studio_catalog:{...offering.metadata?.studio_catalog,category_id:value.category||null,synonyms:phrases}}});
    }
  },onSuccess:async()=>{pristine.current=JSON.stringify(value);setNotice(entry?"Черновик пункта сохранён. Действующий вход изменится после публикации карты.":"Настройки услуги сохранены.");onDirty(false);await cache.invalidateQueries({queryKey:["scenario-catalog"]});await cache.invalidateQueries({queryKey:["scenario-entry-settings",row.scenario?.id]});},onError:()=>setNotice("")});
  useEffect(()=>{onBusy?.(mutation.isPending);return()=>onBusy?.(false);},[mutation.isPending,onBusy]);
  function guarded(action:()=>void){if(!dirty||window.confirm("Есть несохранённые настройки услуги. Продолжить без сохранения?"))action();}
  const maps=row.card.scenarios.filter(map=>!map.archived&&map.status!=="archived");
  return <section className="catalog-inspector-content">
    <header className="catalog-inspector-heading"><div><h2>{row.title}</h2><p>{row.available?"Доступна сотрудникам":"Недоступна сотрудникам"}</p></div><Button variant="ghost" size="sm" aria-label="Закрыть настройки услуги" onClick={()=>guarded(onClose)}>×</Button></header>
    {row.draft&&<p className="catalog-draft-note">Есть изменения черновика. Действующая версия сохраняется до публикации.</p>}
    {row.removedInDraft&&<div className="catalog-draft-note"><p>Пункт удалён из черновика карты, но остаётся в действующей версии.</p>{row.scenario&&<Button variant="outline" onClick={()=>onOpen(row.scenario!,entry?.target_block_id)}>Открыть карту</Button>}</div>}
    <div role="tablist" aria-label="Настройки выбранной услуги" className="catalog-inspector-tabs">{Object.entries(tabs).map(([key,label])=><button type="button" role="tab" aria-selected={tab===key} key={key} onClick={()=>setTab(key as Tab)}>{label}</button>)}</div>
    <form onSubmit={event=>{event.preventDefault();mutation.mutate();}} className="catalog-inspector-form">
      <fieldset disabled={!canEdit||mutation.isPending||row.removedInDraft} className="space-y-4">
        {tab==="basic"&&<>
          <label className="block">Раздел каталога<Input readOnly value={data.services.find(service=>service.code===offering.service_code)?.public_title??"Раздел недоступен"}/></label>
          <label className="block">Категория (необязательно)<Select value={value.category} onChange={event=>setValue({...value,category:event.target.value})}><option value="">{entry?"Категория карты":"В основном разделе"}</option>{data.categories.filter(item=>item.service_code===offering.service_code&&item.lifecycle_status!=="archived").map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
          <label className="block">Название услуги<Input required maxLength={300} value={value.title} onChange={event=>setValue({...value,title:event.target.value})}/></label>
          <p className="catalog-field-help">Так сотрудник видит услугу в каталоге.</p>
          <label className="block">Краткое описание<textarea className="field-base w-full" maxLength={2000} rows={3} value={value.description} onChange={event=>setValue({...value,description:event.target.value})}/></label>
          <label className="block">Слова для поиска<textarea className="field-base w-full" rows={3} value={value.synonyms} onChange={event=>setValue({...value,synonyms:event.target.value})}/></label><p className="catalog-field-help">Одна фраза на строку.</p>
        </>}
        {tab==="help"&&<>
          <h3 className="font-semibold">Действующий способ помощи</h3><p>{row.available?(row.mode==="scenario"?"Пошаговый сценарий":"Обычная форма"):"Услуга пока недоступна сотрудникам"}</p>
          <p className="catalog-field-help">Неопубликованная карта не заменяет действующую форму.</p>
          {offering.request_template_key&&<Link className="catalog-text-link" to={`/app/admin/forms?template=${encodeURIComponent(offering.request_template_key)}`}>Открыть обычную форму</Link>}
          {entry&&detail.data&&<label className="block">Точка входа<Select value={value.target} onChange={event=>setValue({...value,target:event.target.value})}>{detail.data.draft.definition.blocks?.map(block=><option key={block.id} value={block.id}>{block.title}</option>)}</Select></label>}
          {detail.isError&&entry&&<p role="alert">Не удалось загрузить вход. <Button variant="ghost" onClick={()=>void detail.refetch()}>Повторить</Button></p>}
          {maps.map(map=><div className="catalog-binding" key={map.id}><strong>{map.title}</strong><p>{map.published_version?`Опубликованная версия ${map.published_version}`:"Черновик · ещё не опубликован"}{map.issues?.length?" · есть ошибки черновика":""}</p><Button variant="outline" onClick={()=>guarded(()=>onOpen(map,entry?.target_block_id))}>Открыть карту</Button></div>)}
          {canEdit&&!maps.length&&offering.request_template_key&&<Button variant="outline" onClick={()=>guarded(()=>onCreate(offering))}>Создать карту</Button>}
          {!!maps.length&&<p className="catalog-field-help">Связь с общей картой сохраняется. Новые пункты можно добавить в эту же карту.</p>}
        </>}
        {tab==="processing"&&<>
          <h3 className="font-semibold">Каноническая обработка Helpdesk</h3><p className="catalog-field-help">Общий тип обращения может обслуживать несколько услуг и входов сценария.</p>
          <div className="catalog-binding"><span>Связанный тип обращения</span><strong>{offering.public_title}</strong></div>
          {entry?<><p>Шаблон и политики общие для всей карты.</p>{row.scenario&&<Button variant="outline" onClick={()=>guarded(()=>onOpen(row.scenario!,entry.target_block_id))}>Настроить обработку в карте</Button>}</>:<label className="block">Шаблон обработки<Select value={value.template} disabled={registry.isPending||registry.isError} onChange={event=>setValue({...value,template:event.target.value})}><option value={value.template}>{registry.data?.request_templates.find(item=>item.template_code===value.template)?.public_title??"Текущий шаблон"}</option>{registry.data?.request_templates.filter(item=>item.is_active&&item.published_at&&item.template_code!==value.template).map(item=><option key={item.template_code} value={item.template_code}>{item.public_title}</option>)}</Select></label>}
          {registry.isError&&<p role="alert">Шаблоны недоступны. <Button variant="ghost" onClick={()=>void registry.refetch()}>Повторить загрузку</Button></p>}
          <Link className="catalog-text-link" to={`/app/admin/forms?template=${encodeURIComponent(value.template)}`}>Открыть шаблон обработки</Link>
          <p className="catalog-field-help">Очередь, SLA, приоритет и согласование рассчитывает сервер по действующим политикам и собранным данным.</p>
          <Link className="catalog-text-link" to={`/app/admin/service-catalog/offerings/${encodeURIComponent(offering.full_code)}`}>Расширенные политики обработки</Link>
          <details><summary>Расширенные настройки</summary><label className="block">Класс обращения<Select disabled={!!entry} value={value.requestType} onChange={event=>setValue({...value,requestType:event.target.value})}>{["incident","service_request","request","access","consultation"].map((type,index)=><option key={type} value={type}>{["Инцидент","Запрос услуги","Общий запрос","Запрос доступа","Консультация"][index]}</option>)}</Select></label><p className="break-all text-xs">Идентификатор обработки: {offering.full_code}</p></details>
        </>}
        {tab==="availability"&&<>
          <div className="catalog-binding"><strong>{offering.lifecycle_status==="published"?"Тип обращения опубликован":offering.lifecycle_status==="retired"?"Тип обращения выведен из каталога":"Тип обращения в черновике"}</strong><p>{row.available?"Услуга доступна сотрудникам":"Сотрудники пока не видят услугу"}</p></div>
          <label className="block">Видимость услуги<Select value={value.visibility} onChange={event=>setValue({...value,visibility:event.target.value as typeof value.visibility})}><option value="public">Для сотрудников</option><option value="internal">Внутренняя</option><option value="restricted">Ограниченная</option></Select></label>
          {entry&&<label className="flex gap-2"><input type="checkbox" checked={value.enabled} onChange={event=>setValue({...value,enabled:event.target.checked})}/>Включить пункт после публикации карты</label>}
          {entry&&<p className="catalog-field-help">Изменения входа сохраняются в черновик. Для применения откройте карту и проверьте её публикацию.</p>}
          {!entry&&offering.lifecycle_status==="draft"&&!dirty&&canEdit&&<OfferingPublication code={offering.full_code}/>}
          {row.available&&<Link target="_blank" className="catalog-text-link" to={`/app/requester/new?${new URLSearchParams({offering:offering.full_code})}`}>Открыть в кабинете сотрудника</Link>}
          {!row.available&&<p className="catalog-field-help">Для доступности нужны опубликованные раздел и тип обращения, публичная видимость и действующая форма. Вход сценария требует публикации карты.</p>}
          {!!row.scenario?.issues?.length&&<details><summary>Ошибки черновика · {row.scenario.issues.length}</summary><ul className="mt-2 space-y-2">{row.scenario.issues.map((issue,index)=><li key={index}>{issue.message}</li>)}</ul></details>}
        </>}
      </fieldset>
      {!phrasesValid&&<p role="alert">Допускается до 20 поисковых фраз, каждая — до 100 символов.</p>}
      {notice&&<p role="status">{notice}</p>}
      {mutation.isError&&<p role="alert">Настройки не сохранены. Обновите серверную версию и повторите. Изменения остаются в полях.</p>}
      {canEdit&&<footer className="catalog-inspector-footer"><span>{mutation.isPending?"Сохранение…":dirty?"Есть изменения":"Изменений нет"}</span><Button type="submit" disabled={!dirty||mutation.isPending||!value.title.trim()||!!entry&&!detail.data||!phrasesValid||row.removedInDraft}>Сохранить</Button></footer>}
    </form>
  </section>;
}

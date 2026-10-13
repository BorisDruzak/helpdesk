import { Button } from "../../components/ui/button";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { ScenarioCatalog, ScenarioItem } from "./scenario-api";
import type { CatalogService } from "./catalog-service-model";

export function CatalogOfferingInspector({row,data,canEdit,onOpen,onCreate,onClose}:{row:CatalogService;data:ScenarioCatalog;canEdit:boolean;onOpen:(item:ScenarioItem,blockId?:string)=>void;onCreate:(item:AdminServiceCatalogOffering)=>void;onDirty:(dirty:boolean)=>void;onBusy?:(busy:boolean)=>void;onClose:()=>void}){
 const maps=row.card.scenarios.filter(item=>!item.archived),archived=row.card.scenarios.filter(item=>item.archived);
 const section=data.services.find(item=>item.code===row.card.offering.service_code);
 const category=data.categories.find(item=>item.id===row.categoryId);
 return <section className="catalog-inspector-content"><header className="catalog-inspector-heading"><div><h2>{row.title}</h2><p>{row.available?"Доступна сотрудникам":"Не опубликована для сотрудников"}</p></div><Button variant="ghost" size="sm" aria-label="Закрыть настройки услуги" onClick={onClose}>×</Button></header>
 <p>{row.description||"Описание не добавлено"}</p><dl className="space-y-3"><div><dt className="text-xs text-slate-500">Раздел каталога</dt><dd>{section?.public_title??"Раздел недоступен"}</dd></div><div><dt className="text-xs text-slate-500">Категория</dt><dd>{category?.title??"В основном разделе"}</dd></div></dl>
 {!!maps.length&&<div className="space-y-3">{maps.map(map=><section key={map.id} className="rounded border p-3 space-y-2"><h3 className="font-semibold">{map.title}</h3><p className="text-xs">{map.published_version_id?"Есть действующая версия":"Черновик"} · Входов: {map.entry_points?.length??0}</p><Button variant="outline" onClick={()=>onOpen(map,row.entry?.target_block_id)}>Открыть карту сценария</Button>{!!map.issues?.length&&<p className="text-xs text-amber-800">Карта требует проверки перед публикацией.</p>}</section>)}</div>}
 {!maps.length&&<div className="space-y-3"><p>Эта услуга ещё использует прежнюю форму. Её можно перенести в карту с сохранением вопросов и обработки.</p>{canEdit&&<Button onClick={()=>onCreate(row.card.offering)}>Перенести в сценарий</Button>}</div>}
 {!!archived.length&&<details><summary>Архив карт услуги</summary>{archived.map(map=><div key={map.id} className="space-y-2"><p>{map.title}</p><Button variant="outline" onClick={()=>onOpen(map)}>Открыть архивную карту</Button></div>)}</details>}
 <p className="text-xs text-slate-500">Вопросы, входы, название и обработка редактируются на карте услуги.</p>
 </section>;
}

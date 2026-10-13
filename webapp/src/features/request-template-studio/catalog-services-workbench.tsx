import { useCallback, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Folder, Layers, FileText, GitBranch, Plus, Search, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { EmptyState } from "../../components/ui-page/page-components";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import { fetchScenarioCatalog, type ScenarioCatalog, type ScenarioItem } from "./scenario-api";
import { fetchCatalogStructure } from "./catalog-structure-data";
import { catalogServices, catalogServiceLocation } from "./catalog-service-model";
import { CatalogOfferingInspector } from "./catalog-offering-inspector";
import { CatalogSectionForm } from "./catalog-section-form";
import { ScenarioCategoryForm } from "./scenario-category-form";
import { useCatalogGeometry } from "./catalog-geometry";
import "./catalog-services.css";
import { ScenarioConversionPanel } from "./scenario-conversion-panel";

export function categoryDescendants(data: ScenarioCatalog, id: string): Set<string> {
  const ids = new Set([id]);
  for(let changed=true;changed;){changed=false;for(const item of data.categories)if(item.parent_id&&ids.has(item.parent_id)&&!ids.has(item.id)){ids.add(item.id);changed=true;}}
  return ids;
}
type Props = {data:ScenarioCatalog;query:string;status:string;category:string|null;canEdit:boolean;
  onQuery:(value:string)=>void;onStatus:(value:string)=>void;onCategory:(id:string|null)=>void;
  onOpen:(item:ScenarioItem,blockId?:string)=>void;onCreateForOffering:(item:AdminServiceCatalogOffering)=>void;onEditCategory:(id:string)=>void;onPage:(offset:number)=>void;onNewMap?:()=>void;initialOffering?:string;onDirty?:(dirty:boolean)=>void};
type Editor={kind:"section";code?:string}|{kind:"category";id?:string;service?:string;parent?:string|null}|{kind:"create"};
const noDirty=()=>{};
export function ScenarioCatalogExplorer({data,query,status,category,canEdit,onQuery,onStatus,onCategory,onOpen,onCreateForOffering,onPage,onNewMap,initialOffering,onDirty=noDirty}:Props) {
  const [collapsed,setCollapsed]=useState<Set<string>>(new Set());
  const [selected,setSelected]=useState<string|null>(initialOffering??null),[editor,setEditor]=useState<Editor|null>(null),[dirty,setDirty]=useState(false),[sort,setSort]=useState("name");
  const [epoch,setEpoch]=useState(0),[busy,setBusy]=useState(false);
  const grid=useRef<HTMLDivElement>(null),geometry=useCatalogGeometry(grid),cache=useQueryClient();
  const rows=catalogServices(data);
  const needsStructure=!!query||status!=="all"||!!category||data.offset>0||data.total>data.limit;
  const structure=useQuery({queryKey:["scenario-catalog","structure"],queryFn:()=>fetchCatalogStructure(fetchScenarioCatalog),enabled:needsStructure});
  const treeData=needsStructure&&structure.data?structure.data:data;
  const treeRows=catalogServices(treeData);
  function selectService(key:string,fromTree=false){guarded(()=>{setSelected(key);setEditor(null);if(fromTree){const row=treeRows.find(item=>item.key===key);if(row){onQuery("");onStatus("all");onCategory(row.categoryId??`service:${row.card.offering.service_code}`);}}});}
  function leaves(parent:string|null,code:string){return treeRows.filter(row=>row.card.offering.service_code===code&&(row.categoryId??null)===parent).sort((a,b)=>a.title.localeCompare(b.title,"ru")).map(row=><li key={row.key}><button type="button" className={`catalog-tree-row catalog-tree-leaf ${selected===row.key?"is-selected":""}`} aria-label={`Услуга ${row.title} · ${row.mode==="scenario"?"Сценарий":"Ожидает переноса"}`} aria-pressed={selected===row.key} onClick={()=>selectService(row.key,true)}><GitBranch size={15}/><span>{row.title}<small>{row.mode==="scenario"?"Сценарий":"Ожидает переноса"}</small></span></button>{!!row.scenario?.entry_points?.length&&<ul className="ml-5 border-l pl-2">{row.scenario.entry_points.map(entry=><li key={entry.key}><button className="catalog-tree-row text-xs" onClick={()=>guarded(()=>onOpen(row.scenario!,entry.target_block_id))}>↳ {entry.title}</button></li>)}</ul>}</li>);}


  const serviceCode=category?.startsWith("service:")?category.slice(8):data.categories.find(item=>item.id===category)?.service_code;
  const selectedRow=rows.find(row=>row.key===selected)??treeRows.find(row=>row.key===selected)??(selected===initialOffering?rows.find(row=>row.card.offering.full_code===initialOffering&&row.title===row.card.offering.public_title):undefined);
  const folder=category&&!category.startsWith("service:")?data.categories.find(item=>item.id===category):null;
  const descendants=folder?categoryDescendants(data,folder.id):null;
  const visible=rows.filter(row=>(!serviceCode||row.card.offering.service_code===serviceCode)&&(!descendants||!!row.categoryId&&descendants.has(row.categoryId))&&(!query||[row.title,row.description,row.entry?.title??"",row.entry?.description??"",...row.synonyms,catalogServiceLocation(data,row),row.scenario?.title??"",row.card.offering.request_type??"",({incident:"Инцидент",request:"Общий запрос",service_request:"Запрос услуги",access:"Запрос доступа",consultation:"Консультация"} as Record<string,string>)[row.card.offering.request_type??""]??""].join(" ").toLocaleLowerCase().includes(query.toLocaleLowerCase()))&&
    (status==="all"||status==="form_only"&&row.mode==="form"&&row.available||status==="guided"&&row.mode==="scenario"&&row.available||status==="available"&&row.available||status==="hidden"&&!row.available||!["form_only","guided","available","hidden"].includes(status)))
    .sort((a,b)=>sort==="name"?a.title.localeCompare(b.title,"ru"):Date.parse(b.scenario?.updated_at??"1970-01-01")-Date.parse(a.scenario?.updated_at??"1970-01-01"));
  const markDirty=useCallback((next:boolean)=>{setDirty(next);onDirty(next);},[onDirty]);
  function guarded(action:()=>void){if(busy)return;if(!dirty){action();return;}if(window.confirm("Есть несохранённые настройки. Продолжить без сохранения?")){setEpoch(old=>old+1);markDirty(false);action();}}
  function toggle(id:string){setCollapsed(old=>{const next=new Set(old);if(next.has(id))next.delete(id);else next.add(id);return next;});}
  function edit(next:Editor){guarded(()=>{setEditor(next);setSelected(null);});}
  function tree(parent:string|null,code:string,ancestors=new Set<string>()):React.ReactNode {
    return treeData.categories.filter(item=>item.service_code===code&&item.parent_id===parent&&item.lifecycle_status!=="archived"&&!ancestors.has(item.id)).map(item=>{
      const children=treeData.categories.some(child=>child.parent_id===item.id&&child.lifecycle_status!=="archived")||treeRows.some(row=>row.categoryId===item.id&&row.card.offering.service_code===code);
      return <li key={item.id}><div className={`catalog-tree-row ${category===item.id?"is-selected":""}`}>
        {children?<button type="button" aria-label={`${collapsed.has(item.id)?"Развернуть":"Свернуть"} категорию ${item.title}`} aria-expanded={!collapsed.has(item.id)} onClick={()=>toggle(item.id)}>{collapsed.has(item.id)?<ChevronRight size={14}/>:<ChevronDown size={14}/>}</button>:<span className="w-4 shrink-0"/>}
        <button type="button" className="catalog-tree-title" aria-pressed={category===item.id} onClick={()=>guarded(()=>onCategory(item.id))}><Folder size={16}/><span>{item.title}</span></button>
        {canEdit&&<button type="button" aria-label={`Изменить категорию ${item.title}`} onClick={()=>edit({kind:"category",id:item.id})}>…</button>}
      </div>{!collapsed.has(item.id)&&<ul className="catalog-tree-children">{tree(item.id,code,new Set([...ancestors,item.id]))}{leaves(item.id,code)}</ul>}</li>;
    });
  }
  return <div className="catalog-services" aria-busy={busy}>
    {busy&&<p role="status" className="catalog-field-help">Сохранение настроек…</p>}
    <div className="catalog-toolbar"><div className="catalog-search"><Search size={18}/><Input aria-label="Поиск услуг" value={query} onChange={event=>guarded(()=>onQuery(event.target.value))} placeholder="Поиск по услугам, описаниям и словам для поиска"/></div><Select aria-label="Статус" value={status} onChange={event=>guarded(()=>onStatus(event.target.value))}><option value="all">Все состояния</option><option value="available">Доступны сотрудникам</option><option value="hidden">Недоступны сотрудникам</option><option value="draft">Есть черновик карты</option><option value="errors">Ошибки черновика карты</option><option value="archived">Есть архив карт</option></Select></div>
    <div ref={grid} className="catalog-services-grid" style={geometry.style}>
      <nav aria-label="Категории услуг" className="catalog-structure"><div className="catalog-panel-heading"><h2>Структура каталога</h2>{canEdit&&<Button variant="outline" size="sm" aria-label="Создать раздел" onClick={()=>edit({kind:"section"})}><Plus size={16}/></Button>}</div>
        <Button className="mb-3 w-full justify-start" variant={!category?"secondary":"ghost"} onClick={()=>guarded(()=>onCategory(null))}>Все услуги</Button>
        {data.services.map(section=><div key={section.code}><div className={`catalog-tree-row catalog-tree-section ${category===`service:${section.code}`?"is-selected":""}`}><button type="button" aria-label={`${collapsed.has(section.code)?"Развернуть":"Свернуть"} раздел ${section.public_title}`} aria-expanded={!collapsed.has(section.code)} onClick={()=>toggle(section.code)}>{collapsed.has(section.code)?<ChevronRight size={14}/>:<ChevronDown size={14}/>}</button><button type="button" className="catalog-tree-title" aria-label={`${section.public_title} · ${treeRows.filter(row=>row.card.offering.service_code===section.code).length}`} aria-pressed={category===`service:${section.code}`} onClick={()=>guarded(()=>onCategory(`service:${section.code}`))}><Layers size={17}/><span>{section.public_title}</span><small>{treeRows.filter(row=>row.card.offering.service_code===section.code).length}</small></button>{canEdit&&<button type="button" aria-label={`Изменить раздел ${section.public_title}`} onClick={()=>edit({kind:"section",code:section.code})}>…</button>}</div>{!collapsed.has(section.code)&&<ul className="catalog-tree-children">{tree(null,section.code)}{leaves(null,section.code)}</ul>}</div>)}
        {needsStructure&&structure.isPending&&<p role="status" className="catalog-field-help">Загрузка услуг дерева…</p>}
        {needsStructure&&structure.isError&&<p role="alert" className="catalog-field-help">Не удалось загрузить все услуги дерева. <Button variant="ghost" size="sm" onClick={()=>void structure.refetch()}>Повторить</Button></p>}
        {canEdit&&<Button className="mt-4 w-full" variant="outline" disabled={!data.services.length} onClick={()=>edit({kind:"category",service:serviceCode??data.services[0]?.code,parent:folder?.id??null})}>Создать категорию</Button>}
        <p className="catalog-structure-help">Категории группируют услуги. Услуга может находиться прямо в разделе.</p>
      </nav>
      {geometry.handle("left")}
      <section aria-label="Каталог услуг" className="catalog-list-panel"><div className="catalog-panel-heading"><div><p className="catalog-breadcrumb">{serviceCode?data.services.find(item=>item.code===serviceCode)?.public_title:"Все разделы"}{folder?` → ${folder.title}`:""}</p><h2>{`Услуги (${visible.length})`}</h2></div><Select aria-label="Сортировка услуг" value={sort} onChange={event=>setSort(event.target.value)}><option value="name">По названию</option><option value="updated">По изменению карты</option></Select></div>
        {!visible.length?<EmptyState title="Услуги не найдены" description={query||category||status!=="all"?"Измените поиск, раздел или состояние.":"Создайте первую услугу в каталоге."}/>:<ul className="catalog-service-list">{visible.map(row=><li key={row.key} data-offering-code={row.card.offering.full_code}><button type="button" className={`catalog-service-row ${selected===row.key?"is-selected":""}`} aria-label={`Настроить услугу ${row.title}`} aria-pressed={selected===row.key} onClick={()=>selectService(row.key)}><span className={`catalog-service-icon ${row.mode==="scenario"?"is-scenario":""}`}>{row.mode==="scenario"?<GitBranch size={23}/>:<FileText size={23}/>}</span><span className="catalog-service-copy"><strong>{row.title}</strong><span>{row.description||"Описание пока не добавлено"}</span><small>{catalogServiceLocation(data,row)}</small>{row.scenario?.updated_at&&<time dateTime={row.scenario.updated_at}>Изменение карты: {new Date(row.scenario.updated_at).toLocaleDateString("ru-RU")}</time>}</span><span className="catalog-service-meta"><span className={`catalog-chip ${row.mode==="scenario"?"is-scenario":""}`}>{row.mode==="scenario"?"Сценарий":"Ожидает переноса"}</span><span className={`catalog-chip ${row.available?"is-available":"is-muted"}`}>{row.available?"Доступна сотрудникам":"Недоступна сотрудникам"}</span>{row.draft&&<span className="catalog-draft-label">Изменения черновика</span>}{row.scenario?.issues?.length?<span className="catalog-draft-label">Ошибки черновика карты</span>:null}</span></button></li>)}</ul>}
        <footer className="catalog-pagination"><span>Типов обработки: {data.total}</span><Button size="sm" variant="ghost" disabled={!data.offset} onClick={()=>guarded(()=>onPage(Math.max(0,data.offset-data.limit)))}>Предыдущая страница</Button><Button size="sm" variant="ghost" disabled={data.offset+data.limit>=data.total} onClick={()=>guarded(()=>onPage(data.offset+data.limit))}>Следующая страница</Button></footer>
      </section>
      {geometry.handle("right")}
      <aside aria-label="Настройки услуги" className="catalog-inspector">
        {editor?.kind==="section"?<CatalogSectionForm offerings={data.offerings} onBusy={setBusy} sections={data.services} key={`${editor.code??"new-section"}:${epoch}`} section={data.services.find(item=>item.code===editor.code)} onClose={()=>{setEditor(null);markDirty(false);}} onDirty={markDirty}/>:editor?.kind==="category"?<ScenarioCategoryForm onBusy={setBusy} key={`${editor.id??"new-category"}:${epoch}`} catalog={data} category={data.categories.find(item=>item.id===editor.id)} initialServiceCode={editor.service} initialParentId={editor.parent} onDirty={markDirty} onCancel={()=>{setEditor(null);markDirty(false);}} onDone={async()=>{await cache.invalidateQueries({queryKey:["scenario-catalog"]});setEditor(null);markDirty(false);}}/>:selectedRow?<CatalogOfferingInspector onBusy={setBusy} key={`${selectedRow.key}:${epoch}`} row={selectedRow} data={data} canEdit={canEdit} onOpen={onOpen} onCreate={onCreateForOffering} onDirty={markDirty} onClose={()=>{setSelected(null);markDirty(false);}}/>:<div className="catalog-selection-empty"><Layers size={32}/><h2>Настройки услуги</h2><p>Выберите услугу в списке, чтобы настроить её название, помощь сотруднику и обработку.</p></div>}
      </aside>
    </div>
    <p className="catalog-principle"><strong>Раздел → категория → услуга.</strong> Категория необязательна. Каждая услуга создаётся на карте; пункты каталога — входы в её маршрут.</p>
    {canEdit&&<ScenarioConversionPanel/>}
    {canEdit&&<Button className="catalog-create-action" onClick={()=>guarded(()=>onNewMap?.())}><Plus size={18}/>Создать услугу</Button>}
  </div>;
}

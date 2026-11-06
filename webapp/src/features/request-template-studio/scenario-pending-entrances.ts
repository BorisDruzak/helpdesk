import type { ScenarioDraftDefinition } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";
import { catalogEntranceSourceId,createCatalogEntrance } from "./scenario-map-model";
type Point={x:number;y:number};
export const pendingCatalogEntrances=(d:ScenarioDraftDefinition)=>d.editor_layout?.pending_entrances??[];
export const catalogEntranceCount=(d:ScenarioDraftDefinition)=>(d.entry_points?.length??0)+pendingCatalogEntrances(d).length;
function valid(point:Point){if(![point.x,point.y].every(n=>Number.isFinite(n)&&Math.abs(n)<=100000))throw new Error("Выберите место на карте в пределах ±100000.");}
export function beginCatalogEntrance(d:ScenarioDraftDefinition,source:string,position:Point):ScenarioDraftDefinition{
 if(source!==catalogEntranceSourceId)throw new Error("Вход создаётся только от блока «Начало».");
 if(catalogEntranceCount(d)>=64)throw new Error("Достигнут лимит 64 входов.");valid(position);
 return {...d,editor_layout:{...d.editor_layout,pending_entrances:[...pendingCatalogEntrances(d),{key:newKey("entry"),title:"Новый вход",position}]}};
}
export function moveCatalogEntrance(d:ScenarioDraftDefinition,key:string,position:Point):ScenarioDraftDefinition{
 valid(position);return {...d,editor_layout:{...d.editor_layout,pending_entrances:pendingCatalogEntrances(d).map(e=>e.key===key?{...e,position}:e)}};
}
export function renameCatalogEntrance(d:ScenarioDraftDefinition,key:string,title:string):ScenarioDraftDefinition{
 const label=title.trim();if(!label||label.length>300)throw new Error("Укажите название входа до 300 символов.");
 return {...d,editor_layout:{...d.editor_layout,pending_entrances:pendingCatalogEntrances(d).map(e=>e.key===key?{...e,title:label}:e)}};
}
export function removeCatalogEntrance(d:ScenarioDraftDefinition,key:string):ScenarioDraftDefinition{
 return {...d,editor_layout:{...d.editor_layout,pending_entrances:pendingCatalogEntrances(d).filter(e=>e.key!==key)}};
}
export function completeCatalogEntrance(d:ScenarioDraftDefinition,key:string,target:string):ScenarioDraftDefinition{
 const entry=pendingCatalogEntrances(d).find(e=>e.key===key);if(!entry)throw new Error("Незавершённый вход не найден.");
 const next=createCatalogEntrance(removeCatalogEntrance(d,key),catalogEntranceSourceId,target,entry.title);
 return {...next,entry_points:next.entry_points.map((e,i)=>i===next.entry_points.length-1?{...e,key}:e)};
}

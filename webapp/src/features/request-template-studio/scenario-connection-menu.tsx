import { Button } from "../../components/ui/button";
import { mapPalette } from "./scenario-map-model";
import type { ScenarioBlock } from "./scenario-contract";
export type ConnectionDrop={point:{x:number;y:number}} & ({type:"source";source:string;handle:string|null}|{type:"entrance";key:string|null}|{type:"route";source:string;index:number});
export function ScenarioConnectionMenu({start,version4,inserting,position,onChoose,onClose}:{start:boolean;version4:boolean;inserting:boolean;position:{left:number;top:number};onChoose:(kind:ScenarioBlock["kind"]|"catalog_entrance")=>void;onClose:()=>void}){
 const choices=start?[{kind:"catalog_entrance" as const,label:"Вход из каталога"}]:[...mapPalette.filter(e=>!["sla_attachment","routing_attachment"].includes(e.kind)&&(!inserting||!["submit_ticket","resolution_check"].includes(e.kind))&&(version4||e.kind!=="navigation")),...(!inserting?[{kind:"finish" as const,label:"Завершить без обращения"}]:[])];
 return <div role="menu" aria-label="Добавить на конец связи" className="studio-map-context" style={position} onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();onClose();}}}><p className="px-3 text-xs text-slate-500">{start?"Начало → новый вход":"Соединить с новым блоком"}</p>{choices.map(e=><Button role="menuitem" key={e.kind} variant="ghost" onClick={()=>onChoose(e.kind)}>{e.label}</Button>)}<Button role="menuitem" variant="ghost" onClick={onClose}>Отмена</Button></div>;
}

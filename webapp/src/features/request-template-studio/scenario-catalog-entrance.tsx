import { useEffect,useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import { Button } from "../../components/ui/button";
import type { PendingCatalogEntrance, ScenarioBlock } from "./scenario-contract";
export function ScenarioCatalogEntrance({entry,disabled,onTitle,onRemove,blocks=[],onConnect}:{blocks?:ScenarioBlock[];onConnect?:(target:string)=>void;entry:PendingCatalogEntrance;disabled:boolean;onTitle:(title:string)=>void;onRemove:()=>void}){
 const [title,setTitle]=useState(entry.title);
 useEffect(()=>setTitle(entry.title),[entry.key,entry.title]);
 function commit(){if(disabled)return;const label=title.trim();if(label&&label.length<=300){setTitle(label);if(label!==entry.title)onTitle(label);}else setTitle(entry.title);}
 return <section className="space-y-3" aria-label="Незавершённый вход из каталога"><h3 className="font-semibold">Вход из каталога</h3><p>Потяните связь из правой точки к первому блоку. Если отпустить связь на пустом месте, можно добавить новый блок.</p><label className="block">Название входа<Input disabled={disabled} maxLength={300} value={title} onChange={e=>setTitle(e.target.value)} onBlur={commit} onKeyDown={e=>{e.stopPropagation();if(e.key==="Enter")e.currentTarget.blur();}}/></label>{onConnect && <details><summary className="cursor-pointer">Подключение с клавиатуры</summary><label className="block pt-2">Первый блок для сотрудника<Select disabled={disabled} value="" onChange={event=>{if(event.target.value&&!disabled)onConnect(event.target.value);}}><option value="">Выберите шаг на карте</option>{blocks.filter(block=>!isPolicyAttachment(block)).map(block=><option key={block.id} value={block.id}>{block.title}</option>)}</Select></label></details>}<p role="status">Вход сохранится в черновике. Для публикации подключите его к первому блоку.</p><Button variant="ghost" disabled={disabled} onClick={onRemove}>Удалить незавершённый вход</Button></section>;
}

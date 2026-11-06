import { useEffect,useState } from "react";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import type { PendingCatalogEntrance } from "./scenario-contract";
export function ScenarioCatalogEntrance({entry,disabled,onTitle,onRemove}:{entry:PendingCatalogEntrance;disabled:boolean;onTitle:(title:string)=>void;onRemove:()=>void}){
 const [title,setTitle]=useState(entry.title);
 useEffect(()=>setTitle(entry.title),[entry.key,entry.title]);
 function commit(){if(disabled)return;const label=title.trim();if(label&&label.length<=300){setTitle(label);if(label!==entry.title)onTitle(label);}else setTitle(entry.title);}
 return <section className="space-y-3" aria-label="Незавершённый вход из каталога"><h3 className="font-semibold">Вход из каталога</h3><p>Подключён к «Началу». Потяните связь из правой точки к первому блоку. Если отпустить связь на пустом месте, можно добавить новый блок.</p><label className="block">Название входа<Input disabled={disabled} maxLength={300} value={title} onChange={e=>setTitle(e.target.value)} onBlur={commit} onKeyDown={e=>{e.stopPropagation();if(e.key==="Enter")e.currentTarget.blur();}}/></label><p role="status">Вход сохранится в черновике. Для публикации подключите его к первому блоку.</p><Button variant="ghost" disabled={disabled} onClick={onRemove}>Удалить незавершённый вход</Button></section>;
}

import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { reconnectStart } from "./scenario-map-model";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import { Input } from "../../components/ui/input";
import { ScenarioSeparatedInput } from "./scenario-separated-input";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioEntryPoint } from "./scenario-contract";

export function ScenarioEntryInspector({definition,blockId,disabled,onChange,entryKey}:{definition:ScenarioDraftDefinition;blockId:string;catalog:ScenarioCatalog;disabled:boolean;onChange:(next:ScenarioDraftDefinition)=>void;entryKey?:string}){
 const entries=definition.entry_points??[];
 const update=(key:string,patch:Partial<ScenarioEntryPoint>)=>onChange({...definition,entry_points:entries.map(entry=>entry.key===key?{...entry,...patch}:entry)});
 return <section className="space-y-4" aria-label="Точки входа выбранного блока">{entries.filter(entry=>entry.target_block_id===blockId&&(!entryKey||entry.key===entryKey)).map(entry=><fieldset key={entry.key} disabled={disabled} className="space-y-3">
  <label className="block">Название входа<Input maxLength={300} value={entry.title} onChange={event=>update(entry.key,{title:event.target.value})}/></label>
  <p className="text-sm text-slate-500">Открывает первый шаг маршрута. Обычные переходы не могут вести в этот вход.</p>
  <details><summary>Подключение с клавиатуры</summary><p className="text-xs text-slate-500">На карте перетащите правую точку входа к нужному блоку.</p><label className="block">Первый блок для сотрудника<Select value={entry.target_block_id} onChange={event=>onChange(reconnectStart(definition,entry.key,event.target.value))}>{(definition.blocks??[]).filter(block=>!isPolicyAttachment(block)).map(block=><option key={block.id} value={block.id}>{block.title}</option>)}</Select></label></details>
  <label className="block">Краткое описание<textarea className="field-base w-full" maxLength={2000} value={entry.description??""} onChange={event=>update(entry.key,{description:event.target.value})}/></label>
  <details><summary>Поиск в каталоге</summary><p className="text-sm text-slate-500">Добавьте знакомые сотрудникам формулировки, по одной на строку: «не печатает», «не могу распечатать», «ошибка печати». Выражения попадут в каталог после публикации карты.</p><ScenarioSeparatedInput label="Дополнительные поисковые выражения" values={entry.synonyms??[]} separator={"\n"} limit={20} onChange={synonyms=>update(entry.key,{synonyms})} disabled={disabled}/></details>
  <details><summary>Доступность пункта</summary><label className="flex gap-2"><input type="checkbox" checked={entry.enabled!==false} onChange={event=>update(entry.key,{enabled:event.target.checked})}/>Показывать сотрудникам</label><p className="text-xs text-slate-500">Общая доступность зависит от публикации услуги и категории.</p></details>
  <Button variant="ghost" onClick={()=>{const remaining=entries.filter(old=>old.key!==entry.key);onChange({...definition,entry_points:remaining,entry_block_id:remaining[0]?.target_block_id??null});}}>Убрать вход из черновика</Button>
 </fieldset>)}</section>;
}

import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

type Props={definition:ScenarioDraftDefinition;catalog:ScenarioCatalog;disabled:boolean;existing:boolean;onChange:(value:ScenarioDraftDefinition)=>void;focusBinding?:boolean;onCategoryDirty?:(dirty:boolean)=>void;onCategoryOpen?:(open:boolean)=>void;onCategoryCreated?:()=>Promise<void>};
export function ScenarioPurpose({definition,catalog,disabled,existing,onChange}:Props){
 const categories=catalog.categories.filter(item=>item.service_code===definition.service_code&&item.lifecycle_status!=="archived");
 return <fieldset disabled={disabled} className="space-y-4 min-w-0"><legend className="text-lg font-semibold">Услуга</legend>
  <label className="block">Название услуги<Input maxLength={300} value={definition.title} onChange={event=>onChange({...definition,title:event.target.value})}/></label>
  <label className="block">Раздел каталога<Select disabled={existing||!!definition.offering_full_code} value={definition.service_code} onChange={event=>onChange({...definition,service_code:event.target.value,category_id:null})}><option value="">Выберите раздел</option>{catalog.services.filter(item=>item.lifecycle_status!=="retired").map(item=><option key={item.code} value={item.code}>{item.public_title}</option>)}</Select></label>
  <label className="block">Категория (необязательно)<Select disabled={!definition.service_code} value={definition.category_id??""} onChange={event=>{const category_id=event.target.value||null;onChange({...definition,category_id,entry_points:definition.entry_points?.map(entry=>({...entry,category_id:entry.category_id===definition.category_id||!entry.category_id?category_id:entry.category_id}))});}}><option value="">В основном разделе</option>{categories.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
  <details><summary>Описание услуги</summary><textarea aria-label="Описание услуги" className="field-base w-full min-h-24" maxLength={2000} value={definition.description??""} onChange={event=>onChange({...definition,description:event.target.value})}/></details>
  <p className="text-sm text-slate-500">Соедините «Начало» с первым шагом. Название на этой линии — пункт, который сотрудник увидит в каталоге.</p>
 </fieldset>;
}

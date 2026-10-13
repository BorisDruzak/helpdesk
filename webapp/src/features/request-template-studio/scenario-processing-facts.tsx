import { Select } from "../../components/ui/select";
import type { ScenarioProcessingFacts, ScenarioField } from "./scenario-contract";

const dimensions = {
 impact:{label:"Масштаб воздействия",values:{single_user:"Один пользователь",multiple_users:"Несколько пользователей",department:"Целое подразделение"}},
 urgency:{label:"Срочность",values:{can_work:"Можно продолжать работу",degraded:"Работа затруднена",blocked:"Работа остановлена"}},
 importance:{label:"Важность процесса",values:{normal:"Обычный процесс",important:"Важный процесс",critical:"Критичный процесс"}},
};
export function ProcessingFactsEditor({value={},disabled,onChange}:{value?:ScenarioProcessingFacts|null;disabled:boolean;onChange:(value:ScenarioProcessingFacts)=>void}){
 return <fieldset disabled={disabled} className="space-y-3">{(Object.keys(dimensions) as (keyof ScenarioProcessingFacts)[]).map(key=><label key={key} className="block text-sm">{dimensions[key].label}<Select value={value?.[key]??""} onChange={event=>onChange({...value,[key]:event.target.value||null})}><option value="">Не изменять</option>{Object.entries(dimensions[key].values).map(([code,label])=><option key={code} value={code}>{label}</option>)}</Select></label>)}<p className="text-xs text-slate-500">Значения передаются действующим правилам обработки. Приоритет и сроки рассчитывает сервер.</p></fieldset>;
}
export function QuestionProcessingEffects({field,disabled,onChange}:{field:ScenarioField;disabled:boolean;onChange:(field:ScenarioField)=>void}){
 const choices=field.type==="checkbox"?[{value:true,label:"Да"},{value:false,label:"Нет"}]:field.options??[];
 if(!choices.length)return null;
 return <details><summary>Влияние ответов на обработку</summary><div className="space-y-3 mt-3">{choices.map(option=>{
  const effects=field.process_mapping?.effects??[],old=effects.find(item=>item.value===option.value);
  return <section key={String(option.value)} className="rounded border p-3"><h4 className="font-semibold">{option.label}</h4><ProcessingFactsEditor value={old?.facts} disabled={disabled} onChange={facts=>onChange({...field,process_mapping:{...field.process_mapping,effects:[...effects.filter(item=>item.value!==option.value),{value:option.value,facts}]}})}/></section>;
 })}</div></details>;
}

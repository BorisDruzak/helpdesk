import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fixedValue,inputLabel,validControls,validateInputs } from "./tool-inputs";
import { reasonText,type ToolItem } from "./types";
export function ToolForm({tool,canRun,pending,onRun}:{tool:ToolItem;canRun:boolean;pending:boolean;onRun:(inputs:Record<string,string|number>)=>void}) {
  const [inputs,setInputs]=useState<Record<string,string|number>>(()=>Object.fromEntries(tool.input_controls.filter(c=>c.value_type==="integer"&&c.minimum!=null).map(c=>[c.name,c.minimum!])));
  const [error,setError]=useState<string|null>(null);
  const supported=validControls(tool.input_controls);
  return <form className="endpoint-tools-form flex min-w-0 flex-col gap-4" onSubmit={event=>{event.preventDefault();const invalid=validateInputs(tool.input_controls,inputs);setError(invalid);if(!invalid&&canRun&&supported&&tool.availability==="available"&&!pending) onRun({...inputs});}}>
    <div><h3 className="font-semibold">{tool.title}</h3><p className="break-words text-xs text-slate-500">{tool.module_key} · {tool.version}</p></div>
    {tool.availability!=="available"&&<p role="status" className="text-sm text-amber-900">{reasonText(tool.reason_code)}</p>}
    {supported?tool.input_controls.map(control=><label className="block space-y-1" key={control.name}><span className="text-sm font-medium">{inputLabel(control.name)}</span>{control.enum_values?<Select value={String(inputs[control.name]??"")} onChange={e=>setInputs({...inputs,[control.name]:e.target.value})}><option value="">Выберите…</option>{control.enum_values.map(v=><option key={v} value={v}>{fixedValue(v)}</option>)}</Select>:<Input required type={control.value_type==="integer"?"number":"text"} step={control.value_type==="integer"?1:undefined} min={control.minimum??undefined} max={control.maximum??undefined} maxLength={253} value={inputs[control.name]??""} onChange={e=>setInputs({...inputs,[control.name]:control.value_type==="integer"&&e.target.value!==""?Number(e.target.value):e.target.value})}/>}<span className="block text-xs text-slate-500">{control.name}{control.minimum!=null||control.maximum!=null?` · От ${control.minimum??"—"} до ${control.maximum??"—"}`:""}</span></label>):<p role="alert">Формат параметров не поддерживается</p>}
    {tool.fixed_settings.length>0&&<div className="rounded-lg bg-surface-subtle p-3 text-sm"><p className="mb-2 font-medium">Фиксированные настройки</p>{tool.fixed_settings.map((s,i)=><p className="break-words" key={`${s.step_id}:${s.parameter}:${i}`}>{inputLabel(s.parameter)}: {fixedValue(s.value)}</p>)}</div>}
    {error&&<p role="alert" className="text-sm text-rose-700">{error}</p>}
    <Button type="submit" className="endpoint-tools-run w-full" disabled={!canRun||!supported||tool.availability!=="available"||pending}>{pending?"Отправляем…":"Запустить проверку"}</Button>
  </form>;
}

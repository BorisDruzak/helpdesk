import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { AdminServiceCatalogOffering, CatalogVisibility } from "../service-catalog/api";

/** Live catalogue availability is independent of the draft and its published version. */
export function ScenarioCatalogVisibility({id,offering,disabled,onSaved,onRefresh}:{id:string;offering:AdminServiceCatalogOffering;disabled:boolean;onSaved?:()=>void;onRefresh?:()=>void}){
 const [saved,setSaved]=useState(offering.visibility),[value,setValue]=useState(offering.visibility);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 const sequence=useRef(0),flight=useRef(false);
 useEffect(()=>{sequence.current++;flight.current=false;setSaved(offering.visibility);setValue(offering.visibility);setBusy(false);setError("");setMessage("");return()=>{sequence.current++;};},[id,offering.full_code,offering.visibility]);
 async function apply(){
  if(disabled||flight.current||saved===value)return;
  const current=++sequence.current;flight.current=true;setBusy(true);setError("");setMessage("");
  try{
   const response=await fetch(`/api/web/admin/request-studio/scenarios/${encodeURIComponent(id)}/catalog-visibility`,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({visibility:value,expected_visibility:saved})});
   const payload=await response.json();if(current!==sequence.current)return;
   if(!response.ok||payload.status!=="success")throw new Error(response.status===409?"conflict":"save");
   const updated=payload.data?.offering?.visibility;
   if(!["public","internal","restricted"].includes(updated))throw new Error("save");
   setSaved(updated);setValue(updated);setMessage("Видимость изменена. Черновик и опубликованная версия сохранены.");onSaved?.();
  }catch(cause){if(current===sequence.current)setError(cause instanceof Error&&cause.message==="conflict"?"Видимость изменил другой администратор. Обновите каталог и проверьте текущее значение перед повторением.":"Не удалось подтвердить изменение видимости. Обновите каталог и проверьте результат.");}
  finally{onRefresh?.();if(current===sequence.current){flight.current=false;setBusy(false);}}
 }
 return <section aria-label="Видимость услуги в каталоге" className="min-w-0 space-y-3 rounded-xl border p-4" aria-busy={busy}>
  <h3 className="font-semibold">Видимость услуги в каталоге</h3>
  <p className="text-sm text-slate-600">Меняется отдельно от публикации карты. Ограничения раздела, категории и доступа продолжают действовать.</p>
  <label className="block">Видимость услуги<Select aria-label="Видимость услуги" value={value} disabled={disabled||busy} onChange={event=>{setValue(event.target.value as CatalogVisibility);setMessage("");setError("");}}><option value="public">Показывать сотрудникам</option><option value="internal">Скрыть из каталога сотрудников</option><option value="restricted">Ограниченный доступ</option></Select></label>
  {offering.lifecycle_status!=="published"&&<p className="text-sm">Услуга ещё не опубликована. Этот выбор сам по себе её не публикует.</p>}
  <Button variant="outline" disabled={disabled||busy||value===saved} onClick={()=>void apply()}>{busy?"Сохраняем видимость…":"Применить видимость"}</Button>
  {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
 </section>;
}

import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Button as RequesterButton } from "../requester/ui/form-controls";
import { ScenarioStepContent, type ScenarioStepDisplay } from "../requester/scenario-step-content";
import type { DynamicFormValues } from "../requester/dynamic-form";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
export function ScenarioRequesterPreview({ definition, block }: { definition:ScenarioDraftDefinition; block?:ScenarioBlock }) {
 const [values,setValues]=useState<DynamicFormValues>({}),[acknowledged,setAcknowledged]=useState(false);
 if(!block) return <p>Выберите блок на карте, чтобы увидеть его оформление для сотрудника.</p>;
 const projected:ScenarioStepDisplay={id:block.id,kind:block.kind,title:block.title};
 if(block.kind==="form_page"){projected.layout=block.layout;projected.fields=block.fields.map(({visible_when: _visible,required_when: _required,...field})=>field);}
 if(block.kind==="instruction"){projected.content={body:block.content.body,format:block.content.format??"plain"};projected.acknowledgment_required=block.acknowledgment_required;}
 if(block.kind==="finish")projected.message=block.message;

 if(block.kind==="review") projected.answers=definition.blocks?.flatMap(item=>item.kind==="form_page"?item.fields.map(field=>({key:field.key,label:field.label,type:field.type,value:null,display_value:"Ответ сотрудника"})):[]);
 return <section className="grid min-w-0 gap-4 rounded-panel border border-slate-200 bg-white p-5" aria-label="Блок глазами сотрудника">
  <h2 className="text-xl font-semibold text-slate-950">{block.title}</h2>
  <div className="grid min-w-0 gap-4"><ScenarioStepContent block={projected} values={values} acknowledged={acknowledged} onAcknowledged={setAcknowledged} onValue={(key,value)=>setValues(old=>({...old,[key]:value}))} /></div>
  {block.kind==="decision" && <p>Условие автоматически выбирает следующий шаг. Отдельный экран сотруднику не показывается.</p>}
  {block.kind==="diagnostic" && <p>Здесь отображается состояние проверки. В предпросмотре диагностика не запускается.</p>}
  <div className="grid gap-3 border-t border-slate-200 py-3" aria-label="Действия шага в предпросмотре">
   {block.kind==="resolution_check" && <div className="flex flex-wrap gap-2">{["Да, решено","Нет, нужна помощь","Не знаю"].map(label=><RequesterButton key={label} disabled>{label}</RequesterButton>)}</div>}
   {["form_page","instruction","review"].includes(block.kind) && <RequesterButton disabled>Продолжить</RequesterButton>}
   {block.kind==="finish" && <RequesterButton disabled>Завершить</RequesterButton>}
   {block.kind==="submit_ticket" && <RequesterButton disabled>Проверить обработку</RequesterButton>}
  </div>
  {block.kind==="form_page"&&block.fields.some(field=>field.visible_when||field.required_when)&&<p className="text-xs text-slate-500">Для проверки оформления показаны все вопросы. Условия видимости и обязательности проверяются сервером в «Тестировать».</p>}
 </section>;
}
export function ScenarioPagePreview({ definition, block, offeringTitle, onClose }: {definition:ScenarioDraftDefinition;block?:ScenarioBlock;offeringTitle:string;onClose:()=>void}) {
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const element=dialog.current;if(element&&!element.open)element.showModal();return()=>{if(element?.open)element.close();};},[]);
 return <dialog ref={dialog} className="studio-requester-page-preview" aria-label="Предпросмотр полной страницы" onCancel={onClose} onClose={onClose} onKeyDown={event=>event.stopPropagation()}>
  <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b bg-white p-4"><h2 className="font-semibold">Предпросмотр страницы сотрудника</h2><Button autoFocus onClick={onClose}>Вернуться к карте</Button></div>
  <main className="mx-auto grid w-full max-w-4xl gap-5 p-4 md:p-8"><div><p className="text-sm text-slate-500">Помощь → {offeringTitle||"Услуга не выбрана"}</p><h1 className="mt-2 text-2xl font-semibold">{offeringTitle||definition.title}</h1>{definition.description&&<p className="mt-2">{definition.description}</p>}</div>
   <p className="text-sm text-slate-500">Предпросмотр черновика. Ответы не сохраняются, обращение не создаётся.</p>
   <ScenarioRequesterPreview key={block?.id??"empty"} definition={definition} block={block}/>
  </main>
 </dialog>;
}

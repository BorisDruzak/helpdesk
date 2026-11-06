import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { createCatalogEntrance, reconnectStart } from "./scenario-map-model";
import { ScenarioCatalogEntrance } from "./scenario-catalog-entrance";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const draft:ScenarioDraftDefinition={schema_version:3,scenario_key:"old",title:"Услуга",service_code:"it",offering_full_code:"it.test",process_binding:{request_template_key:"test"},entry_block_id:"q",entry_points:[{key:"old",title:"Старый вход",target_block_id:"q"}],blocks:[{id:"q",kind:"instruction",title:"Вопрос",content:{body:"Текст"}},{id:"end",kind:"finish",title:"Другая часть"}]};
it("preserves a legacy implicit main entrance when another named entrance changes destination",()=>{
 const d={...draft,entry_points:[{key:"other",title:"Другой вход",target_block_id:"end"}]};
 const independent={...d,blocks:[...d.blocks!,{id:"third",kind:"instruction" as const,title:"Третий шаг",content:{body:"Текст"}}]};
 expect(reconnectStart(independent,"other","third").entry_block_id).toBe("q");
 expect(reconnectStart(independent,"other","third").blocks).toEqual(independent.blocks);
});
it("creates independent named entrances only from Start without modifying old blocks, schema or main entry",()=>{
 const before=structuredClone(draft);
 const a=createCatalogEntrance(draft,"studio:metadata","end","Вход А");
 const b=createCatalogEntrance(a,"studio:metadata","end","Вход Б");
 expect(draft).toEqual(before);expect(b.blocks).toEqual(before.blocks);expect(b.schema_version).toBe(3);expect(b.entry_block_id).toBe("q");
 expect(b.entry_points).toHaveLength(3);expect(b.entry_points?.[0]).toEqual(before.entry_points?.[0]);
 expect(new Set(b.entry_points?.map(e=>e.key)).size).toBe(3);expect(b.entry_points?.slice(1).map(e=>e.title)).toEqual(["Вход А","Вход Б"]);
 expect(()=>createCatalogEntrance(draft,"q","end","Нельзя")).toThrow(/Начало/);
 expect(()=>createCatalogEntrance(draft,"studio:metadata","missing","Нельзя")).toThrow();
 expect(()=>createCatalogEntrance({...draft,schema_version:4,blocks:[...draft.blocks!,{id:"policy",kind:"sla_attachment",title:"SLA"}]},"studio:metadata","policy","Нельзя")).toThrow();
 expect(()=>createCatalogEntrance({...draft,entry_points:Array.from({length:64},(_,i)=>({key:`e${i}`,title:"Вход",target_block_id:"q"}))},"studio:metadata","end","Лимит")).toThrow(/64/);
});
it("requires an explicit destination and makes its Start connection clear before creation",()=>{
 const create=vi.fn(),close=vi.fn();render(<ScenarioCatalogEntrance definition={draft} disabled={false} onCreate={create} onClose={close}/>);
 expect(screen.getByText(/Всегда подключён к блоку «Начало»/)).toBeVisible();
 const button=screen.getByRole("button",{name:"Создать вход от «Начала»"});expect(button).toBeDisabled();
 fireEvent.change(screen.getByLabelText("Первый блок для сотрудника"),{target:{value:"end"}});
 fireEvent.change(screen.getByLabelText("Название входа"),{target:{value:"Мой вход"}});fireEvent.click(button);
 expect(create).toHaveBeenCalledWith("end","Мой вход");
});
it("explains empty maps and prevents read-only entrance creation",()=>{
 const create=vi.fn();const view=render(<ScenarioCatalogEntrance definition={{...draft,blocks:[]}} disabled={false} onCreate={create} onClose={vi.fn()}/>);
 expect(screen.getByText(/Сначала добавьте вопрос или инструкцию/)).toBeVisible();expect(screen.getByRole("button",{name:"Создать вход от «Начала»"})).toBeDisabled();
 view.rerender(<ScenarioCatalogEntrance definition={draft} disabled onCreate={create} onClose={vi.fn()}/>);
 expect(screen.getByLabelText("Первый блок для сотрудника")).toBeDisabled();expect(create).not.toHaveBeenCalled();
});

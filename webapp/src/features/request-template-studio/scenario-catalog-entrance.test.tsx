import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
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
it("explains visual completion and renames without any target-selection form",()=>{
 const title=vi.fn(),remove=vi.fn();const entry={key:"draft",title:"Новый вход",position:{x:0,y:0}};
 render(<ScenarioCatalogEntrance entry={entry} disabled={false} onTitle={title} onRemove={remove}/>);
 expect(screen.getByText(/Потяните связь из правой точки/)).toBeVisible();expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Название входа"),{target:{value:"Второй вход"}});fireEvent.blur(screen.getByLabelText("Название входа"));expect(title).toHaveBeenCalledWith("Второй вход");
 fireEvent.click(screen.getByRole("button",{name:"Удалить незавершённый вход"}));expect(remove).toHaveBeenCalledOnce();
});
it("prevents edits on a read-only pending entrance",()=>{
 render(<ScenarioCatalogEntrance entry={{key:"draft",title:"Новый вход",position:{x:0,y:0}}} disabled onTitle={vi.fn()} onRemove={vi.fn()}/>);
 expect(screen.getByLabelText("Название входа")).toBeDisabled();expect(screen.getByRole("button",{name:"Удалить незавершённый вход"})).toBeDisabled();
});
it("allows natural multiword typing and replacement before committing the pending title",async()=>{
 const commit=vi.fn();function Harness(){const [entry,setEntry]=useState({key:"draft",title:"Новый вход",position:{x:0,y:0}});return <ScenarioCatalogEntrance entry={entry} disabled={false} onTitle={title=>{commit(title);setEntry({...entry,title:title.trim()});}} onRemove={vi.fn()}/>;}
 render(<Harness/>);const input=screen.getByLabelText("Название входа") as HTMLInputElement;
 fireEvent.change(input,{target:{value:""}});for(const letter of "Вход в отдел поддержки")fireEvent.change(input,{target:{value:input.value+letter}});expect(input).toHaveValue("Вход в отдел поддержки");fireEvent.blur(input);expect(commit).toHaveBeenLastCalledWith("Вход в отдел поддержки");
});

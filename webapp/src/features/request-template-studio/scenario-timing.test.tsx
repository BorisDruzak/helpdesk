import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPolicyAttachmentEditor } from "./scenario-policy-attachments";
import { addMapBlock, mapPalette } from "./scenario-map-model";
import { summarizeTerminalOla } from "./scenario-ola-model";
import { connectPolicyAttachment } from "./scenario-policy-attachments-model";

const draft = (): ScenarioDraftDefinition => ({ schema_version:4, execution_semantics:3, scenario_key:"timing", service_code:"it", offering_full_code:"it.test", title:"Услуга", process_binding:{request_template_key:"it"}, entry_block_id:"first", blocks:[{id:"first",kind:"instruction",title:"Инструкция",content:{body:"Текст"},transitions:[{to:"end"}]},{id:"end",kind:"submit_ticket",title:"Обращение"},{id:"timing",kind:"sla_attachment",title:"Сроки обработки",attached_to:"first"}], processing:{defaults:{route:"",sla_profile:""},routes:{},sla_profiles:{normal:{title:"Обычные сроки",first_response_minutes:60,resolution_minutes:480,time_basis:"calendar"}}} });

it("offers one Russian deadline block and preserves legacy programmatic blocks",()=>{
 expect(mapPalette.filter(item=>["sla_attachment","ola_attachment"].includes(item.kind))).toEqual([{kind:"sla_attachment",label:"Сроки обработки"}]);
 expect(addMapBlock(draft(),"sla_attachment",{x:111,y:222}).blocks!.at(-1)?.title).toBe("Сроки обработки");
 expect(addMapBlock(draft(),"ola_attachment",{x:111,y:222}).blocks!.at(-1)?.kind).toBe("ola_attachment");
});

it("edits both deadline sections without overwriting the other",()=>{
 let latest=draft();
 function Editor(){const [value,setValue]=useState(latest);return <ScenarioPolicyAttachmentEditor block={value.blocks![2]} definition={value} disabled={false} onChange={next=>{latest=next;setValue(next);}}/>;}
 render(<Editor/>);
 expect(screen.getByRole("heading",{name:"Сроки для сотрудника"})).toBeVisible();
 fireEvent.change(screen.getByLabelText("Профиль сроков для сотрудника"),{target:{value:"normal"}});
 fireEvent.change(screen.getByLabelText("Способ задания внутренних сроков"),{target:{value:"targets"}});
 fireEvent.change(screen.getByLabelText("Назначение исполнителя, мин."),{target:{value:"7"}});
 fireEvent.change(screen.getByLabelText("Обработка группой, мин."),{target:{value:"43"}});
 const settings=latest.blocks![2] as Extract<NonNullable<ScenarioDraftDefinition['blocks']>[number],{kind:"sla_attachment"}>;
 expect(settings.sla_profile).toBe("normal");
 expect((settings as unknown as {ola_targets:unknown}).ola_targets).toEqual({ack_minutes:7,processing_minutes:43});
 expect(summarizeTerminalOla(latest,"end").alternatives[0].targets).toEqual({ack_minutes:7,processing_minutes:43});
 fireEvent.change(screen.getByLabelText("Способ задания внутренних сроков"),{target:{value:"inherit"}});
 expect((latest.blocks![2] as {sla_profile?:string}).sla_profile).toBe("normal");
 expect(latest.blocks![2]).not.toHaveProperty("ola_targets");
});

it("rejects conflicting combined and legacy internal assignments",()=>{
 const definition=draft();definition.blocks![2]={...definition.blocks![2],ola_targets:{ack_minutes:7,processing_minutes:43}} as never;
 definition.blocks!.push({id:"old",kind:"ola_attachment",title:"Прежние сроки",targets:{ack_minutes:10,processing_minutes:60}});
 expect(()=>connectPolicyAttachment(definition,"old","first")).toThrow(/уже есть внутренние сроки/);
});

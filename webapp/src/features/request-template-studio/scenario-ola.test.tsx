import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { addMapBlock, mapPalette } from "./scenario-map-model";
import { connectPolicyAttachment, isPolicyAttachment } from "./scenario-policy-attachments-model";
import { ScenarioOlaEditor, ScenarioTerminalOla, summarizeTerminalOla } from "./scenario-ola";
import type { ScenarioSimulation } from "./scenario-api";

vi.mock("./scenario-policy-attachments", () => ({ usePublishedScenarioPolicies: () => ({policies:{ola:[{code:"ola_rule",title:"Правило группы",is_active:true,published_at:"2026-11-10"}]},error:false,retry:vi.fn()}) }));
const draft = (): ScenarioDraftDefinition => ({ schema_version:4, execution_semantics:3, scenario_key:"s", service_code:"it", offering_full_code:"it.test", title:"Услуга", process_binding:{request_template_key:"it"}, entry_block_id:"first", blocks:[{id:"first",kind:"instruction",title:"Инструкция",content:{body:"Текст"},transitions:[{to:"end"}]},{id:"end",kind:"submit_ticket",title:"Обращение"}] });

describe("OLA attachment", () => {
 it("is available in the palette, adds at the viewport and connects without creating transitions", () => {
  expect(mapPalette.some(item=>item.kind==="ola_attachment")).toBe(true);
  const created=addMapBlock(draft(),"ola_attachment",{x:222,y:333}); const block=created.blocks!.at(-1)!;
  expect(isPolicyAttachment(block)).toBe(true);
  const connected=connectPolicyAttachment(created,block.id,"first");
  expect(connected.blocks![0].transitions).toEqual([{to:"end"}]);
  expect(connected.editor_layout?.positions?.[block.id]).toEqual({x:222,y:333});
  expect(()=>connectPolicyAttachment({...connected,blocks:[...connected.blocks!,{id:"another",kind:"ola_attachment",title:"Другой OLA",attached_to:"first"}]},block.id,"first")).toThrow(/OLA/);
 });
 it("edits visible durations directly and switches atomically to a published rule", () => {
  const onChange=vi.fn();render(<ScenarioOlaEditor value={{targets:{ack_minutes:10,processing_minutes:60}}} disabled={false} onChange={onChange}/>);
  fireEvent.change(screen.getByLabelText("Подтверждение, мин."),{target:{value:"5"}});
  expect(onChange).toHaveBeenLastCalledWith({targets:{ack_minutes:5,processing_minutes:60}});
  fireEvent.change(screen.getByLabelText("Способ задания OLA"),{target:{value:"policy"}});
  expect(onChange).toHaveBeenLastCalledWith({});
 });
 it("summarizes last visited OLA and terminal override, retaining independent branch alternatives", () => {
  const d=draft();d.blocks!.push({id:"ola",kind:"ola_attachment",title:"OLA группы",attached_to:"first",targets:{ack_minutes:10,processing_minutes:60}});
  expect(summarizeTerminalOla(d,"end").alternatives[0].targets).toEqual({ack_minutes:10,processing_minutes:60});
  d.blocks![1]={...d.blocks![1],ola_targets:{ack_minutes:5,processing_minutes:30}} as never;
  expect(summarizeTerminalOla(d,"end").alternatives[0].targets?.ack_minutes).toBe(5);
  expect(summarizeTerminalOla(d,"end",true).alternatives[0].targets?.ack_minutes).toBe(10);
 });
 it("labels disabled OLA as configured targets rather than verified timers", () => {
  const d=draft();const block=d.blocks![1];
  const result={current_block:block,state:{current_block_id:"end",history:["first"]},processing:{sla:{},routing:{},ola:{enabled:false,ack_min:7,processing_min:43}}} as unknown as ScenarioSimulation;
  render(<ScenarioTerminalOla definition={d} block={block} disabled={false} onChange={vi.fn()} result={result}/>);
  expect(screen.getByRole("alert")).toHaveTextContent("OLA отключён на сервере");
  expect(screen.queryByText("Проверенный OLA этого пути")).not.toBeInTheDocument();
 });
});

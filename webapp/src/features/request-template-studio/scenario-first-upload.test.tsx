import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioAuthorAttachmentProvider, ScenarioAuthorAttachments } from "./scenario-author-attachments";
import { useScenarioEditor } from "./use-scenario-editor";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { uploadScenarioAttachment } from "./scenario-api";
vi.mock("./scenario-api",async original=>({...await original<object>(),uploadScenarioAttachment:vi.fn()}));
afterEach(()=>{vi.unstubAllGlobals();vi.clearAllMocks();});
const asset=(asset_id:string)=>({asset_id,name:`${asset_id}.png`,mime_type:"image/png",size_bytes:1,url:`/api/web/request-scenario-assets/${asset_id}/download`});
it.each([false,true])("keeps generated bindings and copied material identities during an immediate first upload (copy=%s)",async copied=>{
 const base={schema_version:4,execution_semantics:3,scenario_key:"first-upload",title:"Upload",service_code:"it",offering_full_code:"",process_binding:{request_template_key:""},entry_block_id:"q",blocks:[{id:"q",kind:"form_page",title:"Q",fields:[{key:"f",type:"text",label:"F",help_attachments:copied?[asset("old-copy")]:[]}],transitions:[]}]} as ScenarioDraftDefinition;
 let editor!:ReturnType<typeof useScenarioEditor>,uploaded!:()=>void;const arrived=new Promise<void>(resolve=>{uploaded=resolve;});
 vi.mocked(uploadScenarioAttachment).mockImplementation(async()=>{uploaded();return asset("new-upload");});
 vi.stubGlobal("fetch",vi.fn(async(_url:unknown,init?:RequestInit)=>{
  const submitted=JSON.parse(String(init?.body)).definition;const saved={...submitted,offering_full_code:"it.created",publish_offering:true,process_binding:{request_template_key:"print"},blocks:submitted.blocks.map((block:ScenarioBlock)=>block.kind==="form_page"?{...block,fields:block.fields.map(field=>({...field,help_attachments:copied?[asset("rebound-copy")]:[]}))}:block)};
  return new Response(JSON.stringify({status:"success",data:{scenario:{id:"created"},draft:{revision:1,definition:saved},...(copied?{asset_rebindings:{"old-copy":asset("rebound-copy")}}:{})}}),{headers:{"content-type":"application/json"}});
 }));
 function Parent(){editor=useScenarioEditor(false);const field=editor.definition?.blocks?.find(block=>block.kind==="form_page")?.fields[0];return editor.definition&&<ScenarioAuthorAttachmentProvider id={editor.detail?.scenario.id} definition={editor.definition} getDefinition={editor.getDefinition} ensureSaved={editor.ensureSaved} onChange={editor.change}><ScenarioAuthorAttachments blockId="q" fieldKey="f" attachments={field?.help_attachments}/></ScenarioAuthorAttachmentProvider>;}
 render(<QueryClientProvider client={new QueryClient()}><Parent/></QueryClientProvider>);act(()=>editor.create(base,false));
 await act(async()=>{
  fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"),{target:{files:[new File(["a"],"new.png",{type:"image/png"})]}});
  await arrived;await Promise.resolve();await Promise.resolve();
 });
 expect(editor.definition?.offering_full_code).toBe("it.created");expect(editor.definition?.process_binding.request_template_key).toBe("print");
 const field=editor.definition?.blocks?.find(block=>block.kind==="form_page")?.fields[0];
 expect(field?.help_attachments?.map(item=>item.asset_id)).toEqual([...(copied?["rebound-copy"]:[]),"new-upload"]);
 expect(uploadScenarioAttachment).toHaveBeenCalledExactlyOnceWith("created",expect.any(File),"q","f",expect.any(AbortSignal));
});

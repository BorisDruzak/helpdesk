import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useScenarioEditor } from "./use-scenario-editor";
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
function setup(autosave=true,mapFirst=false){
 const client=new QueryClient({defaultOptions:{mutations:{retry:false},queries:{retry:false}}});
 function Wrapper({children}:{children:ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>;}
 return renderHook(()=>useScenarioEditor(autosave,mapFirst),{wrapper:Wrapper});
}
function reply(definition:unknown,revision=1){return new Response(JSON.stringify({status:"success",data:{scenario:{id:"new-draft"},draft:{revision,definition}}}),{headers:{"content-type":"application/json"}});}
it("autosaves a newly authored service without a manual first save",async()=>{
 vi.useFakeTimers();
 const fetcher=vi.fn(async(_url:unknown,init?:RequestInit)=>reply({...JSON.parse(String(init?.body)).definition,offering_full_code:"it.created",publish_offering:true,process_binding:{request_template_key:"request"}}));vi.stubGlobal("fetch",fetcher);
 const hook=setup();act(()=>hook.result.current.create());
 act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Новая проверка",service_code:"it"}));
 await act(async()=>{await vi.advanceTimersByTimeAsync(1199);});expect(fetcher).not.toHaveBeenCalled();
 await act(async()=>{await vi.advanceTimersByTimeAsync(1);});
 expect(fetcher).toHaveBeenCalledTimes(1);expect(String(fetcher.mock.calls[0][0])).toContain("/services");
 expect(hook.result.current.detail?.scenario.id).toBe("new-draft");expect(hook.result.current.dirty).toBe(false);
});
it("does not create a pristine initial canvas merely by opening Studio",async()=>{
 vi.useFakeTimers();const fetcher=vi.fn();vi.stubGlobal("fetch",fetcher);setup(true,true);
 await act(async()=>{await vi.advanceTimersByTimeAsync(5000);});expect(fetcher).not.toHaveBeenCalled();
});
it("joins on-demand save with an in-flight first save then flushes newer edits",async()=>{
 const pending:((response:Response)=>void)[]=[];
 const fetcher=vi.fn((_url:unknown,_init?:RequestInit)=>new Promise<Response>(resolve=>pending.push(resolve)));vi.stubGlobal("fetch",fetcher);
 const hook=setup(false);act(()=>hook.result.current.create());act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Первый",service_code:"it"}));
 let first!:Promise<unknown>,ready!:Promise<unknown>;act(()=>{first=hook.result.current.save.mutateAsync();});
 await act(async()=>{await Promise.resolve();});
 act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Новая правка"}));
 act(()=>{ready=hook.result.current.ensureSaved();});expect(fetcher).toHaveBeenCalledTimes(1);
 const firstDefinition=JSON.parse(String(fetcher.mock.calls[0][1]?.body)).definition;
 await act(async()=>{pending[0](reply({...firstDefinition,offering_full_code:"it.created",process_binding:{request_template_key:"request"}},1));await first;});
 expect(fetcher).toHaveBeenCalledTimes(2);expect(fetcher.mock.calls.map(call=>call[1]?.method)).toEqual(["POST","PUT"]);
 expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toMatchObject({revision:1,definition:{title:"Новая правка",offering_full_code:"it.created"}});
 await act(async()=>{pending[1](reply(JSON.parse(String(fetcher.mock.calls[1][1]?.body)).definition,2));await ready;});
 expect(hook.result.current.detail?.draft.revision).toBe(2);expect(hook.result.current.dirty).toBe(false);
});
it("rejects identity preparation after switching to another draft",async()=>{
 let resolve!:(response:Response)=>void;vi.stubGlobal("fetch",vi.fn(()=>new Promise<Response>(done=>{resolve=done;})));
 const hook=setup(false);act(()=>hook.result.current.create());act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Old",service_code:"it"}));
 let ready!:Promise<unknown>;act(()=>{ready=hook.result.current.ensureSaved();});const outcome=ready.catch(error=>error);
 await act(async()=>{await Promise.resolve();});const old=hook.result.current.definition;
 act(()=>hook.result.current.create());await act(async()=>{resolve(reply(old));await outcome;});
 expect(await outcome).toBeInstanceOf(Error);expect(hook.result.current.detail).toBeNull();
});
it("does not duplicate first creation when manual save and identity preparation overlap",async()=>{
 let resolve!:(response:Response)=>void;const fetcher=vi.fn(()=>new Promise<Response>(done=>{resolve=done;}));vi.stubGlobal("fetch",fetcher);
 const hook=setup(false);act(()=>hook.result.current.create());act(()=>hook.result.current.change({...hook.result.current.definition!,title:"New",service_code:"it"}));
 let first!:Promise<unknown>,second!:Promise<unknown>;act(()=>{first=hook.result.current.save.mutateAsync();second=hook.result.current.ensureSaved();});
 await act(async()=>{await Promise.resolve();});expect(fetcher).toHaveBeenCalledTimes(1);
 await act(async()=>{resolve(reply({...hook.result.current.definition!,offering_full_code:"it.created",process_binding:{request_template_key:"request"}}));await Promise.all([first,second]);});
 expect(fetcher).toHaveBeenCalledTimes(1);expect(hook.result.current.dirty).toBe(false);
});
it("ignores a late refused save from another draft while a new save is pending",async()=>{
 const pending:((response:Response)=>void)[]=[];vi.stubGlobal("fetch",vi.fn(()=>new Promise<Response>(done=>pending.push(done))));
 const hook=setup(false);act(()=>hook.result.current.create());act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Old",service_code:"it"}));
 let old!:Promise<unknown>,current!:Promise<unknown>;act(()=>{old=hook.result.current.save.mutateAsync().catch(error=>error);});await act(async()=>{await Promise.resolve();});
 act(()=>hook.result.current.create());act(()=>hook.result.current.change({...hook.result.current.definition!,title:"Current",service_code:"it"}));
 act(()=>{current=hook.result.current.save.mutateAsync();});await act(async()=>{await Promise.resolve();});
 await act(async()=>{pending[0](new Response(JSON.stringify({status:"error",error_code:"FORBIDDEN"}),{status:403,headers:{"content-type":"application/json"}}));await old;});
 expect(hook.result.current.error).toBe("");expect(hook.result.current.accessError).toBeNull();
 await act(async()=>{pending[1](reply({...hook.result.current.definition!,offering_full_code:"it.created",process_binding:{request_template_key:"request"}}));await current;});
 expect(hook.result.current.definition?.title).toBe("Current");expect(hook.result.current.error).toBe("");
});

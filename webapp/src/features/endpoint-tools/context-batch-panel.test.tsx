import { QueryClient,QueryClientProvider } from "@tanstack/react-query";
import { fireEvent,render,screen,waitFor } from "@testing-library/react";
import { afterEach,expect,it,vi } from "vitest";
import { ContextBatchPanel } from "./context-batch-panel";
import { EndpointToolResult } from "./tool-result";
import type { ToolBatch,ToolRun } from "./types";
vi.mock("../auth/session-provider",()=>({useSession:()=>({status:"authenticated",session:{user_login:"operator"}})}));
const run=(profile:string,index:number):ToolRun=>({schema_version:"endpoint_tool_run_v1",run_id:`run${index}`,ticket_id:"ticket",device_ref:"device",kind:index===5?"diagnostic":"context_collection",module_key:null,version:null,profile:index===5?null:profile,inputs:{},status:index===2?"failed":"succeeded",remote_ref:`remote${index}`,safe_result:null,error_code:index===2?"network_failed":null,created_at:"2026-10-12T10:00:00Z",batch_id:"batch"});
afterEach(()=>vi.restoreAllMocks());
it("hides cached batch results after ticket access is revoked",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"error",error:"Доступ закрыт"}),{status:403,headers:{"content-type":"application/json"}})));
  const batch:ToolBatch={schema_version:"endpoint_tool_batch_v1",batch_id:"batch",ticket_id:"ticket",status:"running",runs:["baseline_v1","health_v1","network_v1","inventory_v1","session_v1","diagnostic_v1"].map(run)};
  const query=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={query}><ContextBatchPanel ticketId="ticket" deviceRef="device" canRun initialBatch={batch}/></QueryClientProvider>);
  await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent(/Доступ/));
  expect(screen.queryAllByRole("button",{name:/Выбрать результат/})).toHaveLength(0);
});
it("shows six steps and partial outcome without reusing old snapshots",()=>{
  const batch:ToolBatch={schema_version:"endpoint_tool_batch_v1",batch_id:"batch",ticket_id:"ticket",status:"partial",runs:["baseline_v1","health_v1","network_v1","inventory_v1","session_v1","diagnostic_v1"].map(run)};
  const query=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={query}><ContextBatchPanel ticketId="ticket" deviceRef="device" canRun initialBatch={batch}/></QueryClientProvider>);
  expect(screen.getByText("Частичный результат")).toBeInTheDocument();
  expect(screen.getAllByRole("button",{name:/Выбрать результат/})).toHaveLength(6);
  fireEvent.click(screen.getByRole("button",{name:/Выбрать результат: Сеть/}));
  expect(screen.getByText(/Сохранённый результат отсутствует/)).toBeInTheDocument();
});
it("attaches the selected completed result while pending results stay disabled",()=>{
  const attach=vi.fn();const completed:ToolRun={...run("diagnostic_v1",5),kind:"diagnostic",status:"failed",safe_result:{profile:"diagnostic_v1",reason:"Диагностика по обращению",collected_at:"2026-10-12T10:00:00Z",warnings:[],processes:[],log_excerpt:null}};
  const view=render(<EndpointToolResult run={completed} onAttach={attach}/>);
  fireEvent.click(screen.getByRole("button",{name:"Приложить к паспорту"}));
  expect(attach).toHaveBeenCalledExactlyOnceWith("run5",0);
  view.rerender(<EndpointToolResult run={completed} onAttach={attach} attachedSteps={[0]}/>);
  expect(screen.getByRole("button",{name:"В паспорте"})).toBeDisabled();
  view.rerender(<EndpointToolResult run={{...completed,status:"queued",safe_result:null}} onAttach={attach}/>);
  expect(screen.getByRole("button",{name:"Приложить к паспорту"})).toBeDisabled();
});

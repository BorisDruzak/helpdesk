import { QueryClient,QueryClientProvider } from "@tanstack/react-query";
import { fireEvent,render,screen,waitFor } from "@testing-library/react";
import { afterEach,expect,it,vi } from "vitest";
vi.mock("../auth/session-provider",()=>({useSession:()=>({status:"authenticated",session:{user_login:"operator",actor_role:"support",permissions:["ticket.tool.run"]}})}));
const item={module_key:"helpdesk.dns",version:"1.0.0",title:"Проверка DNS",availability:"available",reason_code:null,
  input_controls:[{name:"target",value_type:"string",minimum:null,maximum:null,enum_values:null}],
  fixed_settings:[{step_id:"dns",parameter:"family",value:"ipv4"}],capabilities:["dns.resolve"]};
function response(data:unknown){return new Response(JSON.stringify({status:"success",data}),{headers:{"content-type":"application/json"}});}
afterEach(()=>{vi.restoreAllMocks();sessionStorage.clear();});
it("renders literal settings and does not enable an unavailable published tool",async()=>{
  const module=await import("./endpoint-tools-panel").catch(()=>null);
  expect(module).not.toBeNull();
  vi.stubGlobal("fetch",vi.fn(async(input)=>String(input).endsWith("/runs")?response({schema_version:"endpoint_tool_run_history_v1",items:[]}):response({schema_version:"endpoint_tool_catalog_v1",ticket_id:"ticket",device_ref:"device",enabled:true,can_run:true,observed_at:"2026-10-12T10:00:00Z",items:[item,{...item,module_key:"helpdesk.ping",title:"Проверка связи",availability:"unknown",reason_code:"agent_facts_missing"}],next_cursor:null,profiles:[]})));
  const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const Panel=module!.EndpointToolsPanel;
  render(<QueryClientProvider client={query}><Panel ticketId="ticket"/></QueryClientProvider>);
  fireEvent.change(await screen.findByRole("combobox",{name:"Инструмент Endpoint"}),{target:{value:"helpdesk.dns:1.0.0"}});
  expect(await screen.findByText(/IPv4/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox",{name:"Инструмент Endpoint"}),{target:{value:"helpdesk.ping:1.0.0"}});
  expect(screen.getByRole("button",{name:"Запустить проверку"})).toBeDisabled();
});

it("keeps selected run B when an older response for A arrives",async()=>{
  const {EndpointToolsPanel}=await import("./endpoint-tools-panel");
  const now="2026-10-12T10:00:00Z";
  const run=(id:string,target:string)=>({schema_version:"endpoint_tool_run_v1",run_id:id,ticket_id:"ticket",device_ref:"device",kind:"module",module_key:id==="A"?"helpdesk.dns.a":"helpdesk.dns.b",version:"1.0.0",profile:null,inputs:{target},status:"succeeded",remote_ref:id,error_code:null,created_at:now,batch_id:null,
    safe_result:{schema_version:"endpoint_module_operation_v1",operation_id:id,device_id:"device",module_key:item.module_key,version:"1.0.0",status:"succeeded",created_at:now,deadline_at:now,expected_step_count:1,steps:[{sequence:0,capability:"dns.resolve",status:"succeeded",safe_result:{schema_version:"dns_resolve_result_v1",target,status:"succeeded",collected_at:now,addresses:[],address_count:0}}]}});
  let resolveA!:(value:Response)=>void;
  const fetcher=vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input);
    if(url.endsWith("/runs/A")) return new Promise<Response>(resolve=>{resolveA=resolve;});
    if(url.endsWith("/runs/B")) return response(run("B","b.example.test"));
    if(url.endsWith("/runs")) return response({schema_version:"endpoint_tool_run_history_v1",items:[run("A","a.example.test"),run("B","b.example.test")]});
    return response({schema_version:"endpoint_tool_catalog_v1",ticket_id:"ticket",device_ref:"device",enabled:true,can_run:true,observed_at:now,items:[item],next_cursor:null,profiles:[]});
  });
  vi.stubGlobal("fetch",fetcher);
  const query=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={query}><EndpointToolsPanel ticketId="ticket"/></QueryClientProvider>);
  fireEvent.click(await screen.findByText("История запусков"));
  fireEvent.click(await screen.findByRole("button",{name:/helpdesk.dns.a/}));
  await waitFor(()=>expect(resolveA).toBeDefined());
  fireEvent.click(screen.getByRole("button",{name:/helpdesk.dns.b/}));
  await screen.findByText("b.example.test");
  resolveA(response(run("A","a.example.test")));
  await waitFor(()=>expect(screen.queryByText("a.example.test")).not.toBeInTheDocument());
  expect(screen.getByText("b.example.test")).toBeInTheDocument();
});

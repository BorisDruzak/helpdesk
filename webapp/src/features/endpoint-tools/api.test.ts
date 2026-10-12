import { afterEach,expect,it,vi } from "vitest";
import { pendingToolKey,createRun,getRun,createBatch } from "./api";
afterEach(()=>{vi.restoreAllMocks();sessionStorage.clear();});
it("prevents dispatch when a replay identity cannot be saved",()=>{
  vi.spyOn(Storage.prototype,"setItem").mockImplementation(()=>{throw new Error("blocked");});
  expect(()=>pendingToolKey("operator","ticket","device",["dns","1.0.0",{target:"example.test"}])).toThrow(/безопасного повтора/);
});
it("does not read a foreign run into the selected query",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{schema_version:"endpoint_tool_run_v1",run_id:"other",ticket_id:"ticket"}}),{status:200,headers:{"content-type":"application/json"}})));
  await expect(getRun("ticket","selected")).rejects.toThrow();
});
it("rejects a created context batch owned by another ticket",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{schema_version:"endpoint_tool_batch_v1",batch_id:"batch",ticket_id:"other",runs:[]}}),{status:200,headers:{"content-type":"application/json"}})));
  await expect(createBatch("ticket","request-key","device")).rejects.toThrow();
});

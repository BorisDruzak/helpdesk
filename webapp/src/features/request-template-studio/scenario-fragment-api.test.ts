import { afterEach, expect, it, vi } from "vitest";
import { insertSavedScenarioFragment } from "./scenario-fragment-api";
afterEach(() => vi.unstubAllGlobals());
it("sends revisions, position and explicit mappings to the encoded fragment insertion endpoint", async () => {
 const fetcher = vi.fn().mockResolvedValue({ ok: true, headers: new Headers({"content-type":"application/json"}), json: async () => ({status:"success",data:{inserted_block_ids:["new"]}}) });
 vi.stubGlobal("fetch", fetcher);
 await insertSavedScenarioFragment("scenario/a", "fragment/b", 2, 3, {x:4,y:5}, {blocks:{old_target:"end"},fields:{old:"new"},routes:{},sla_profiles:{},policy_refs:{},sla_policy_refs:{shared:"selected-sla"},ola_policy_refs:{},routing_policy_refs:{shared:"selected-routing"},calendars:{},facts:{}});
 expect(fetcher.mock.calls[0][0]).toBe("/api/web/admin/request-studio/scenarios/scenario%2Fa/fragments/fragment%2Fb/insert");
 expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({revision:2,fragment_revision:3,position:{x:4,y:5},mappings:{blocks:{old_target:"end"},fields:{old:"new"},routes:{},sla_profiles:{},policy_refs:{},sla_policy_refs:{shared:"selected-sla"},ola_policy_refs:{},routing_policy_refs:{shared:"selected-routing"},calendars:{},facts:{}}});
});

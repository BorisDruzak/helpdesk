import {afterEach,expect,it,vi} from "vitest";
import {loadPanelPreferences,savePanelPreferences} from "./workspace-panel-preferences";
afterEach(()=>{vi.restoreAllMocks();localStorage.clear();});
it("reads old preferences with an unpinned navigation and isolates a saved pin",()=>{
  localStorage.setItem('pc-client:workspace-panels:v1:["A","support"]',JSON.stringify({schema_version:1,navigationCollapsed:false,ticketListCollapsed:true}));
  expect(loadPanelPreferences("A","support").navigationPinned).toBe(false);
  savePanelPreferences("A","support",{navigationCollapsed:false,ticketListCollapsed:true,navigationPinned:true});
  expect(loadPanelPreferences("A","support").navigationPinned).toBe(true);
  expect(loadPanelPreferences("B","support").navigationPinned).toBe(false);
  expect(loadPanelPreferences("A","admin").navigationPinned).toBe(false);
});
it("keeps navigation and ticket list independent and isolates accounts",()=>{
  savePanelPreferences("A","support",{navigationCollapsed:true,ticketListCollapsed:false});
  expect(loadPanelPreferences("A","support")).toEqual({navigationCollapsed:true,ticketListCollapsed:false,navigationPinned:false});
  savePanelPreferences("A","support",{...loadPanelPreferences("A","support"),ticketListCollapsed:true});
  expect(loadPanelPreferences("A","support")).toEqual({navigationCollapsed:true,ticketListCollapsed:true,navigationPinned:false});
  expect(loadPanelPreferences("B","support")).toEqual({navigationCollapsed:false,ticketListCollapsed:false,navigationPinned:false});
  expect(loadPanelPreferences("A","admin")).toEqual({navigationCollapsed:false,ticketListCollapsed:false,navigationPinned:false});
});
it("storage failure keeps navigation usable",()=>{
  vi.spyOn(Storage.prototype,"getItem").mockImplementation(()=>{throw new Error("blocked");});
  vi.spyOn(Storage.prototype,"setItem").mockImplementation(()=>{throw new Error("blocked");});
  expect(()=>loadPanelPreferences("A","support")).not.toThrow();
  expect(savePanelPreferences("A","support",{navigationCollapsed:true,ticketListCollapsed:false})).toBe(false);
});

import {afterEach,expect,it,vi} from "vitest";
import {loadPanelPreferences,savePanelPreferences} from "./workspace-panel-preferences";
afterEach(()=>{vi.restoreAllMocks();localStorage.clear();});
it("keeps navigation and ticket list independent and isolates accounts",()=>{
  savePanelPreferences("A","support",{navigationCollapsed:true,ticketListCollapsed:false});
  expect(loadPanelPreferences("A","support")).toEqual({navigationCollapsed:true,ticketListCollapsed:false});
  savePanelPreferences("A","support",{...loadPanelPreferences("A","support"),ticketListCollapsed:true});
  expect(loadPanelPreferences("A","support")).toEqual({navigationCollapsed:true,ticketListCollapsed:true});
  expect(loadPanelPreferences("B","support")).toEqual({navigationCollapsed:false,ticketListCollapsed:false});
  expect(loadPanelPreferences("A","admin")).toEqual({navigationCollapsed:false,ticketListCollapsed:false});
});
it("storage failure keeps navigation usable",()=>{
  vi.spyOn(Storage.prototype,"getItem").mockImplementation(()=>{throw new Error("blocked");});
  vi.spyOn(Storage.prototype,"setItem").mockImplementation(()=>{throw new Error("blocked");});
  expect(()=>loadPanelPreferences("A","support")).not.toThrow();
  expect(savePanelPreferences("A","support",{navigationCollapsed:true,ticketListCollapsed:false})).toBe(false);
});

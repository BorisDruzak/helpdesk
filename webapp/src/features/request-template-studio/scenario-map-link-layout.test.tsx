import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { entranceLayoutKey, routeLayoutKey, useMapLinkLayout } from "./scenario-map-link-layout";
beforeEach(() => localStorage.clear());
it("keeps button/automatic route positions attached to their identity after reorder", () => {
 const a={to:"a",button:{key:"open-a",label:"A"}},b={to:"b",when:{op:"eq" as const,source:"answer" as const,field:"f",value:"b"}};
 const first=routeLayoutKey("q",a),second=routeLayoutKey("q",b);
 expect(routeLayoutKey("q",{...a,button:{...a.button,label:"New title"}})).toBe(first);
 expect([b,a].map(edge=>routeLayoutKey("q",edge))).toEqual([second,first]);
 const hook=renderHook(()=>useMapLinkLayout("s"));act(()=>hook.result.current.move(first,{x:400,y:500}));hook.unmount();
 const reopened=renderHook(()=>useMapLinkLayout("s"));expect(reopened.result.current.positions[first]).toEqual({x:400,y:500});expect(reopened.result.current.positions[second]).toBeUndefined();
});
it("isolates scenario layouts and ignores invalid saved coordinates",()=>{
 localStorage.setItem("studio-map-link-positions:v1:a",JSON.stringify({broken:{x:null,y:0},valid:{x:1,y:2}}));
 const hook=renderHook(({scenario})=>useMapLinkLayout(scenario),{initialProps:{scenario:"a"}});expect(hook.result.current.positions).toEqual({valid:{x:1,y:2}});
 hook.rerender({scenario:"b"});expect(hook.result.current.positions).toEqual({});act(()=>hook.result.current.move("valid",{x:NaN,y:0}));expect(hook.result.current.positions).toEqual({});
});
it("stores implicit primary and named primary entrance geometry independently",()=>{
 const implicit=entranceLayoutKey(null),named=entranceLayoutKey("primary");expect(implicit).not.toBe(named);
 const hook=renderHook(()=>useMapLinkLayout("primary-collision"));act(()=>hook.result.current.move(implicit,{x:100,y:200}));act(()=>hook.result.current.move(named,{x:700,y:800}));
 expect(hook.result.current.positions[implicit]).toEqual({x:100,y:200});expect(hook.result.current.positions[named]).toEqual({x:700,y:800});
});

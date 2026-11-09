import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioCatalogVisibility } from "./scenario-catalog-visibility";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
const offering:AdminServiceCatalogOffering={code:"print",full_code:"it.print",public_title:"Печать",visibility:"public",lifecycle_status:"published"};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("changes catalogue visibility separately without saving or publishing the draft",async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:"success",data:{offering:{...offering,visibility:"internal"}}})});vi.stubGlobal("fetch",fetcher);const saved=vi.fn();
 render(<ScenarioCatalogVisibility id="map" offering={offering} disabled={false} onSaved={saved}/>);
 fireEvent.change(screen.getByLabelText("Видимость услуги"),{target:{value:"internal"}});fireEvent.click(screen.getByRole("button",{name:"Применить видимость"}));
 await screen.findByText("Видимость изменена. Черновик и опубликованная версия сохранены.");expect(fetcher).toHaveBeenCalledTimes(1);expect(fetcher.mock.calls[0][0]).toBe("/api/web/admin/request-studio/scenarios/map/catalog-visibility");expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({visibility:"internal",expected_visibility:"public"});expect(saved).toHaveBeenCalledTimes(1);
});
it("keeps the saved choice on a concurrent update conflict",async()=>{
 vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({status:"error"})}));
 render(<ScenarioCatalogVisibility id="map" offering={offering} disabled={false}/>);fireEvent.change(screen.getByLabelText("Видимость услуги"),{target:{value:"internal"}});fireEvent.click(screen.getByRole("button",{name:"Применить видимость"}));await screen.findByRole("alert");expect(screen.getByLabelText("Видимость услуги")).toHaveValue("internal");expect(screen.getByText(/другой администратор/)).toBeInTheDocument();
});
it("refreshes catalogue after a late response without displaying success in another service",async()=>{
 let done!:(r:unknown)=>void;vi.stubGlobal("fetch",vi.fn(()=>new Promise(r=>{done=r;})));const saved=vi.fn(),refresh=vi.fn();const view=render(<ScenarioCatalogVisibility id="map" offering={offering} disabled={false} onSaved={saved} onRefresh={refresh}/>);fireEvent.change(screen.getByLabelText("Видимость услуги"),{target:{value:"internal"}});fireEvent.click(screen.getByRole("button",{name:"Применить видимость"}));view.rerender(<ScenarioCatalogVisibility id="other" offering={{...offering,full_code:"it.other"}} disabled={false} onSaved={saved} onRefresh={refresh}/>);await act(async()=>{done({ok:true,json:async()=>({status:"success",data:{offering:{...offering,visibility:"internal"}}})});});await waitFor(()=>expect(screen.getByLabelText("Видимость услуги")).toHaveValue("public"));expect(saved).not.toHaveBeenCalled();expect(refresh).toHaveBeenCalledTimes(1);
});

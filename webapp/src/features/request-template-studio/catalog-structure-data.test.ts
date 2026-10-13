import { expect, it, vi } from "vitest";
import type { ScenarioCatalog } from "./scenario-api";
import { fetchCatalogStructure } from "./catalog-structure-data";

it("loads every unfiltered page for the tree, retaining named entrances", async () => {
  const page = (offset:number):ScenarioCatalog => ({services:[],categories:[],offerings:[],scenarios:[{id:`s${offset}`} as never],entries:[{offering:{full_code:`it.${offset}`}} as never],total:3,offset,limit:2});
  const fetcher=vi.fn(async (_q,_status,offset)=>page(offset));
  const result=await fetchCatalogStructure(fetcher);
  expect(fetcher.mock.calls).toEqual([["","all",0,null],["","all",2,null]]);
  expect(result.entries).toHaveLength(2);
  expect(result.scenarios.map(item=>item.id)).toEqual(["s0","s2"]);
});

it("rejects a repeated page instead of looping or claiming a complete tree", async () => {
  const fetcher=vi.fn(async()=>({services:[],categories:[],offerings:[],scenarios:[],total:200,offset:0,limit:100}));
  await expect(fetchCatalogStructure(fetcher)).rejects.toThrow("CATALOG_PAGE_MISMATCH");
  expect(fetcher).toHaveBeenCalledTimes(2);
});

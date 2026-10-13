import type { ScenarioCatalog } from "./scenario-api";

type CatalogReader=(q:string,status:string,offset:number,category:null)=>Promise<ScenarioCatalog>;
export async function fetchCatalogStructure(read:CatalogReader):Promise<ScenarioCatalog> {
  const first=await read("","all",0,null);
  if(first.offset!==0||first.limit<=0)throw new Error("CATALOG_PAGE_MISMATCH");
  const entries=[...(first.entries??[])], scenarios=[...first.scenarios];
  for(let offset=first.limit;offset<first.total;) {
    const page=await read("","all",offset,null);
    if(page.offset!==offset||page.limit<=0||page.total!==first.total)throw new Error("CATALOG_PAGE_MISMATCH");
    entries.push(...page.entries??[]);scenarios.push(...page.scenarios);
    offset+=page.limit;
  }
  return {...first,...(first.entries?{entries}:{}),scenarios,limit:Math.max(first.limit,first.total)};
}

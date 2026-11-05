import { useState } from "react";
import { ChevronDown } from "lucide-react";

export type CatalogCategory = {
  key:string; title:string; offeringFullCode?:string;
  items:Array<{key:string;title:string;description?:string;entry_point_key:string}>;
};

export function CatalogCategories({categories,selectedKey,onSelect,onCategorySelect}: {
  categories:CatalogCategory[]; selectedKey?:string;
  onSelect:(offering:string,entry?:string)=>void;onCategorySelect:(key:string)=>void;
}) {
  const [expanded,setExpanded]=useState<string | undefined>(selectedKey);
  return <div className="mt-3 grid gap-2" aria-label="Все категории">
    {categories.map(category=><div key={category.key} className="overflow-hidden rounded-xl border border-slate-200">
      <button type="button" className="flex w-full items-center justify-between gap-3 bg-white p-3 text-left font-semibold text-slate-950 hover:bg-brand-50"
        aria-expanded={category.items.length ? expanded===category.key : undefined}
        onClick={()=>{if(category.items.length)setExpanded(expanded===category.key ? undefined : category.key);else onCategorySelect(category.key);}}>
        <span>{category.title}</span>{category.items.length ? <ChevronDown aria-hidden="true" className={`h-4 w-4 shrink-0 ${expanded===category.key ? 'rotate-180' : ''}`}/> : null}
      </button>
      {expanded===category.key ? <ul className="grid gap-1 border-t border-slate-200 bg-slate-50 p-2">
        {category.items.map(item=><li key={item.key}><button type="button" className="w-full rounded-lg p-3 text-left hover:bg-white focus-visible:outline-2 focus-visible:outline-brand-700"
          onClick={()=>{if(category.offeringFullCode)onSelect(category.offeringFullCode,item.entry_point_key);}}>
          <span className="block font-medium">{item.title}</span>{item.description ? <span className="mt-1 block text-sm text-slate-600">{item.description}</span> : null}
        </button></li>)}
      </ul> : null}
    </div>)}
  </div>;
}

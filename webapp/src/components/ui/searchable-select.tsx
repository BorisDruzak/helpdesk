import { useId, useState } from "react";
import { Input } from "./input";

/** One text field; only an explicit published option supplies the stored ID. */
export function SearchableSelect({ label, value, options, onChange, error, required, disabled }: {
  label: string; value: string; options: Array<{value:string;label:string;disabled?:boolean}>;
  onChange:(value:string)=>void; error?:string; required?:boolean; disabled?:boolean;
}) {
  const id=useId();
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState("");
  const [active,setActive]=useState(-1);
  const selected=options.find(item=>item.value===value);
  const filtered=options.filter(item=>item.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  function choose(item:typeof options[number]) {
    if(item.disabled) return;
    onChange(item.value);setQuery("");setOpen(false);setActive(-1);
  }
  return <div className="relative min-w-0 space-y-1 text-sm">
    <label htmlFor={id} className="font-semibold text-slate-700">{label}{required ? " *" : ""}</label>
    <Input id={id} role="combobox" aria-label={label} aria-expanded={open} aria-controls={`${id}-options`}
      aria-autocomplete="list" aria-required={required} aria-invalid={error ? true : undefined}
      aria-describedby={error ? `${id}-error` : undefined}
      aria-activedescendant={open && active>=0 ? `${id}-option-${active}` : undefined}
      disabled={disabled} className="w-full" autoComplete="off" placeholder="Выберите или начните вводить отдел"
      value={open ? query : selected?.label ?? ""}
      onFocus={()=>{setQuery("");setActive(-1);setOpen(true);}}
      onClick={()=>{if(!open){setQuery("");setActive(-1);setOpen(true);}}}
      onBlur={()=>{setOpen(false);setActive(-1);}}
      onChange={event=>{setQuery(event.target.value);setOpen(true);setActive(-1);if(value)onChange("");}}
      onKeyDown={event=>{
        if(event.key==='Escape'){event.preventDefault();setOpen(false);return;}
        if(event.key==='ArrowDown' || event.key==='ArrowUp') {
          event.preventDefault();setOpen(true);
          const next=event.key==='ArrowDown' ? Math.min(active+1,filtered.length-1) : Math.max(active-1,0);
          setActive(next);
          window.requestAnimationFrame(()=>document.getElementById(`${id}-option-${next}`)?.scrollIntoView?.({block:'nearest'}));return;
        }
        if(event.key==='Enter' && open){event.preventDefault();if(filtered[active])choose(filtered[active]);}
      }} />
    {open ? <ul id={`${id}-options`} role="listbox" aria-label={label} className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-xl border border-slate-300 bg-white p-1 shadow-lg">
      {filtered.map((item,index)=><li key={item.value} id={`${id}-option-${index}`} role="option" aria-selected={item.value===value} aria-disabled={item.disabled}
        className={`cursor-pointer rounded-lg px-3 py-2 break-words ${active===index ? 'bg-brand-50' : ''} ${item.disabled ? 'text-slate-400' : 'hover:bg-brand-50'}`}
        onMouseDown={event=>event.preventDefault()} onClick={()=>choose(item)}>{item.label}</li>)}
      {!filtered.length ? <li className="px-3 py-2 text-slate-500" role="presentation">Отдел не найден. Измените запрос.</li> : null}
    </ul> : null}
    {error ? <p id={`${id}-error`} className="text-xs font-semibold text-rose-700">{error}</p> : null}
  </div>;
}

import { useId, useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "./input";

export function PasswordInput({label,toggleLabel="пароль",hint,...props}:InputHTMLAttributes<HTMLInputElement> & {label:string;toggleLabel?:string;hint?:string}) {
  const id=useId();
  const [visible,setVisible]=useState(false);
  return <div className="min-w-0 space-y-1 text-sm font-medium">
    <label htmlFor={id}>{label}</label>
    <div className="relative">
      <Input {...props} id={id} aria-label={label} aria-describedby={hint ? `${id}-hint` : undefined} type={visible ? "text" : "password"} className="w-full pr-12" />
      <button type="button" aria-label={`${visible ? 'Скрыть' : 'Показать'} ${toggleLabel}`} aria-pressed={visible}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-slate-500 hover:text-slate-950 focus-visible:outline-2 focus-visible:outline-brand-700"
        onClick={()=>setVisible(!visible)}>{visible ? <EyeOff aria-hidden="true" className="h-5 w-5"/> : <Eye aria-hidden="true" className="h-5 w-5"/>}</button>
    </div>
    {hint ? <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p> : null}
  </div>;
}

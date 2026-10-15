import {useEffect,useRef} from 'react';
import {ArrowRight,ChevronDown,X,Info,Check,Search,Plus} from 'lucide-react';
export function Button({children,icon:Icon,primary=false,quiet=false,className='',...props}){return <button className={`button ${primary?'primary':''} ${quiet?'quiet':''} ${className}`} {...props}>{Icon&&<Icon size={18}/>}<span>{children}</span></button>;}
export function Tag({children,tone='green'}){return <span className={`tag ${tone}`}>{children}</span>;}
export function Field({label,hint,children}){return <label className="field"><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>;}
export function Select({label,value,onChange,options,disabled=false}){return <Field label={label}><select value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{options.map(o=><option key={typeof o==='string'?o:o.id} value={typeof o==='string'?o:o.id}>{typeof o==='string'?o:o.name||o.title}</option>)}</select></Field>;}
export function Toggle({label,checked,onChange,hint}){return <div className="toggle-row"><div><span>{label}</span>{hint&&<small>{hint}</small>}</div><button type="button" role="switch" aria-label={label} aria-checked={checked} className={`toggle ${checked?'on':''}`} onClick={()=>onChange(!checked)}><span/></button></div>;}
export function Advanced({children}){return <details className="advanced"><summary>Дополнительно <ChevronDown size={16}/></summary><div>{children}</div></details>;}
export function Notice({children,tone='info'}){return <div className={`notice ${tone}`}><Info size={18}/><div>{children}</div></div>;}
export function Empty({title,body,children}){return <div className="empty"><Search size={32}/><h3>{title}</h3><p>{body}</p>{children}</div>;}
export function SearchBox({value,onChange,placeholder='Поиск по названию или синониму'}){return <div className="searchbox"><Search size={18}/><input aria-label={placeholder} placeholder={placeholder} value={value} onChange={e=>onChange(e.target.value)}/>{value&&<button aria-label="Очистить поиск" onClick={()=>onChange('')}><X size={16}/></button>}</div>;}
export function Modal({title,children,onClose,footer}){
  const ref=useRef(null);
  useEffect(()=>{const before=document.activeElement;const dialog=ref.current;dialog?.querySelector('input,button,select,textarea')?.focus();const key=e=>{if(e.key==='Escape')onClose();if(e.key==='Tab'){const els=[...dialog.querySelectorAll('button,input,select,textarea,[tabindex="0"]')].filter(x=>!x.disabled);if(!els.length)return;const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);before?.focus();};},[onClose]);
  return <div className="modal-shade" onClick={e=>{if(e.target===e.currentTarget)onClose();}}><section ref={ref} className="modal" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button className="iconbutton" aria-label="Закрыть окно" onClick={onClose}><X size={20}/></button></header><div className="modal-body">{children}</div><footer>{footer}</footer></section></div>;
}
export function KeyValue({label,value}){return <div className="kv"><span>{label}</span><strong>{value}</strong></div>;}
export function ScreenHeading({eyebrow,title,description,children}){return <header className="screen-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description&&<p>{description}</p>}</div><div className="actions">{children}</div></header>;}
export function NextLink({children,onClick}){return <button className="text-link" onClick={onClick}>{children}<ArrowRight size={16}/></button>;}

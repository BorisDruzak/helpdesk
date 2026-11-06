import { createContext,useCallback,useContext,useEffect,useRef,type ReactNode } from 'react';

type Event='opened'|'search_ready'|'result_selected'|'service_selected'|'service_changed'|'catalog_selected'|'fallback_selected'|'submitted'|'abandoned';
type RecordEvent=(event:Event,details?:{rank?:number;resultCount?:number})=>void;
const Context=createContext<RecordEvent>(()=>{});
export const useCatalogEvent=()=>useContext(Context);

export function CatalogFunnel({children}:{children:ReactNode}) {
 const flow=useRef({id:crypto.randomUUID(),start:Date.now(),sequence:0,finished:false});
 const pendingLeave=useRef<ReturnType<typeof setTimeout>|null>(null);
 const record=useCallback<RecordEvent>((event,details={})=>{
  const current=flow.current;if(current.finished)return;
  if(event==='submitted'||event==='abandoned')current.finished=true;
  const body={flow_id:current.id,sequence:++current.sequence,event,
   elapsed_ms:Math.max(0,Math.min(86400000,Date.now()-current.start)),rank:details.rank??0,result_count:details.resultCount??0};
  try { void fetch('/api/web/requester/catalog-events',{method:'POST',credentials:'same-origin',keepalive:true,
   headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).catch(()=>{}); } catch { /* Metrics never block a request. */ }
 },[]);
 useEffect(()=>{
  if(pendingLeave.current!==null)clearTimeout(pendingLeave.current);
  if(!flow.current.sequence)record('opened');
  const leave=()=>record('abandoned');
  const resume=(event:PageTransitionEvent)=>{if(event.persisted){flow.current={id:crypto.randomUUID(),start:Date.now(),sequence:0,finished:false};record('opened');}};
  window.addEventListener('pagehide',leave);window.addEventListener('pageshow',resume);
  return()=>{window.removeEventListener('pagehide',leave);window.removeEventListener('pageshow',resume);pendingLeave.current=setTimeout(leave,0);};
 },[record]);
 return <Context.Provider value={record}>{children}</Context.Provider>;
}

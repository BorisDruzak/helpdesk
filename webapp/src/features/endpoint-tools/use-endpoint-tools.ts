import { useEffect,useRef,useState } from "react";
import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { useSession } from "../auth/session-provider";
import { acceptedToolKey,createRun,getCatalog,getRun,getRuns,pendingToolKey } from "./api";
import { activeStatus,type RunSelection,type ToolItem,type ToolRun } from "./types";

export function useVisiblePage() {
  const [visible,setVisible]=useState(()=>document.visibilityState!=="hidden");
  useEffect(()=>{const change=()=>setVisible(document.visibilityState!=="hidden");document.addEventListener("visibilitychange",change);return ()=>document.removeEventListener("visibilitychange",change);},[]);
  return visible;
}
export function runQueryKey(account:string,ticket:string,device:string,run:RunSelection) {return ["endpoint-tools",account,ticket,device,"run",run.module_key,run.version,run.profile,run.run_id] as const;}
export function useEndpointTools(ticketId:string) {
  const {session,status}=useSession();const account=session?.user_login??"";const visible=useVisiblePage();const queries=useQueryClient();
  const enabled=!!account && status!=="anonymous" && visible;
  const [cursor,setCursor]=useState<string|null>(null);const [selection,setSelection]=useState<RunSelection|null>(null);
  const version=useRef(0);const mounted=useRef(true);
  const current=useRef({account,ticketId,device:""});
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;void queries.cancelQueries({queryKey:["endpoint-tools",account,ticketId]});};},[queries,account,ticketId]);
  const catalog=useQuery({queryKey:["endpoint-tools",account,ticketId,"catalog",cursor],queryFn:({signal})=>getCatalog(ticketId,cursor,signal),enabled,staleTime:5000,retry:false});
  const device=catalog.data?.device_ref??"";
  current.current={account,ticketId,device};
  const history=useQuery({queryKey:["endpoint-tools",account,ticketId,device,"history"],queryFn:({signal})=>getRuns(ticketId,signal),enabled:enabled&&!!device,retry:false,
    refetchInterval:query=>query.state.data?.items.some(r=>activeStatus(r.status))?2000:false,refetchIntervalInBackground:false});
  const run=useQuery({queryKey:selection?runQueryKey(account,ticketId,device,selection):["endpoint-tools",account,ticketId,device,"no-run"],
    queryFn:({signal})=>getRun(ticketId,selection!.run_id,signal),enabled:enabled&&!!device&&!!selection,retry:false,
    refetchInterval:query=>activeStatus(query.state.data?.status)?2000:false,refetchIntervalInBackground:false});
  const chooseRun=(next:RunSelection|null)=>{version.current++;setSelection(next);};
  const create=useMutation({mutationKey:["endpoint-tools",account,ticketId,device,"create"],
    mutationFn:async({tool,inputs,selectionVersion}:{tool:ToolItem;inputs:Record<string,string|number>;selectionVersion:number})=>{
      const sorted=Object.fromEntries(Object.entries(inputs).sort(([a],[b])=>a.localeCompare(b)));
      const identity=pendingToolKey(account,ticketId,device,[tool.module_key,tool.version,sorted]);
      const scope={account,ticketId,device};
      const result=await createRun(ticketId,tool.module_key,tool.version,sorted,identity.key);acceptedToolKey(identity);return {result,selectionVersion,scope};
    },onSuccess:({result,selectionVersion,scope})=>{
      queries.setQueryData(runQueryKey(scope.account,scope.ticketId,result.device_ref,result),result);
      void queries.invalidateQueries({queryKey:["endpoint-tools",scope.account,scope.ticketId,result.device_ref,"history"]});
      if(mounted.current && version.current===selectionVersion && current.current.account===scope.account && current.current.ticketId===scope.ticketId && current.current.device===result.device_ref) setSelection(result);
    }});
  return {account,device,session,catalog,history,run,selection,chooseRun,selectionVersion:()=>version.current,create,setCursor};
}

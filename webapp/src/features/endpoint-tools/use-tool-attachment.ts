import { useMutation,useQueryClient } from "@tanstack/react-query";
import { useSession } from "../auth/session-provider";
import { attachSelectedToolResult } from "./api";
export function useToolAttachment(ticketId:string,deviceRef:string) {
  const {session}=useSession();const query=useQueryClient();const account=session?.user_login??"";
  const mutation=useMutation({mutationKey:["endpoint-tools",account,ticketId,deviceRef,"attach"],
    mutationFn:({runId,step,scope}:{runId:string;step:number;scope:{account:string;ticket:string;device:string}})=>attachSelectedToolResult(scope.ticket,runId,step).then(result=>({result,scope})),
    onSuccess:({result,scope})=>{
      query.setQueryData(["endpoint-tools",scope.account,scope.ticket,scope.device,"attached",result.run_id,result.step_sequence],true);
      void query.invalidateQueries({queryKey:["endpoint-tools",scope.account,scope.ticket,scope.device]});
      void query.invalidateQueries({queryKey:["support-ticket-passport",scope.ticket]});
    }});
  const known=(runId:string,step:number)=>query.getQueryData(["endpoint-tools",account,ticketId,deviceRef,"attached",runId,step])===true;
  const canAttach=!!session?.permissions?.includes("ticket.passport.manage");
  return {mutation,known,canAttach,attach:(runId:string,step:number)=>mutation.mutate({runId,step,scope:{account,ticket:ticketId,device:deviceRef}})};
}

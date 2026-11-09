
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {fetchTechAlerts, fetchWebSettingsPayload} from "../../features/settings/api";

import {type SettingsTab, type ActionFeedback, type QueueDraft, type RoutingDraft, type RoutingConditionBuilder, type PolicyDraft, type CalendarDraft, type ResolutionDraft, type OlaDraftRow, type SlaTargetDraftRow, type PriorityMatrixDraftRow, type WorkflowProfileDraft} from './settings-types';
import {buildQueueDraft, buildRoutingDraft, buildRoutingConditionBuilder, buildPolicyDraft, buildCalendarDraft, buildResolutionDraft, buildOlaDraft, buildSlaTargetsDraft, buildPriorityMatrixDraft} from './settings-form-model';
import {buildWorkflowProfileDraft} from './settings-workflow-model';

export function useServiceSettingsState(){
const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SettingsTab>("overview");
  const [dirtyGroups, setDirtyGroups] = useState<Record<string, boolean>>({});
  const dirty = Object.values(dirtyGroups).some(Boolean);
  const defaultGroup: Record<string,string> = {queues:'queue',routing:'routing',sla:'policy',calendars:'calendar',resolution:'resolution',tickets:'workflow'};
  function markDirty(group?:string) {if(group==="view")return;setDirtyGroups(current=>({...current,[group||defaultGroup[activeTab]||activeTab]:true}));}
  function setDirty(value:boolean) {if(value)markDirty();else setDirtyGroups({});}
  const [formEpoch, setFormEpoch] = useState(0);
  const [pendingChange, setPendingChange] = useState<(() => void) | null>(null);
  const [feedback, setFeedback] = useState<ActionFeedback>(null);

  const settingsQuery = useQuery({
    queryKey: ["web-settings"],
    queryFn: fetchWebSettingsPayload,
    retry: false,
    refetchInterval: dirty ? false : 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const techAlertsQuery = useQuery({
    queryKey: ["admin-tech-alerts-settings"],
    queryFn: fetchTechAlerts,
    enabled: activeTab === "notifications",
    retry: false,
    refetchInterval: 30_000,
  });

  const payload = settingsQuery.data;
  const canWrite = payload?.capabilities.can_write ?? false;
  const writeEnabled = payload?.ticket_settings.operational_flags.admin_config_write_enabled === true;
  const canManageQueues = (payload?.capabilities.can_manage_queues ?? canWrite) && writeEnabled;
  const canManageWorkflow = payload?.capabilities.can_manage_routing ?? canWrite;
  const canManageRouting = canManageWorkflow && writeEnabled;
  const workflowDeniedReason = canManageWorkflow ? null : payload?.capabilities.manage_routing_denial_reason ?? "Недостаточно прав: settings.manage_routing";
  const queueDeniedReason =
    canManageQueues ? null : !writeEnabled ? "Изменение общей конфигурации отключено на сервере." : payload?.capabilities.manage_queues_denial_reason ?? "Недостаточно прав: settings.manage_queues";
  const routingDeniedReason =
    canManageRouting ? null : !writeEnabled ? "Изменение общей конфигурации отключено на сервере." : payload?.capabilities.manage_routing_denial_reason ?? "Недостаточно прав: settings.manage_routing";

  const [selectedQueueId, setSelectedQueueId] = useState<number | null>(null);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null);
  const [selectedCalendarId, setSelectedCalendarId] = useState<number | null>(null);
  const [selectedResolutionCode, setSelectedResolutionCode] = useState<string | null>(null);

  const selectedQueue = selectedQueueId === -1 ? null : (selectedQueueId == null ? payload?.queues[0] : payload?.queues.find((item) => item.id === selectedQueueId)) ?? null;
  const selectedRule =
    selectedRuleId === -1
      ? null
      : payload?.routing_rules.find((item) => item.id === selectedRuleId) ?? null;
  const selectedPolicy = selectedPolicyId === -1 ? null : (selectedPolicyId == null ? payload?.sla_policies[0] : payload?.sla_policies.find((item) => item.id === selectedPolicyId)) ?? null;
  const selectedCalendar = selectedCalendarId === -1 ? null : (selectedCalendarId == null ? payload?.calendars[0] : payload?.calendars.find((item) => item.id === selectedCalendarId)) ?? null;
  const selectedResolution = selectedResolutionCode === "__new__" ? null : (selectedResolutionCode == null ? payload?.resolution_codes[0] : payload?.resolution_codes.find((item) => item.code === selectedResolutionCode)) ?? null;

  const [queueDraft, setQueueDraft] = useState<QueueDraft>(buildQueueDraft(null));
  const [routingDraft, setRoutingDraft] = useState<RoutingDraft>(buildRoutingDraft(null, null));
  const [routingConditionBuilder, setRoutingConditionBuilder] = useState<RoutingConditionBuilder>({
    field: "request_kind",
    op: "eq",
    value_text: "access",
    null_state: "true",
  });
  const [policyDraft, setPolicyDraft] = useState<PolicyDraft>(buildPolicyDraft(null));
  const [calendarDraft, setCalendarDraft] = useState<CalendarDraft>(buildCalendarDraft(null));
  const [resolutionDraft, setResolutionDraft] = useState<ResolutionDraft>(buildResolutionDraft(null));
  const [olaDraft, setOlaDraft] = useState<OlaDraftRow[]>(buildOlaDraft(null));
  const [slaTargetsDraft, setSlaTargetsDraft] = useState<SlaTargetDraftRow[]>(buildSlaTargetsDraft(null));
  const [priorityMatrixDraft, setPriorityMatrixDraft] = useState<PriorityMatrixDraftRow[]>(buildPriorityMatrixDraft(null));
  const [workflowProfileDrafts, setWorkflowProfileDrafts] = useState<WorkflowProfileDraft[]>([]);
  const [newMemberActorId, setNewMemberActorId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("");

  useEffect(() => {
    if (dirty || selectedQueueId === -1) return;
    if (!payload?.queues.length) {
      setSelectedQueueId(null);
      return;
    }
    if (!selectedQueueId || !payload.queues.some((item) => item.id === selectedQueueId)) {
      setSelectedQueueId(payload.queues[0].id);
    }
  }, [payload?.queues, selectedQueueId]);

  useEffect(() => {
    if (dirty) return;
    if (!payload?.routing_rules.length) {
      setSelectedRuleId(null);
      return;
    }
    if (selectedRuleId == null) {
      setSelectedRuleId(payload.routing_rules[0].id);
      return;
    }
    if (selectedRuleId !== -1 && !payload.routing_rules.some((item) => item.id === selectedRuleId)) {
      setSelectedRuleId(payload.routing_rules[0].id);
    }
  }, [payload?.routing_rules, selectedRuleId]);

  useEffect(() => {
    if (dirty || selectedPolicyId === -1) return;
    if (!payload?.sla_policies.length) {
      setSelectedPolicyId(null);
      return;
    }
    if (!selectedPolicyId || !payload.sla_policies.some((item) => item.id === selectedPolicyId)) {
      setSelectedPolicyId(payload.sla_policies[0].id);
    }
  }, [payload?.sla_policies, selectedPolicyId]);

  useEffect(() => {
    if (dirty || selectedCalendarId === -1) return;
    if (!payload?.calendars.length) {
      setSelectedCalendarId(null);
      return;
    }
    if (!selectedCalendarId || !payload.calendars.some((item) => item.id === selectedCalendarId)) {
      setSelectedCalendarId(payload.calendars[0].id);
    }
  }, [payload?.calendars, selectedCalendarId]);

  useEffect(() => {
    if (dirty || selectedResolutionCode === "__new__") return;
    if (!payload?.resolution_codes.length) {
      setSelectedResolutionCode(null);
      return;
    }
    if (!selectedResolutionCode || !payload.resolution_codes.some((item) => item.code === selectedResolutionCode)) {
      setSelectedResolutionCode(payload.resolution_codes[0].code);
    }
  }, [payload?.resolution_codes, selectedResolutionCode]);

  useEffect(() => {
    if (dirtyGroups.queue) return;
    setQueueDraft(buildQueueDraft(selectedQueue));

  }, [selectedQueue, dirtyGroups.queue, formEpoch]);

  useEffect(() => {
    if (dirtyGroups.routing) return;
    setRoutingDraft(buildRoutingDraft(selectedRule, payload?.queues[0]?.id ?? null));
    setRoutingConditionBuilder(
      buildRoutingConditionBuilder(
        (selectedRule?.condition_json as Record<string, unknown> | null | undefined) ?? null,
        payload?.routing_builder.fields[0]?.field ?? "request_kind"
      )
    );
  }, [payload?.queues, payload?.routing_builder.fields, selectedRule, dirtyGroups.routing, formEpoch]);

  useEffect(() => {
    if (dirtyGroups.policy) return;
    setPolicyDraft(buildPolicyDraft(selectedPolicy));
  }, [selectedPolicy, dirtyGroups.policy, formEpoch]);

  useEffect(() => {
    if (dirtyGroups.calendar) return;
    setCalendarDraft(buildCalendarDraft(selectedCalendar));
  }, [selectedCalendar, dirtyGroups.calendar, formEpoch]);

  useEffect(() => {
    if (dirtyGroups.resolution) return;
    setResolutionDraft(buildResolutionDraft(selectedResolution));
  }, [selectedResolution, dirtyGroups.resolution, formEpoch]);

  useEffect(() => {
    if (dirty) return;
    if (!payload?.ticket_settings.workflow_profiles) {
      setWorkflowProfileDrafts([]);
      return;
    }
    setWorkflowProfileDrafts(payload.ticket_settings.workflow_profiles.map(buildWorkflowProfileDraft));
  }, [payload?.ticket_settings.workflow_profiles, dirtyGroups.workflow, formEpoch]);


  useEffect(()=>{if(!dirtyGroups.ola)setOlaDraft(buildOlaDraft(selectedQueue));},[selectedQueue,dirtyGroups.ola,formEpoch]);
  useEffect(()=>{if(!dirtyGroups.sla)setSlaTargetsDraft(buildSlaTargetsDraft(selectedPolicy));},[selectedPolicy,dirtyGroups.sla,formEpoch]);
  useEffect(()=>{if(!dirtyGroups.matrix)setPriorityMatrixDraft(buildPriorityMatrixDraft(selectedPolicy));},[selectedPolicy,dirtyGroups.matrix,formEpoch]);

  function discardDraft() {
    setDirty(false);
    setFormEpoch(value => value + 1);
    setFeedback(null);
  }
  function requestChange(action: () => void) {
    if (dirty) {setPendingChange(() => action);return;}
    action();
  }
  function confirmChange() {
    discardDraft();
    pendingChange?.();
    setPendingChange(null);
  }
  function reportError(error: unknown, fallback: string) {
    setFeedback({
      tone: "error",
      text: error instanceof Error ? error.message : fallback,
    });
  }

  function reportSuccess(text: string) {
    setFeedback({
      tone: "success",
      text,
    });
  }

  async function refreshSettings(text?: string, group?: string) {
    setDirtyGroups(current => group ? {...current,[group]:false} : {});
    setFormEpoch(value => value + 1);
    await queryClient.invalidateQueries({ queryKey: ["web-settings"] });
    if (text) {
      reportSuccess(text);
    }
  }


return {canManageWorkflow,workflowDeniedReason,writeEnabled,markDirty,dirtyGroups,requestChange,discardDraft,pendingChange,setPendingChange,confirmChange,queryClient,activeTab,setActiveTab,dirty,setDirty,formEpoch,setFormEpoch,feedback,setFeedback,settingsQuery,techAlertsQuery,payload,canWrite,canManageQueues,canManageRouting,queueDeniedReason,routingDeniedReason,selectedQueueId,setSelectedQueueId,selectedRuleId,setSelectedRuleId,selectedPolicyId,setSelectedPolicyId,selectedCalendarId,setSelectedCalendarId,selectedResolutionCode,setSelectedResolutionCode,selectedQueue,selectedRule,selectedPolicy,selectedCalendar,selectedResolution,queueDraft,setQueueDraft,routingDraft,setRoutingDraft,routingConditionBuilder,setRoutingConditionBuilder,policyDraft,setPolicyDraft,calendarDraft,setCalendarDraft,resolutionDraft,setResolutionDraft,olaDraft,setOlaDraft,slaTargetsDraft,setSlaTargetsDraft,priorityMatrixDraft,setPriorityMatrixDraft,workflowProfileDrafts,setWorkflowProfileDrafts,newMemberActorId,setNewMemberActorId,newMemberRole,setNewMemberRole,reportError,reportSuccess,refreshSettings};
}

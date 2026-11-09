
import {useMutation} from "@tanstack/react-query";

import {createWebSettingsCalendar, createWebSettingsQueue, createWebSettingsResolutionCode, createWebSettingsRoutingRule, createWebSettingsSlaPolicy, deleteWebSettingsQueueMember, deleteWebSettingsResolutionCode, saveWebSettingsWorkflowProfiles, saveWebSettingsOlaTargets, saveWebSettingsPriorityMatrix, saveWebSettingsSlaTargets, setWebSettingsDefaultSlaPolicy, updateWebSettingsCalendar, updateWebSettingsQueue, updateWebSettingsResolutionCode, updateWebSettingsRoutingRule, updateWebSettingsSlaPolicy, upsertWebSettingsQueueMember} from "../../features/settings/api";

import {buildBusinessHoursJson, buildCalendarHoursJson, buildHolidaysJson, buildRoutingConditionJson} from './settings-form-model';
import {buildWorkflowProfilePayload, validDurationRows} from './settings-workflow-model';

import {useServiceSettingsState} from './use-service-settings-state';
export function useServiceSettingsActions(state:ReturnType<typeof useServiceSettingsState>){const {canManageWorkflow,queryClient,activeTab,setActiveTab,dirty,setDirty,formEpoch,setFormEpoch,feedback,setFeedback,settingsQuery,techAlertsQuery,payload,canWrite,canManageQueues,canManageRouting,queueDeniedReason,routingDeniedReason,selectedQueueId,setSelectedQueueId,selectedRuleId,setSelectedRuleId,selectedPolicyId,setSelectedPolicyId,selectedCalendarId,setSelectedCalendarId,selectedResolutionCode,setSelectedResolutionCode,selectedQueue,selectedRule,selectedPolicy,selectedCalendar,selectedResolution,queueDraft,setQueueDraft,routingDraft,setRoutingDraft,routingConditionBuilder,setRoutingConditionBuilder,policyDraft,setPolicyDraft,calendarDraft,setCalendarDraft,resolutionDraft,setResolutionDraft,olaDraft,setOlaDraft,slaTargetsDraft,setSlaTargetsDraft,priorityMatrixDraft,setPriorityMatrixDraft,workflowProfileDrafts,setWorkflowProfileDrafts,newMemberActorId,setNewMemberActorId,newMemberRole,setNewMemberRole,reportError,reportSuccess,refreshSettings}=state;
  const workflowProfilesMutation = useMutation({
    mutationFn: async () => {
      if (!canManageWorkflow) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      const profiles = buildWorkflowProfilePayload(workflowProfileDrafts);
      if (!profiles.length) {
        throw new Error("Нужен хотя бы один workflow profile.");
      }
      const ticketTypes = new Set<string>();
      for (const profile of profiles) {
        if (!profile.ticket_type) {
          throw new Error("ticket_type не может быть пустым.");
        }
        if (ticketTypes.has(profile.ticket_type)) {
          throw new Error(`ticket_type дублируется: ${profile.ticket_type}`);
        }
        ticketTypes.add(profile.ticket_type);
      }
      await saveWebSettingsWorkflowProfiles(profiles);
    },
    onSuccess: async () => refreshSettings("Профили процесса сохранены.",'workflow'),
    onError: (error) => reportError(error, "Не удалось сохранить профили процесса."),
  });

  const queueMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!queueDraft.code.trim() || !queueDraft.name.trim()) {
        throw new Error("Для очереди нужны code и name.");
      }
      if (selectedQueueId != null && selectedQueueId !== -1 && !selectedQueue) throw new Error("Выбранная настройка больше недоступна. Отмените изменения и обновите страницу.");
      if (selectedQueue) {
        await updateWebSettingsQueue(selectedQueue.id, queueDraft);
        return { created: false, id: selectedQueue.id };
      }
      const result = await createWebSettingsQueue({
        code: queueDraft.code.trim(),
        name: queueDraft.name.trim(),
        is_triage: queueDraft.is_triage,
        auto_assign_enabled: queueDraft.auto_assign_enabled,
      });
      return { created: true, id: result.queue.id };
    },
    onSuccess: async (result) => {
      await refreshSettings("Настройки очереди сохранены.",'queue');
      if (result.created) { setSelectedQueueId(result.id); }
    },
    onError: (error) => reportError(error, "Не удалось сохранить очередь."),
  });

  const memberMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      if (!newMemberActorId.trim()) {
        throw new Error("Укажите actor_id участника очереди.");
      }
      await upsertWebSettingsQueueMember(selectedQueue.id, newMemberActorId.trim(), {
        role_in_queue: newMemberRole.trim() || null,
      });
    },
    onSuccess: async () => {
      setNewMemberActorId("");
      setNewMemberRole("");
      await refreshSettings("Участник очереди обновлён.",'member');
    },
    onError: (error) => reportError(error, "Не удалось обновить участника очереди."),
  });

  const removeMemberMutation = useMutation({
    mutationFn: async (actorId: string) => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      await deleteWebSettingsQueueMember(selectedQueue.id, actorId);
    },
    onSuccess: async () => {
      await refreshSettings("Участник очереди удалён.",'member');
    },
    onError: (error) => reportError(error, "Не удалось удалить участника очереди."),
  });

  const olaMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      await saveWebSettingsOlaTargets(selectedQueue.id, validDurationRows(olaDraft, "ack_min", "processing_min"));
    },
    onSuccess: async () => {
      await refreshSettings("Внутренние сроки очереди сохранены.",'ola');
    },
    onError: (error) => reportError(error, "Не удалось сохранить внутренние сроки очереди."),
  });

  const routingMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!routingDraft.target_queue_id) {
        throw new Error("Для правила нужно выбрать целевую очередь.");
      }
      if (selectedRuleId != null && selectedRuleId !== -1 && !selectedRule) throw new Error("Выбранное правило больше недоступно. Отмените изменения и обновите страницу.");
      const conditionJson = buildRoutingConditionJson(routingConditionBuilder);
      const payloadToSave = {
        enabled: routingDraft.enabled,
        priority_order: Number(routingDraft.priority_order),
        target_queue_id: Number(routingDraft.target_queue_id),
        condition_json: conditionJson,
      };
      if (selectedRule) {
        await updateWebSettingsRoutingRule(selectedRule.id, payloadToSave);
        return { created: false, id: selectedRule.id };
      }
      const result = await createWebSettingsRoutingRule(payloadToSave);
      return { created: true, id: result.routing_rule.id };
    },
    onSuccess: async (result) => {
      await refreshSettings("Правило маршрутизации сохранено.",'routing');
      if (result.created) {setSelectedRuleId(result.id);}
    },
    onError: (error) => reportError(error, "Не удалось сохранить правило маршрутизации."),
  });

  const policyMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!policyDraft.name.trim()) {
        throw new Error("У политики сроков должно быть имя.");
      }
      const payloadToSave = {
        name: policyDraft.name.trim(),
        timezone: policyDraft.timezone.trim() || "UTC",
        business_hours_json: buildBusinessHoursJson(policyDraft.business_hours_mode),
        calendar_id: policyDraft.calendar_id ? Number(policyDraft.calendar_id) : null,
        is_default: policyDraft.is_default,
        ...(selectedPolicy ? { is_active: policyDraft.is_active } : {}),
      };
      if (selectedPolicyId != null && selectedPolicyId !== -1 && !selectedPolicy) throw new Error("Выбранная настройка больше недоступна. Отмените изменения и обновите страницу.");
      if (selectedPolicy) {
        await updateWebSettingsSlaPolicy(selectedPolicy.id, payloadToSave);
        if (policyDraft.is_default && !selectedPolicy.is_default) {
          await setWebSettingsDefaultSlaPolicy(selectedPolicy.id);
        }
        return { created: false, id: selectedPolicy.id };
      }
      const result = await createWebSettingsSlaPolicy(payloadToSave);
      return { created: true, id: result.sla_policy.id };
    },
    onSuccess: async (result) => {
      await refreshSettings("Политика сроков сохранена.",'policy');
      if (result.created) { setSelectedPolicyId(result.id); }
    },
    onError: (error) => reportError(error, "Не удалось сохранить политику сроков."),
  });

  const slaTargetsMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedPolicy) {
        throw new Error("Сначала выберите политику сроков.");
      }
      await saveWebSettingsSlaTargets(selectedPolicy.id, validDurationRows(slaTargetsDraft, "first_response_min", "resolution_min"));
    },
    onSuccess: async () => {
      await refreshSettings("Сроки ответа и решения сохранены.",'sla');
    },
    onError: (error) => reportError(error, "Не удалось сохранить сроки ответа и решения."),
  });

  const priorityMatrixMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedPolicy) {
        throw new Error("Сначала выберите политику сроков.");
      }
      await saveWebSettingsPriorityMatrix(selectedPolicy.id, priorityMatrixDraft.filter(row=>row.priority));
    },
    onSuccess: async () => {
      await refreshSettings("Матрица приоритетов сохранена.",'matrix');
    },
    onError: (error) => reportError(error, "Не удалось сохранить матрицу приоритетов."),
  });

  const calendarMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!calendarDraft.code.trim() || !calendarDraft.name.trim()) {
        throw new Error("Для календаря нужны code и name.");
      }
      const payloadToSave = {
        code: calendarDraft.code.trim(),
        name: calendarDraft.name.trim(),
        timezone: calendarDraft.timezone.trim() || "UTC",
        weekly_hours_json: buildCalendarHoursJson(calendarDraft.weekly_hours),
        holidays_json: buildHolidaysJson(calendarDraft.holidays),
        ...(selectedCalendar ? { is_active: calendarDraft.is_active } : {}),
      };
      if (selectedCalendarId != null && selectedCalendarId !== -1 && !selectedCalendar) throw new Error("Выбранная настройка больше недоступна. Отмените изменения и обновите страницу.");
      if (selectedCalendar) {
        await updateWebSettingsCalendar(selectedCalendar.id, payloadToSave);
        return { created: false, id: selectedCalendar.id };
      }
      const result = await createWebSettingsCalendar(payloadToSave);
      return { created: true, id: result.calendar.id };
    },
    onSuccess: async (result) => {
      await refreshSettings("Календарь сохранён.",'calendar');
      if (result.created) { setSelectedCalendarId(result.id); }
    },
    onError: (error) => reportError(error, "Не удалось сохранить календарь."),
  });

  const resolutionMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!resolutionDraft.code.trim() || !resolutionDraft.name.trim()) {
        throw new Error("Для кода решения нужны code и name.");
      }
      const payloadToSave = {
        name: resolutionDraft.name.trim(),
        is_active: resolutionDraft.is_active,
        sort_order: Number(resolutionDraft.sort_order),
      };
      if (selectedResolutionCode != null && selectedResolutionCode !== "__new__" && !selectedResolution) throw new Error("Выбранная настройка больше недоступна. Отмените изменения и обновите страницу.");
      if (selectedResolution) {
        await updateWebSettingsResolutionCode(selectedResolution.code, payloadToSave);
        return { created: false, code: selectedResolution.code };
      }
      const result = await createWebSettingsResolutionCode({
        code: resolutionDraft.code.trim(),
        ...payloadToSave,
      });
      return { created: true, code: result.resolution_code.code };
    },
    onSuccess: async (result) => {
      await refreshSettings("Код решения сохранён.",'resolution');
      if (result.created) { setSelectedResolutionCode(result.code); }
    },
    onError: (error) => reportError(error, "Не удалось сохранить код решения."),
  });

  const deleteResolutionMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedResolution) {
        throw new Error("Сначала выберите код решения.");
      }
      await deleteWebSettingsResolutionCode(selectedResolution.code);
    },
    onSuccess: async () => {
      await refreshSettings("Код решения удалён.",'resolution');
    },
    onError: (error) => reportError(error, "Не удалось удалить код решения."),
  });


return {workflowProfilesMutation,queueMutation,memberMutation,removeMemberMutation,olaMutation,routingMutation,policyMutation,slaTargetsMutation,priorityMatrixMutation,calendarMutation,resolutionMutation,deleteResolutionMutation};
}

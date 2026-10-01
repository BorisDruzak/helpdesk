import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  fetchSupportQueue,
  fetchSupportTicketPassportEvidenceCandidates,
  fetchSupportTicketPassport,
  fetchSupportTicketDetail,
  fetchSupportTicketPlaybooks,
  fetchSupportTicketTools,
  generateSupportTicketPassport,
  createSupportTicketPassportEvidence,
  linkSupportTicketPassportEvidence,
  patchSupportTicketPassport,
  postSupportTicketMessage,
  postSupportTicketPlaybookRun,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportTicketPassportEvidenceCreatePayload,
  type SupportPlaybookRunActionResult,
  type SupportQueueScope,
  type SupportTicketPassportSectionPatchPayload,
} from "../../../features/queues/api";
import {
  requirePermission,
  requireToolRunPermission,
} from "../../../features/auth/permissions";
import {
  useSession,
} from "../../../features/auth/session-provider";
import {
  getNextActionOwnerForStatus,
} from "../../../features/tickets/status-presentation";
import {
  getSharedWebRealtimeClient,
} from "../../../shared/realtime/client";
import {
  SUPPORT_QUEUE_REFRESH_MS,
  formatDateTime,
  flattenAttachments,
  parseToolParams,
} from '../detail-formatting';
export function useTicketDetailController() {
  const navigate = useNavigate();
  const { ticketId } = useParams();
  const queryClient = useQueryClient();
  const { session } = useSession();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [queueSearch, setQueueSearch] = useState("");
  const [activeTab, setActiveTab] = useState("dialog");
  const [messageMode, setMessageMode] = useState<"internal" | "public">("public");
  const [messageDraft, setMessageDraft] = useState("");
  const [statusAction, setStatusAction] = useState("");
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [toolParams, setToolParams] = useState<Record<string, unknown>>({});
  const [toolSearch, setToolSearch] = useState("");
  const [selectedPlaybookVersionId, setSelectedPlaybookVersionId] = useState<number | null>(null);
  const deferredQueueSearch = useDeferredValue(queueSearch);
  const deferredToolSearch = useDeferredValue(toolSearch);
  const queueQuery = useQuery({
    queryKey: ["ticket-detail-queue", scope, statusFilter, deferredQueueSearch],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter,
        query: deferredQueueSearch,
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS,
  });
  const detailQuery = useQuery({
    queryKey: ["ticket-detail", ticketId],
    queryFn: () => fetchSupportTicketDetail(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });
  const toolsQuery = useQuery({
    queryKey: ["ticket-tools", ticketId],
    queryFn: () => fetchSupportTicketTools(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });
  const playbooksQuery = useQuery({
    queryKey: ["ticket-playbooks", ticketId],
    queryFn: () => fetchSupportTicketPlaybooks(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });
  const passportQuery = useQuery({
    queryKey: ["ticket-passport", ticketId],
    queryFn: () => fetchSupportTicketPassport(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });
  const passportCandidatesQuery = useQuery({
    queryKey: ["ticket-passport-candidates", ticketId],
    queryFn: () => fetchSupportTicketPassportEvidenceCandidates(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });
  useEffect(() => {
    setStatusAction("");
    setMessageDraft("");
    setSelectedPlaybookVersionId(null);
  }, [ticketId]);
  const toolList = toolsQuery.data?.tools ?? [];
  const visibleTools = useMemo(() => {
    const normalized = deferredToolSearch.trim().toLowerCase();
    if (!normalized) {
      return toolList;
    }
    return toolList.filter((tool) =>
      [
        tool.tool_name,
        tool.module_name ?? "",
        tool.description ?? "",
        tool.source,
        tool.risk_level,
      ].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [deferredToolSearch, toolList]);
  useEffect(() => {
    if (!visibleTools.length) {
      setSelectedToolName(null);
      setSelectedPresetId("");
      setToolParams({});
      return;
    }

    if (!selectedToolName || !visibleTools.some((tool) => tool.tool_name === selectedToolName)) {
      setSelectedToolName(visibleTools[0].tool_name);
      setSelectedPresetId("");
      setToolParams({});
    }
  }, [selectedToolName, visibleTools]);
  const playbooks = playbooksQuery.data?.playbooks ?? [];
  useEffect(() => {
    if (!playbooks.length) {
      setSelectedPlaybookVersionId(null);
      return;
    }
    if (!selectedPlaybookVersionId || !playbooks.some((playbook) => playbook.playbook_version_id === selectedPlaybookVersionId)) {
      setSelectedPlaybookVersionId(playbooks[0].playbook_version_id);
    }
  }, [playbooks, selectedPlaybookVersionId]);
  useEffect(() => {
    if (!ticketId) {
      return;
    }

    const realtimeClient = getSharedWebRealtimeClient();
    return realtimeClient.subscribeTicket(ticketId, () => {
      void queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-playbooks", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] });
    });
  }, [queryClient, ticketId]);
  const sendMessageMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(
        session,
        messageMode === "internal" ? "ticket.comment.internal" : "ticket.comment.public",
      );
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return postSupportTicketMessage(ticketId, messageDraft.trim(), messageMode);
    },
    onSuccess: async () => {
      setMessageDraft("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] }),
      ]);
    },
  });
  const statusMutation = useMutation({
    mutationFn: async (nextStatus: string) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.status.change");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return postSupportTicketStatus(ticketId, nextStatus);
    },
    onSuccess: async () => {
      setStatusAction("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] }),
      ]);
    },
  });
  const toolMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const selectedTool = toolList.find((tool) => tool.tool_name === selectedToolName) ?? null;
      const parsed = parseToolParams(selectedTool, selectedPresetId, toolParams);
      const access = requireToolRunPermission(session, selectedTool?.risk_level);
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return postSupportTicketToolRun(ticketId, {
        toolName: selectedTool!.tool_name,
        presetId: parsed.presetId,
        params: parsed.params,
        ...(selectedTool!.tool_name === "endpoint.context.diagnostic.collect" ? { actorLogin: session?.user_login ?? "" } : {}),
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] }),
      ]);
    },
  });
  const playbookMutation = useMutation<SupportPlaybookRunActionResult, Error, number>({
    mutationFn: async (playbookVersionId: number) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.playbook.run");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return postSupportTicketPlaybookRun(ticketId, { playbookVersionId });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-playbooks", ticketId] }),
      ]);
    },
  });
  const passportGenerateMutation = useMutation({
    mutationFn: async (mode: "create" | "refresh") => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.passport.manage");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return generateSupportTicketPassport(ticketId, mode);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      ]);
    },
  });
  const passportLinkCandidateMutation = useMutation({
    mutationFn: async (link: { source_kind: string; source_id: string; required_fact?: string | null; visibility?: string }) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.passport.manage");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return linkSupportTicketPassportEvidence(ticketId, link);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      ]);
    },
  });
  const passportCreateEvidenceMutation = useMutation({
    mutationFn: async (evidence: SupportTicketPassportEvidenceCreatePayload) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.passport.manage");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return createSupportTicketPassportEvidence(ticketId, evidence);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      ]);
    },
  });
  const passportPatchSectionsMutation = useMutation({
    mutationFn: async (patch: SupportTicketPassportSectionPatchPayload) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const access = requirePermission(session, "ticket.passport.manage");
      if (!access.allowed) {
        throw new Error(access.reason);
      }
      return patchSupportTicketPassport(ticketId, patch);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      ]);
    },
  });
  const queue = queueQuery.data;
  const detail = detailQuery.data;
  const passport = passportQuery.data;
  const attachments = detail && ticketId ? flattenAttachments(ticketId, detail.timeline) : [];
  const historyItems = detail?.timeline.filter((entry) => entry.event_type !== "chat_message") ?? [];
  const autoPlaybookEvents = detail?.timeline.filter((entry) => entry.event_type === "playbook_started") ?? [];
  const selectedTool = toolList.find((tool) => tool.tool_name === selectedToolName) ?? null;
  const statusAccess = requirePermission(session, "ticket.status.change");
  const publicCommentAccess = requirePermission(session, "ticket.comment.public");
  const internalCommentAccess = requirePermission(session, "ticket.comment.internal");
  const messageAccess = messageMode === "internal" ? internalCommentAccess : publicCommentAccess;
  const playbookAccess = requirePermission(session, "ticket.playbook.run");
  const passportAccess = requirePermission(session, "ticket.passport.manage");
  const toolAccess = requireToolRunPermission(session, selectedTool?.risk_level);
  const canSendInternal = Boolean(detail?.actions.can_send_internal_note) && internalCommentAccess.allowed;
  const latestOperations = detail?.snapshot.latest_operations ?? [];
  const customerHistoryEvents = detail?.customer_history?.events?.slice(0, 10) ?? [];
  const contextPreviewEvents = detail?.llm_context_preview?.events?.slice(0, 10) ?? [];
  const priorityDecision = detail?.ticket.priority_decision ?? {};
  const requestRows = detail?.request_form?.rows ?? [];
  const findRequestValue = (keys: string[]): string => {
    for (const key of keys) {
      const value = requestRows.find((row) => row.key === key)?.value;
      if (value) {
        return value;
      }
    }
    return "";
  };
  const diagnosticsDone = detail
    ? [
      ...detail.timeline
        .filter((entry) =>
          ["tool_call_result", "playbook_started", "status_changed", "passport_generated", "ticket_routed"].includes(
            entry.event_type
          )
        )
        .slice(0, 5)
        .map((entry) => entry.text),
      ...latestOperations
        .slice(0, 3)
        .map((operation) => operation.result_summary || operation.tool_name || operation.operation_id),
      ...(detail.ticket.resolution_summary ? [detail.ticket.resolution_summary] : []),
    ].filter(Boolean)
    : [];
  const latestTimelineEntry = detail?.timeline.length ? detail.timeline[detail.timeline.length - 1] : null;
  const operationalRows = detail
    ? [
      {
        question: "Что случилось?",
        answer: detail.ticket.description || detail.ticket.title,
      },
      {
        question: "С кем случилось?",
        answer: detail.ticket.requester_display_name || "Не указано",
      },
      {
        question: "Где случилось?",
        answer:
          findRequestValue(["location", "room", "cabinet", "building", "office", "pc_name", "device_location"]) ||
          detail.ticket.device_id ||
          "Не указано",
      },
      {
        question: "Что затронуто?",
        answer:
          findRequestValue([
            "service",
            "service_id",
            "system",
            "system_name",
            "url",
            "device",
            "asset_name",
            "printer",
            "printer_model",
            "software_name",
            "replace_what",
          ]) ||
          detail.ticket.ticket_type ||
          "Не указано",
      },
      {
        question: "Кто сейчас должен действовать?",
        answer: detail.ticket.next_action_owner || getNextActionOwnerForStatus(detail.ticket.status),
      },
      {
        question: "Когда крайний срок?",
        answer:
          formatDateTime(detail.ticket.resolution_due_at) ||
          formatDateTime(detail.ticket.next_action_due_at) ||
          "Не указан",
      },
      {
        question: "Что уже проверили и сделали?",
        answer: diagnosticsDone.length ? diagnosticsDone.join(" / ") : "Пока нет зафиксированных действий",
      },
    ]
    : [];
  const operationalCompleteness = operationalRows.filter((row) => {
    const value = String(row.answer ?? "").trim();
    return value && !/Не указан|Пока нет/i.test(value);
  }).length;
  const tabItems = [
    { value: "dialog", label: "Диалог", count: detail?.timeline.length ?? 0 },
    { value: "diagnostics", label: "Диагностика" },
    { value: "info", label: "Информация" },
    { value: "files", label: "Файлы", count: attachments.length },
    {
      value: "history",
      label: "История",
      count: historyItems.length + latestOperations.length + customerHistoryEvents.length,
    },
    { value: "passport", label: "Паспорт", count: passport?.passport ? passport.passport.version : undefined },
  ];
  return { navigate, ticketId, queryClient, session, scope, setScope, statusFilter, setStatusFilter, queueSearch, setQueueSearch, activeTab, setActiveTab, messageMode, setMessageMode, messageDraft, setMessageDraft, statusAction, setStatusAction, selectedToolName, setSelectedToolName, selectedPresetId, setSelectedPresetId, toolParams, setToolParams, toolSearch, setToolSearch, selectedPlaybookVersionId, setSelectedPlaybookVersionId, deferredQueueSearch, deferredToolSearch, queueQuery, detailQuery, toolsQuery, playbooksQuery, passportQuery, passportCandidatesQuery, toolList, visibleTools, playbooks, sendMessageMutation, statusMutation, toolMutation, playbookMutation, passportGenerateMutation, passportLinkCandidateMutation, passportCreateEvidenceMutation, passportPatchSectionsMutation, queue, detail, passport, attachments, historyItems, autoPlaybookEvents, selectedTool, statusAccess, publicCommentAccess, internalCommentAccess, messageAccess, playbookAccess, passportAccess, toolAccess, canSendInternal, latestOperations, customerHistoryEvents, contextPreviewEvents, priorityDecision, requestRows, findRequestValue, diagnosticsDone, latestTimelineEntry, operationalRows, operationalCompleteness, tabItems };
}
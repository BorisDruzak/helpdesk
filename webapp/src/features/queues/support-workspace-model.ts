import type {
  SupportQueuePayload,
  SupportTicketClosurePlanPayload,
  SupportTicketDetailPayload,
  SupportTicketInventoryContext,
  SupportTicketKnowledgeSuggestionsPayload,
  SupportTicketPassportReadinessPayload,
  SupportTicketPassportPayload,
  SupportTicketPlaybooksPayload,
  SupportTicketSlaOlaPayload,
  SupportTicketToolsPayload,
} from "./api";
import type { TicketBadgeTone } from "../tickets/status-presentation";

export type SupportWorkspaceTheme = "dark" | "light";

export type SupportWorkspaceSliceId =
  | "my_action"
  | "sla_risk"
  | "unassigned"
  | "requester_reply"
  | string;

export type SupportWorkspaceSlice = {
  id: SupportWorkspaceSliceId;
  label: string;
  count: number;
  icon: "inbox" | "alert" | "user" | "message" | "spark";
  active: boolean;
};

export type SupportWorkspaceQueue = {
  id: string;
  label: string;
  count: number;
  icon: "layers" | "network" | "server" | "printer" | "monitor" | "shield";
  active: boolean;
};

export type SupportWorkspaceTicketItem = {
  id: string;
  code: string;
  subject: string;
  requester: string;
  priority: string;
  priorityTone: TicketBadgeTone;
  statusLabel: string;
  statusTone: TicketBadgeTone;
  queueLabel: string;
  assigneeLabel: string;
  updatedLabel: string;
  unread: boolean;
  nextDueLabel: string;
  slaRisk: boolean;
  hiddenFromWorkspace: boolean;
  archivedAt: string | null;
  active: boolean;
};

export type SupportWorkspaceNextAction = {
  owner: string;
  ownerLabel: string;
  label: string;
  hint: string;
  dueAt: string | null;
  remainingSeconds: number | null;
  remainingLabel: string;
  timerType: "sla" | "ola" | "none";
  tone: TicketBadgeTone;
};

export type SupportWorkspaceTimer = {
  key: "first_response" | "resolution" | "ola_ack" | "ola_processing";
  label: string;
  dueAt: string | null;
  remainingSeconds: number | null;
  remainingLabel: string;
  status: "ok" | "at_risk" | "breached" | "paused" | "unknown";
  progress: number;
};

export type SupportWorkspaceTimelineKind =
  | "message"
  | "internal"
  | "diagnostics"
  | "history";

export type SupportWorkspaceTimelineItem = {
  id: string;
  kind: SupportWorkspaceTimelineKind;
  title: string;
  actor: string;
  timestampLabel: string;
  body: string;
  visibility: string;
  tone: TicketBadgeTone;
  operation?: {
    name: string;
    status: string;
    statusLabel: string;
    statusTone: TicketBadgeTone;
    summary: string | null;
    preview: string | null;
    resultPayload?: unknown;
    presentationSchema?: unknown;
    presentationSchemaSource?: string | null;
    metaLabels: string[];
    steps?: Array<{
      name: string;
      status: string;
      value: string;
      details?: string | null;
    }>;
  };
  attachments: Array<Record<string, unknown>>;
};

export type SupportWorkspaceClosurePlan = {
  readyForResolution: boolean;
  missingCount: number;
  total: number;
  evidenceCandidateCount: number;
  recommendedNextAction: string | null;
  blockers: Array<{
    key: string;
    label: string;
    detail: string;
    actionKind: string;
    actionLabel: string;
    severity: string | null;
    candidateCount: number;
    factKey: string | null;
    blockingForClosure: boolean;
  }>;
};

export type SupportWorkspaceSelectedTicket = {
  id: string;
  code: string;
  subject: string;
  description: string;
  priority: string;
  priorityTone: TicketBadgeTone;
  statusLabel: string;
  statusTone: TicketBadgeTone;
  queueLabel: string;
  assigneeLabel: string;
  requesterLabel: string;
  createdLabel: string;
  updatedLabel: string;
  hiddenFromWorkspace: boolean;
  hiddenReason: string | null;
  archivedAt: string | null;
  archiveReason: string | null;
  canHideFromWorkspace: boolean;
  canUnhideFromWorkspace: boolean;
  canArchiveTicket: boolean;
  canUnarchiveTicket: boolean;
  resolutionCode: string;
  requesterResolutionSummary: string;
  resolutionSummary: string;
  nextAction: SupportWorkspaceNextAction;
  timers: SupportWorkspaceTimer[];
  timeline: SupportWorkspaceTimelineItem[];
  canSendInternalNote: boolean;
  closurePlan: SupportWorkspaceClosurePlan;
};

export type SupportWorkspaceContext = {
  requester: {
    name: string;
    department: string;
    phone: string;
    email: string;
    location: string;
    sourceLabel: string;
    accountWarning: string | null;
    accountDeclaredName: string | null;
    accountLogin: string | null;
    accountReason: string | null;
    accountVerification: string | null;
    activeDeviceOwner: string | null;
  };
  device: {
    id: string | null;
    assetId: string | null;
    assetTypeLabel: string;
    hostname: string;
    os: string;
    online: boolean;
    onlineLabel: string;
    lastSeenLabel: string;
  };
  classification: {
    ticketType: string;
    category: string;
    service: string;
    serviceOwner: string;
    serviceSourceLabel: string;
    source: string;
    similarTicketsCount: number;
  };
};

export type SupportWorkspaceToolItem = {
  id: string;
  kind: "playbook" | "tool";
  title: string;
  subtitle: string;
  riskLabel: string;
  enabled: boolean;
  disabledReason: string | null;
  requiresConsent: boolean;
  metaLabels: string[];
};

export type SupportWorkspaceOperationSummary = {
  id: string;
  title: string;
  status: string;
  statusLabel: string;
  statusTone: TicketBadgeTone;
  active: boolean;
  retryable: boolean;
  canRetry: boolean;
  canCancel: boolean;
  requiresConsentForRetry: boolean;
  retryUrl: string | null;
  cancelUrl: string | null;
  retryDisabledReason: string | null;
  cancelDisabledReason: string | null;
  policyLabels: string[];
  detailsUrl: string | null;
  traceRelation: string;
  traceRelationLabel: string;
  traceUrl: string | null;
  rootTraceUrl: string | null;
  retryOfOperationId: string | null;
  retrySourceTraceId: string | null;
  summary: string | null;
  metaLabels: string[];
  queuedOrStartedLabel: string;
  finishedLabel: string | null;
};

export type SupportWorkspaceObserverTrace = {
  id: string;
  compactId: string;
  title: string;
  status: string;
  statusLabel: string;
  rootKind: string;
  errorCount: number;
  timeLabel: string;
  traceUrl: string | null;
};

export type SupportWorkspaceObserverDiagnostic = {
  health: string;
  healthLabel: string;
  healthTone: TicketBadgeTone;
  summaryEndpoint: string;
  rootTraceId: string | null;
  rootTraceCompactId: string;
  rootTraceUrl: string | null;
  rootTraceStatusLabel: string;
  rootKind: string;
  traceCount: number;
  activeTraceCount: number;
  errorTraceCount: number;
  signatureCount: number;
  latestTraceLabel: string;
  latestErrorLabel: string | null;
  latestErrorStage: string | null;
  latestErrorAtLabel: string | null;
  topSignature: {
    title: string;
    severity: string;
    ticketOccurrences: number;
    globalOccurrences: number | null;
    lastSeenLabel: string | null;
  } | null;
  activeTraces: SupportWorkspaceObserverTrace[];
  errorTraces: SupportWorkspaceObserverTrace[];
  relatedTraces: SupportWorkspaceObserverTrace[];
  recentOccurrences: Array<{
    signature: string;
    message: string;
    stage: string;
    severity: string;
    timeLabel: string;
    traceUrl: string | null;
  }>;
};

export type SupportWorkspaceKnowledge = {
  similarTickets: Array<{ id: string; code: string; subject: string; summary: string }>;
  articles: Array<{ id: string; title: string; url: string }>;
  aiSummary: {
    text: string;
    sources: string[];
    confidence: string;
    sourceCount: number;
  } | null;
  diagnostics: {
    provider: string;
    providerVersion: string;
    providerStatus: string;
    providerStatusLabel: string;
    externalProviderStatus: string;
    externalProviderStatusLabel: string;
    fallbackReason: string | null;
    fallbackReasonLabel: string | null;
    catalogEntryCount: number;
    queryTokens: string[];
    sourceCounts: Record<string, number>;
    querySignals: string[];
    articleMatches: Record<string, {
      sourceType: string;
      score: number | null;
      matchReasons: string[];
    }>;
    similarTicketMatches: Record<string, {
      sourceType: string;
      score: number | null;
      matchReasons: string[];
    }>;
  };
};

export type SupportWorkspacePassport = {
  status: string;
  done: number;
  total: number;
  items: Array<{
    key: string;
    label: string;
    done: boolean;
  }>;
  openUrl: string | null;
};

export type SupportWorkspaceViewModel = {
  theme: SupportWorkspaceTheme;
  left: {
    slices: SupportWorkspaceSlice[];
    queues: SupportWorkspaceQueue[];
    tickets: SupportWorkspaceTicketItem[];
    visibleCount: number;
  };
  selectedTicket: SupportWorkspaceSelectedTicket | null;
  right: {
    context: SupportWorkspaceContext | null;
    inventoryContext: SupportTicketInventoryContext | null;
    tools: SupportWorkspaceToolItem[];
    playbooks: SupportWorkspaceToolItem[];
    operations: SupportWorkspaceOperationSummary[];
    observer: SupportWorkspaceObserverDiagnostic;
    knowledge: SupportWorkspaceKnowledge;
    passport: SupportWorkspacePassport;
  };
  raw: {
    queue?: SupportQueuePayload;
    detail?: SupportTicketDetailPayload;
    tools?: SupportTicketToolsPayload;
    playbooks?: SupportTicketPlaybooksPayload;
    passport?: SupportTicketPassportPayload;
    knowledge?: SupportTicketKnowledgeSuggestionsPayload;
    slaOla?: SupportTicketSlaOlaPayload;
    passportReadiness?: SupportTicketPassportReadinessPayload;
    closurePlan?: SupportTicketClosurePlanPayload;
    inventoryContext?: SupportTicketInventoryContext | null;
  };
};

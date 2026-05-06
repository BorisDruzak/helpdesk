import type {
  SupportQueuePayload,
  SupportTicketDetailPayload,
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
    summary: string | null;
    preview: string | null;
    steps?: Array<{
      name: string;
      status: string;
      value: string;
      details?: string | null;
    }>;
  };
  attachments: Array<Record<string, unknown>>;
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
  nextAction: SupportWorkspaceNextAction;
  timers: SupportWorkspaceTimer[];
  timeline: SupportWorkspaceTimelineItem[];
  canSendInternalNote: boolean;
};

export type SupportWorkspaceContext = {
  requester: {
    name: string;
    department: string;
    phone: string;
    email: string;
    location: string;
  };
  device: {
    id: string | null;
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
    source: string;
  };
};

export type SupportWorkspaceToolItem = {
  id: string;
  title: string;
  subtitle: string;
  riskLabel: string;
  enabled: boolean;
  requiresConsent: boolean;
};

export type SupportWorkspaceKnowledge = {
  similarTickets: Array<{ id: string; code: string; subject: string; summary: string }>;
  articles: Array<{ id: string; title: string; url: string }>;
  aiSummary: {
    text: string;
    sources: string[];
  } | null;
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
    tools: SupportWorkspaceToolItem[];
    playbooks: SupportWorkspaceToolItem[];
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
  };
};

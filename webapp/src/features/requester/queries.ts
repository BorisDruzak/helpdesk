import { useQuery, type QueryClient, type QueryKey } from "@tanstack/react-query";

import {
  fetchPublicFormPack,
  fetchRequesterBootstrap,
  fetchRequesterConsents,
  fetchRequesterDevice,
  fetchRequesterProfile,
  fetchRequesterRegistryOptions,
  fetchRequesterTicket,
  fetchRequesterTickets,
  fetchServiceCatalogCurrent,
} from "./api";
import type {
  AuthenticatedRequesterTicket,
  RequestFormPack,
  RequesterBootstrap,
  RequesterConsent,
  RequesterDeviceDetail,
  RequesterProfileDetail,
  RequesterRegistryOptionsPayload,
  RequesterTicketDetail,
  ServiceCatalogCurrent,
} from "./types";
import { formatHumanIdentifier, formatRussianDateTime, formatStatusLabel } from "../../components/ui-page";

const REQUESTER_QUERY_STALE_TIME_MS = 30_000;

type EnabledQueryOptions = {
  enabled?: boolean;
};

type RequesterNextActionKey =
  | "complete_profile"
  | "review_consents"
  | "link_device"
  | "continue_requests";

export type RequesterDashboardProjection = {
  readiness: {
    profileComplete: boolean;
    hasDeviceContext: boolean;
    canCreateWithoutDevice: boolean;
  };
  nextAction: {
    key: RequesterNextActionKey;
    label: string;
    href: string;
  };
  stats: {
    openTickets: number;
    actionsRequired: number;
    pendingConsents: number;
    devices: number;
  };
  recentTickets: Array<{
    ticketId: string;
    ticketRouteParam: string | null;
    displayCode: string;
    title: string;
    statusLabel: string;
    createdAtLabel: string;
  }>;
};

function normalizedConsentStatuses(statuses: string[] = ["pending"]): string[] {
  return Array.from(new Set(statuses.map((status) => status.trim()).filter(Boolean))).sort();
}

export const requesterQueryKeys = {
  all: ["requester"] as const,
  bootstrap: () => [...requesterQueryKeys.all, "bootstrap"] as const,
  consents: (statuses: string[] = ["pending"]) =>
    [...requesterQueryKeys.all, "consents", normalizedConsentStatuses(statuses).join(",")] as const,
  deviceDetail: (deviceId: string) => [...requesterQueryKeys.all, "device-detail", deviceId] as const,
  formPack: () => [...requesterQueryKeys.all, "form-pack", "request_forms"] as const,
  profile: () => [...requesterQueryKeys.all, "profile"] as const,
  registryOptions: () => [...requesterQueryKeys.all, "registry-options"] as const,
  serviceCatalog: () => [...requesterQueryKeys.all, "service-catalog"] as const,
  ticketDetail: (ticketId: string) => [...requesterQueryKeys.all, "ticket-detail", ticketId] as const,
  ticketList: () => [...requesterQueryKeys.all, "ticket-list"] as const,
};

async function invalidateExact(queryClient: QueryClient, queryKeys: QueryKey[]): Promise<void> {
  await Promise.all(queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey, exact: true })));
}

export const requesterInvalidations = {
  afterWorkspaceRefresh(queryClient: QueryClient): Promise<void> {
    return invalidateExact(queryClient, [
      requesterQueryKeys.bootstrap(),
      requesterQueryKeys.ticketList(),
      requesterQueryKeys.consents(["pending"]),
      requesterQueryKeys.formPack(),
      requesterQueryKeys.serviceCatalog(),
    ]);
  },
  afterTicketMutation(queryClient: QueryClient, ticketId?: string | null): Promise<void> {
    return invalidateExact(queryClient, [
      requesterQueryKeys.ticketList(),
      requesterQueryKeys.bootstrap(),
      ...(ticketId ? [requesterQueryKeys.ticketDetail(ticketId)] : []),
    ]);
  },
  afterConsentDecision(queryClient: QueryClient, ticketId?: string | null): Promise<void> {
    return invalidateExact(queryClient, [
      requesterQueryKeys.bootstrap(),
      requesterQueryKeys.ticketList(),
      requesterQueryKeys.consents(["pending"]),
      ...(ticketId ? [requesterQueryKeys.ticketDetail(ticketId)] : []),
    ]);
  },
  afterDeviceLink(queryClient: QueryClient): Promise<void> {
    return invalidateExact(queryClient, [
      requesterQueryKeys.bootstrap(),
      requesterQueryKeys.profile(),
      requesterQueryKeys.ticketList(),
    ]);
  },
  afterProfileUpdate(queryClient: QueryClient): Promise<void> {
    return invalidateExact(queryClient, [
      requesterQueryKeys.bootstrap(),
      requesterQueryKeys.profile(),
      requesterQueryKeys.ticketList(),
    ]);
  },
};

export function humanRequesterTicketCode(ticket: Pick<AuthenticatedRequesterTicket, "ticket_code" | "ticket_id">): string {
  const safeCode = String(ticket.ticket_code || "").trim();
  return safeCode || "Обращение без номера";
}

export function requesterTicketRouteParam(ticket: Pick<AuthenticatedRequesterTicket, "ticket_id" | "ticket_code">): string | null {
  const safeCode = String(ticket.ticket_code || "").trim();
  return safeCode || null;
}

export function projectRequesterDashboard(
  bootstrap: RequesterBootstrap | null | undefined,
  tickets: AuthenticatedRequesterTicket[] = [],
  consents: RequesterConsent[] = [],
): RequesterDashboardProjection {
  const visibleTickets = tickets.length ? tickets : bootstrap?.recent_tickets ?? [];
  const pendingConsents = consents.filter((consent) => consent.status === "pending");
  const profileComplete = bootstrap?.profile_completion
    ? bootstrap.profile_completion.complete !== false
    : Boolean(bootstrap?.profile);
  const canCreateWithoutDevice = bootstrap?.feature_flags?.requester_no_device_create === true;
  const hasDeviceContext = Boolean((bootstrap?.devices ?? []).length || canCreateWithoutDevice);
  const nextAction = !profileComplete
    ? {
        key: "complete_profile" as const,
        label: "Заполнить профиль",
        href: bootstrap?.profile_completion?.setup_path || "/app/requester/profile/setup",
      }
    : pendingConsents.length
      ? {
          key: "review_consents" as const,
          label: "Проверить согласия",
          href: "/app/requester/tickets",
        }
      : !hasDeviceContext
        ? {
            key: "link_device" as const,
            label: "Привязать устройство",
            href: "/app/requester/devices/link",
          }
        : {
            key: "continue_requests" as const,
            label: "Создать обращение",
            href: "/app/requester/new",
          };

  return {
    readiness: {
      profileComplete,
      hasDeviceContext,
      canCreateWithoutDevice,
    },
    nextAction,
    stats: {
      openTickets: bootstrap?.open_ticket_count ?? visibleTickets.length,
      actionsRequired: (bootstrap?.tickets_requiring_user_action_count ?? 0) + pendingConsents.length,
      pendingConsents: pendingConsents.length,
      devices: bootstrap?.devices.length ?? 0,
    },
    recentTickets: visibleTickets.map((ticket) => ({
      ticketId: ticket.ticket_id,
      ticketRouteParam: requesterTicketRouteParam(ticket),
      displayCode: humanRequesterTicketCode(ticket),
      title: ticket.title || "Без темы",
      statusLabel: ticket.requester_status_label || ticket.public_status_label || ticket.status_label || formatStatusLabel(ticket.status),
      createdAtLabel: formatRussianDateTime(ticket.created_at, { emptyText: "Дата не указана" }),
    })),
  };
}

export function useRequesterBootstrapQuery() {
  return useQuery<RequesterBootstrap>({
    queryKey: requesterQueryKeys.bootstrap(),
    queryFn: fetchRequesterBootstrap,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterTicketsQuery() {
  return useQuery<AuthenticatedRequesterTicket[]>({
    queryKey: requesterQueryKeys.ticketList(),
    queryFn: fetchRequesterTickets,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterConsentsQuery(statuses: string[] = ["pending"]) {
  const normalizedStatuses = normalizedConsentStatuses(statuses);
  return useQuery<RequesterConsent[]>({
    queryKey: requesterQueryKeys.consents(normalizedStatuses),
    queryFn: () => fetchRequesterConsents(normalizedStatuses),
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterFormPackQuery() {
  return useQuery<RequestFormPack>({
    queryKey: requesterQueryKeys.formPack(),
    queryFn: fetchPublicFormPack,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterServiceCatalogQuery() {
  return useQuery<ServiceCatalogCurrent>({
    queryKey: requesterQueryKeys.serviceCatalog(),
    queryFn: fetchServiceCatalogCurrent,
    retry: false,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterRegistryOptionsQuery(options: EnabledQueryOptions = {}) {
  return useQuery<RequesterRegistryOptionsPayload>({
    queryKey: requesterQueryKeys.registryOptions(),
    queryFn: fetchRequesterRegistryOptions,
    enabled: options.enabled ?? true,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterProfileQuery(options: EnabledQueryOptions = {}) {
  return useQuery<RequesterProfileDetail>({
    queryKey: requesterQueryKeys.profile(),
    queryFn: fetchRequesterProfile,
    enabled: options.enabled ?? true,
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterDeviceDetailQuery(deviceId: string | null | undefined, options: EnabledQueryOptions = {}) {
  return useQuery<RequesterDeviceDetail>({
    queryKey: requesterQueryKeys.deviceDetail(deviceId ?? ""),
    queryFn: () => fetchRequesterDevice(deviceId ?? ""),
    enabled: Boolean(deviceId) && (options.enabled ?? true),
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

export function useRequesterTicketDetailQuery(ticketId: string | null | undefined, options: EnabledQueryOptions = {}) {
  return useQuery<RequesterTicketDetail>({
    queryKey: requesterQueryKeys.ticketDetail(ticketId ?? ""),
    queryFn: () => fetchRequesterTicket(ticketId ?? ""),
    enabled: Boolean(ticketId) && (options.enabled ?? true),
    staleTime: REQUESTER_QUERY_STALE_TIME_MS,
  });
}

import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import {
  humanRequesterTicketCode,
  projectRequesterDashboard,
  requesterInvalidations,
  requesterQueryKeys,
  requesterTicketRouteParam,
} from "./queries";
import type { AuthenticatedRequesterTicket, RequesterBootstrap, RequesterConsent } from "./types";

describe("requester query architecture", () => {
  it("builds stable domain query keys without invalidating the requester root", async () => {
    expect(requesterQueryKeys.bootstrap()).toEqual(["requester", "bootstrap"]);
    expect(requesterQueryKeys.ticketList()).toEqual(["requester", "ticket-list"]);
    expect(requesterQueryKeys.ticketDetail("ticket-1")).toEqual(["requester", "ticket-detail", "ticket-1"]);
    expect(requesterQueryKeys.consents(["denied", "pending", ""])).toEqual(["requester", "consents", "denied,pending"]);

    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await requesterInvalidations.afterTicketMutation(queryClient, "ticket-1");

    const invalidatedKeys = invalidateSpy.mock.calls.map(([filters]) => filters?.queryKey);
    expect(invalidatedKeys).toEqual([
      requesterQueryKeys.ticketList(),
      requesterQueryKeys.bootstrap(),
      requesterQueryKeys.ticketDetail("ticket-1"),
    ]);
    expect(invalidatedKeys).not.toContainEqual(requesterQueryKeys.all);
  });

  it("projects requester readiness and hides raw UUID ticket identifiers from visible labels", () => {
    const rawUuidTicket = {
      ticket_id: "550e8400-e29b-41d4-a716-446655440000",
      title: "VPN",
      status: "waiting_user",
      created_at: "2026-06-19T08:00:00Z",
    } satisfies AuthenticatedRequesterTicket;
    const codedTicket = {
      ticket_id: "ticket-2",
      ticket_code: "REQ-2026-42",
      title: "Printer",
      status: "open",
    } satisfies AuthenticatedRequesterTicket;
    const bootstrap = {
      workspace: "requester",
      profile: null,
      profile_completion: {
        complete: false,
        status: "required",
        setup_path: "/app/requester/profile/setup",
        required_fields: [{ key: "full_name", label: "ФИО" }],
        missing_fields: [{ key: "full_name", label: "ФИО" }],
      },
      devices: [],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 2,
      tickets_requiring_user_action_count: 1,
      pending_consent_count: 1,
      recent_tickets: [rawUuidTicket],
    } satisfies RequesterBootstrap;
    const consents = [{ consent_id: "consent-1", status: "pending", subject_type: "remote_control", subject_id: "subject-1" }] satisfies RequesterConsent[];

    expect(humanRequesterTicketCode(rawUuidTicket)).toBe("Обращение без номера");
    expect(requesterTicketRouteParam(rawUuidTicket)).toBeNull();
    expect(humanRequesterTicketCode(codedTicket)).toBe("REQ-2026-42");
    expect(requesterTicketRouteParam(codedTicket)).toBe("REQ-2026-42");

    const projection = projectRequesterDashboard(bootstrap, [codedTicket], consents);
    expect(projection.readiness.profileComplete).toBe(false);
    expect(projection.readiness.hasDeviceContext).toBe(false);
    expect(projection.nextAction.key).toBe("complete_profile");
    expect(projection.stats.actionsRequired).toBe(2);
    expect(projection.recentTickets).toEqual([
      expect.objectContaining({
        displayCode: "REQ-2026-42",
        ticketRouteParam: "REQ-2026-42",
        statusLabel: "Открыта",
      }),
    ]);
  });

  it("prioritizes requester ticket action over generic create action", () => {
    const actionTicket = {
      ticket_id: "ticket-action",
      ticket_code: "REQ-2001",
      title: "Need requester answer",
      status: "waiting_on_user",
      requester_status_label: "Waiting for requester",
      next_action_owner: "requester",
    } satisfies AuthenticatedRequesterTicket;
    const bootstrap = {
      workspace: "requester",
      profile: { person_id: "person-1" },
      profile_completion: {
        complete: true,
        status: "complete",
        setup_path: "/app/requester/profile/setup",
        required_fields: [],
        missing_fields: [],
      },
      devices: [{ device_id: "device-1" }],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 1,
      tickets_requiring_user_action_count: 1,
      pending_consent_count: 0,
      recent_tickets: [actionTicket],
      feature_flags: { requester_no_device_create: false },
    } satisfies RequesterBootstrap;

    const projection = projectRequesterDashboard(bootstrap, [actionTicket], []);

    expect(projection.nextAction.key).toBe("review_ticket");
    expect(projection.nextAction.href).toBe("/app/requester/tickets/REQ-2001");
    expect(projection.nextAction.label).toBe("Ответить по обращению");
    expect(projection.stats.actionsRequired).toBe(1);
  });

  it("uses server ordered next actions from bootstrap before local create fallback", () => {
    const bootstrap = {
      workspace: "requester",
      profile: { person_id: "person-1" },
      profile_completion: {
        complete: true,
        status: "complete",
        setup_path: "/app/requester/profile/setup",
        required_fields: [],
        missing_fields: [],
      },
      devices: [{ device_id: "device-1" }],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 1,
      tickets_requiring_user_action_count: 1,
      next_actions: [
        {
          key: "review_ticket",
          label: "Ответить по обращению",
          href: "/app/requester/tickets/REQ-3001",
          ticket_code: "REQ-3001",
        },
        {
          key: "continue_requests",
          label: "Создать обращение",
          href: "/app/requester/new",
        },
      ],
      pending_consent_count: 0,
      recent_tickets: [],
      feature_flags: { requester_no_device_create: false },
    } satisfies RequesterBootstrap;

    const projection = projectRequesterDashboard(bootstrap, [], []);

    expect(projection.nextAction).toEqual({
      key: "review_ticket",
      label: "Ответить по обращению",
      href: "/app/requester/tickets/REQ-3001",
    });
  });

  it("does not let locally fetched consents override the server ordered next action", () => {
    const bootstrap = {
      workspace: "requester",
      profile: { person_id: "person-1" },
      profile_completion: {
        complete: true,
        status: "complete",
        setup_path: "/app/requester/profile/setup",
        required_fields: [],
        missing_fields: [],
      },
      devices: [{ device_id: "device-1" }],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 0,
      tickets_requiring_user_action_count: 0,
      next_actions: [
        {
          key: "continue_requests",
          label: "Создать обращение",
          href: "/app/requester/new",
        },
      ],
      pending_consent_count: 1,
      recent_tickets: [],
      feature_flags: { requester_no_device_create: false },
    } satisfies RequesterBootstrap;
    const consents = [{ consent_id: "consent-1", status: "pending", subject_type: "diagnostic", subject_id: "subject-1" }] satisfies RequesterConsent[];

    const projection = projectRequesterDashboard(bootstrap, [], consents);

    expect(projection.nextAction).toEqual({
      key: "continue_requests",
      label: "Создать обращение",
      href: "/app/requester/new",
    });
    expect(projection.stats.pendingConsents).toBe(1);
    expect(projection.stats.actionsRequired).toBe(1);
  });

  it("does not count devices or global no-device create as primary diagnostic context", () => {
    const bootstrap = {
      workspace: "requester",
      profile: { person_id: "person-1" },
      profile_completion: {
        complete: true,
        status: "complete",
        setup_path: "/app/requester/profile/setup",
        required_fields: [],
        missing_fields: [],
      },
      devices: [
        { device_id: "device-1", hostname: "WORKSTATION-1" },
        { device_id: "device-2", hostname: "WORKSTATION-2" },
      ],
      primary_device: null,
      primary_device_resolution: { status: "ambiguous", reason_code: "multiple_active_devices", candidate_count: 2 },
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 0,
      tickets_requiring_user_action_count: 0,
      pending_consent_count: 0,
      recent_tickets: [],
      feature_flags: { requester_no_device_create: true },
    } satisfies RequesterBootstrap;

    const projection = projectRequesterDashboard(bootstrap, [], []);

    expect(projection.readiness.hasDeviceContext).toBe(false);
    expect(projection.readiness.canCreateWithoutDevice).toBe(true);
    expect(projection.nextAction.key).toBe("continue_requests");
  });
});

import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import {
  humanRequesterTicketCode,
  projectRequesterDashboard,
  requesterInvalidations,
  requesterQueryKeys,
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

    expect(humanRequesterTicketCode(rawUuidTicket)).toBe("Обращение 550e8400");
    expect(humanRequesterTicketCode(codedTicket)).toBe("REQ-2026-42");

    const projection = projectRequesterDashboard(bootstrap, [codedTicket], consents);
    expect(projection.readiness.profileComplete).toBe(false);
    expect(projection.readiness.hasDeviceContext).toBe(false);
    expect(projection.nextAction.key).toBe("complete_profile");
    expect(projection.stats.actionsRequired).toBe(2);
    expect(projection.recentTickets).toEqual([
      expect.objectContaining({
        displayCode: "REQ-2026-42",
        statusLabel: "Открыта",
      }),
    ]);
  });
});

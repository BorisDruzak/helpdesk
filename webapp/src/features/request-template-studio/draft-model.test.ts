import { describe, expect, it } from "vitest";

import type { StudioDraft } from "./draft-model";
import { buildOfferingDraftPayload } from "./draft-model";

describe("request studio draft model", () => {
  it("builds a durable catalog draft payload for a new Studio request", () => {
    const draft: StudioDraft = {
      serviceCode: "it",
      offeringCode: "crm_access",
      templateCode: "crm_access",
      title: "Доступ к CRM",
      description: "Запрос прав в CRM",
      visibility: "restricted",
      processProfile: "Заявка на доступ",
      routingPolicyCode: "route_l1",
      slaPolicyCode: "sla_p2",
      approvalMode: "required",
      approvalPolicyCode: "approval_owner",
      closurePolicyCode: "closure_basic",
      notificationPolicyCode: "",
      fields: [],
    };

    expect(buildOfferingDraftPayload(draft, null)).toMatchObject({
      service_code: "it",
      code: "crm_access",
      full_code: "it.crm_access",
      public_title: "Доступ к CRM",
      lifecycle_status: "draft",
      visibility: "restricted",
      request_template_key: "crm_access",
      routing_policy_code: "route_l1",
      sla_policy_code: "sla_p2",
      approval_policy_code: "approval_owner",
      closure_policy_code: "closure_basic",
      notification_policy_code: null,
    });
  });
});

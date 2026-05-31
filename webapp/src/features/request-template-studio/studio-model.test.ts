import { describe, expect, it } from "vitest";

import type { StudioDraft } from "./draft-model";
import { buildWorkingRequestStudioItem, findDefaultStudioItem, type RequestStudioItem } from "./studio-model";

function draft(overrides: Partial<StudioDraft> = {}): StudioDraft {
  return {
    serviceCode: "it",
    offeringCode: "crm_access",
    templateCode: "crm_access",
    title: "Доступ к CRM",
    description: "Запрос прав в CRM",
    visibility: "public",
    processProfile: "Заявка на доступ",
    routingPolicyCode: "route_l1",
    slaPolicyCode: "sla_p2",
    approvalMode: "required",
    approvalPolicyCode: "approval_owner",
    closurePolicyCode: "closure_basic",
    notificationPolicyCode: "",
    fields: [
      {
        key: "system",
        label: "В какую систему?",
        type: "text",
        required: true,
        placeholder: "",
        helpText: "",
        optionsText: "",
        visibleWhenField: "",
        visibleWhenValue: "",
        processMeaning: "routing_input",
      },
    ],
    ...overrides,
  };
}

describe("request studio model", () => {
  it("builds a virtual working item from a new draft", () => {
    const item = buildWorkingRequestStudioItem({
      selectedItem: null,
      draft: draft(),
      services: [
        {
          code: "it",
          public_title: "ИТ поддержка",
          short_description: null,
          lifecycle_status: "published",
          visibility: "public",
        },
      ],
      health: undefined,
    });

    expect(item).toMatchObject({
      isVirtualDraft: true,
      draftApplied: true,
      service: { code: "it", public_title: "ИТ поддержка" },
      offering: { code: "crm_access", full_code: "it.crm_access", public_title: "Доступ к CRM" },
      template: {
        template_code: "crm_access",
        routing_policy_code: "route_l1",
        sla_policy_code: "sla_p2",
        approval_policy_code: "approval_owner",
        closure_policy_code: "closure_basic",
      },
    });
    expect(item?.formPreview?.fields[0]).toMatchObject({
      key: "system",
      label: "В какую систему?",
      required: true,
      processMapping: { roles: ["routing_input"] },
    });
  });

  it("overlays an existing item with unsaved draft values", () => {
    const selectedItem = {
      id: "service:it:offering:it.old:template:old",
      service: { code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" },
      offering: { code: "old", full_code: "it.old", service_code: "it", public_title: "Старое", lifecycle_status: "published", visibility: "public" },
      template: null,
      formPreview: null,
      processProfile: { profileName: "Простая заявка", requiredMissing: [], recommendedMissing: [], readyLabels: [], issueLabels: [] },
      processBlocks: [],
      health: null,
      isTechnical: false,
      technicalRefs: {},
    } as unknown as RequestStudioItem;

    const item = buildWorkingRequestStudioItem({
      selectedItem,
      draft: draft({ title: "Новое название", routingPolicyCode: "" }),
      services: [],
      health: undefined,
    });

    expect(item?.id).toBe(selectedItem.id);
    expect(item?.offering?.public_title).toBe("Новое название");
    expect(item?.template?.routing_policy_code).toBeNull();
    expect(item?.draftApplied).toBe(true);
  });

  it("prefers the published access scenario as default", () => {
    const smoke = { id: "smoke", isTechnical: true, service: { code: "smoke" }, offering: { lifecycle_status: "published" } } as RequestStudioItem;
    const generic = { id: "generic", isTechnical: false, service: { code: "it" }, offering: { lifecycle_status: "published" } } as RequestStudioItem;
    const access = {
      id: "access",
      isTechnical: false,
      service: { code: "access" },
      offering: { full_code: "access.grant_access", lifecycle_status: "published" },
    } as RequestStudioItem;

    expect(findDefaultStudioItem([smoke, generic, access], false)?.id).toBe("access");
  });
});

import { describe, expect, it } from "vitest";

import type { StudioDraft } from "./draft-model";
import {
  buildOfferingDraftPayload,
  buildRequestStudioPublishPayload,
  validateStudioDraftRequesterRuntime,
} from "./draft-model";
import { resolveVisibilityPolicyCode } from "./policy-resolvers";

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

    const registry = registryWithVisibility([
      { code: "visibility_default", is_active: true },
    ]);

    expect(buildOfferingDraftPayload(draft, null, registry)).toMatchObject({
      service_code: "it",
      code: "crm_access",
      full_code: "it.crm_access",
      public_title: "Доступ к CRM",
      lifecycle_status: "draft",
      visibility: "restricted",
      visibility_policy_code: "visibility_default",
      request_template_key: "crm_access",
      routing_policy_code: "route_l1",
      sla_policy_code: "sla_p2",
      approval_policy_code: "approval_owner",
      closure_policy_code: "closure_basic",
      notification_policy_code: null,
    });
  });

  it("prefers the active default visibility policy when it exists", () => {
    expect(resolveVisibilityPolicyCode(registryWithVisibility([
      { code: "visibility_team", is_active: true },
      { code: "visibility_default", is_active: true },
    ]))).toBe("visibility_default");
  });

  it("uses the first active visibility policy when no default exists", () => {
    expect(resolveVisibilityPolicyCode(registryWithVisibility([
      { code: "visibility_internal", is_active: true },
      { code: "visibility_archived", is_active: false },
    ]))).toBe("visibility_internal");
  });

  it("returns null when no active visibility policy exists", () => {
    expect(resolveVisibilityPolicyCode(registryWithVisibility([
      { code: "visibility_default", is_active: false },
    ]))).toBeNull();
    expect(buildOfferingDraftPayload(baseDraft(), null, registryWithVisibility([]))).toMatchObject({
      visibility_policy_code: null,
    });
  });

  it("rejects Studio publish when requester runtime cannot render the schema safely", () => {
    const draft = {
      ...baseDraft(),
      fields: [
        {
          key: "attachment",
          label: "Файл",
          type: "file",
          required: true,
          placeholder: "",
          helpText: "",
          optionsText: "",
          visibleWhenField: "",
          visibleWhenValue: "",
          processMeaning: "display_only",
        },
      ],
    } satisfies StudioDraft;

    expect(validateStudioDraftRequesterRuntime(draft, null)).toMatchObject({
      canPublish: false,
      issues: [expect.objectContaining({ code: "requester_file_upload_disabled" })],
    });
    expect(() => buildRequestStudioPublishPayload({ draft, registry: null })).toThrow(/requester runtime/);
  });

  it("rejects Studio publish when visible_when points to a missing field", () => {
    const draft = {
      ...baseDraft(),
      fields: [
        {
          key: "details",
          label: "Детали",
          type: "textarea",
          required: false,
          placeholder: "",
          helpText: "",
          optionsText: "",
          visibleWhenField: "missing_field",
          visibleWhenValue: "yes",
          processMeaning: "display_only",
        },
      ],
    } satisfies StudioDraft;

    expect(validateStudioDraftRequesterRuntime(draft, null).issues).toEqual(
      expect.arrayContaining([expect.objectContaining({ code: "invalid_visible_when_field" })]),
    );
    expect(() => buildRequestStudioPublishPayload({ draft, registry: null })).toThrow(/Условие/);
  });
});

function baseDraft(): StudioDraft {
  return {
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
}

function registryWithVisibility(policies: Array<{ code: string; is_active: boolean }>) {
  return {
    policies: {
      visibility: policies.map((policy) => ({
        kind: "visibility",
        table: "visibility_policies",
        code: policy.code,
        version: "1.0.0",
        title: policy.code,
        description: null,
        scope_level: "system",
        scope_ref: null,
        config: {},
        is_active: policy.is_active,
        published_at: null,
        created_at: null,
        created_by: null,
        updated_at: null,
        updated_by: null,
      })),
    },
  } as never;
}

import { describe, expect, it } from "vitest";

import {
  buildGuidedSimulationPayload,
  defaultGuidedSimulationDraft,
  offeringOptions,
  policyOptions,
  requestTemplateOptions,
  serviceOptions,
} from "./options";

describe("request template studio options", () => {
  it("maps service and offering pickers with labels, metadata and disabled states", () => {
    const services = serviceOptions([
      {
        code: "mail",
        public_title: "Почта",
        lifecycle_status: "published",
        visibility: "public",
        short_description: "Корпоративная почта",
      },
      {
        code: "old",
        public_title: "Старый сервис",
        lifecycle_status: "retired",
        visibility: "internal",
      },
    ]);
    const offerings = offeringOptions(
      [
        {
          code: "new_box",
          full_code: "mail.new_box",
          public_title: "Новый ящик",
          service_code: "mail",
          lifecycle_status: "published",
          visibility: "public",
          request_template_key: "mailbox",
        },
      ],
      "mail",
    );

    expect(services[0]).toMatchObject({ value: "mail", label: "Почта (mail)", disabled: false });
    expect(services[1]).toMatchObject({ value: "old", disabled: true, disabledReason: "Услуга выведена из каталога" });
    expect(offerings[0]).toMatchObject({ value: "mail.new_box", label: "Новый ящик (mail.new_box)" });
  });

  it("maps active templates and policies without exposing raw codes as labels only", () => {
    const registry = {
      request_templates: [
        {
          template_code: "access",
          public_title: "Доступ",
          internal_name: null,
          ticket_type: "service_request",
          version: "1.0.0",
          is_active: true,
        },
      ],
      policies: {
        routing: [
          {
            code: "route_l1",
            title: "Маршрут L1",
            version: "1.0.0",
            scope_level: "request_template",
            scope_ref: "access",
            is_active: true,
          },
        ],
      },
    };

    expect(requestTemplateOptions(registry as never)[0].label).toBe("Доступ (access)");
    expect(policyOptions(registry as never, "routing")[0].subtitle).toContain("Маршрутизация");
  });

  it("builds guided simulation payload without requiring JSON input", () => {
    const payload = buildGuidedSimulationPayload({
      ...defaultGuidedSimulationDraft,
      requester: "ivanov",
      device: "device-1",
      location: "Екатеринбург",
      serviceCode: "mail",
      offeringCode: "mail.new_box",
      answerSummary: "Нужен почтовый ящик",
      expectedPriority: "P2",
    });

    expect(payload.requester_context).toMatchObject({ requester_id: "ivanov", location: "Екатеринбург" });
    expect(payload.device_metadata).toMatchObject({ device_id: "device-1" });
    expect(payload.custom_fields).toMatchObject({ service_code: "mail", offering_code: "mail.new_box" });
    expect(payload.request_form_data).toMatchObject({ summary: "Нужен почтовый ящик", expected_priority: "P2" });
  });
});

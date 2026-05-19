import { describe, expect, it } from "vitest";

import {
  buildCatalogSimulationContext,
  buildGuidedSimulationPayload,
  buildStudioSimulationPayload,
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
  it("builds the exact Studio simulation body with top-level catalog context", () => {
    const service = {
      code: "it-support",
      public_title: "ИТ поддержка",
      lifecycle_status: "published" as const,
      visibility: "public" as const,
    };
    const offering = {
      code: "password-reset",
      full_code: "it-support.password-reset",
      public_title: "Сброс пароля",
      service_code: "it-support",
      lifecycle_status: "published" as const,
      visibility: "public" as const,
      request_template_key: "password_reset_request",
    };

    const payload = buildStudioSimulationPayload({
      selectedTemplateCode: "password_reset_request",
      selectedService: service,
      selectedOffering: offering,
      simulationDraft: {
        ...defaultGuidedSimulationDraft,
        requester: "ivanov",
        device: "device-1",
        answerSummary: "Не могу войти",
        expectedPriority: "P2",
      },
    });

    expect(payload).toMatchObject({
      template_code: "password_reset_request",
      service_code: "it-support",
      offering_code: "password-reset",
      offering_full_code: "it-support.password-reset",
      request_form_data: {
        summary: "Не могу войти",
        expected_priority: "P2",
      },
      requester_context: {
        requester_id: "ivanov",
      },
      device_metadata: {
        device_id: "device-1",
      },
    });
    expect(payload.custom_fields).toMatchObject({
      service_code: "it-support",
      offering_code: "password-reset",
    });
  });

  it("does not leak an offering from another service into Studio simulation body", () => {
    const payload = buildStudioSimulationPayload({
      selectedTemplateCode: "mailbox_request",
      selectedService: {
        code: "mail",
        public_title: "Почта",
        lifecycle_status: "published" as const,
        visibility: "public" as const,
      },
      selectedOffering: {
        code: "password-reset",
        full_code: "it-support.password-reset",
        public_title: "Сброс пароля",
        service_code: "it-support",
        lifecycle_status: "published" as const,
        visibility: "public" as const,
        request_template_key: "password_reset_request",
      },
      simulationDraft: {
        ...defaultGuidedSimulationDraft,
        serviceCode: "mail",
        offeringCode: "it-support.password-reset",
      },
    });

    expect(payload.service_code).toBe("mail");
    expect(payload.offering_code).toBeNull();
    expect(payload.offering_full_code).toBeNull();
    expect(payload.custom_fields?.offering_code).toBeUndefined();
  });

  it("builds catalog simulation context with full offering code priority", () => {
    expect(
      buildCatalogSimulationContext(
        { code: "it-support", public_title: "ИТ", lifecycle_status: "published" as const, visibility: "public" as const },
        {
          code: "password-reset",
          full_code: "it-support.password-reset",
          public_title: "Сброс пароля",
          service_code: "it-support",
          lifecycle_status: "published" as const,
          visibility: "public" as const,
        },
      ),
    ).toEqual({
      service_code: "it-support",
      offering_code: "password-reset",
      offering_full_code: "it-support.password-reset",
    });
  });
});

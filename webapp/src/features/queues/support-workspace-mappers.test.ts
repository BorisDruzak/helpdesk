import { describe, expect, it } from "vitest";

import type {
  SupportQueuePayload,
  SupportTicketKnowledgeSuggestionsPayload,
  SupportTicketPassportReadinessPayload,
  SupportTicketDetailPayload,
  SupportTicketPassportPayload,
  SupportTicketSlaOlaPayload,
} from "./api";
import {
  formatRemainingSeconds,
  mapSupportWorkspaceViewModel,
  mapWorkspaceSlices,
  mapWorkspaceTimeline,
} from "./support-workspace-mappers";

const NOW = new Date("2026-05-05T10:00:00+05:00");

function queuePayload(): SupportQueuePayload {
  return {
    scope: "all",
    query: "",
    status_filter: "all",
    smart_view: "all",
    summary: {
      visible_count: 2,
      selected_ticket_id: "ticket-1",
      scope_counts: [
        { value: "all", label: "Все доступные", count: 2 },
        { value: "mine", label: "Только мои", count: 1 },
      ],
      status_counts: [{ value: "in_progress", label: "В работе", count: 2 }],
      smart_view_counts: [
        { value: "my_action", label: "Нужен мой ответ", count: 12 },
        { value: "sla_risk", label: "Риск по сроку ответа", count: 8 },
        { value: "unassigned", label: "Без исполнителя", count: 7 },
        { value: "requester_reply", label: "Ответил пользователь", count: 15 },
      ],
      queue_counts: [{ id: 1, code: "servicedesk_l1", name: "ServiceDesk L1", count: 1 }],
    },
    filters: {
      scope_options: [
        { value: "all", label: "Все доступные" },
        { value: "mine", label: "Только мои" },
      ],
      status_options: [{ value: "in_progress", label: "В работе" }],
      smart_view_options: [
        { value: "my_action", label: "Нужен мой ответ" },
        { value: "sla_risk", label: "Риск по сроку ответа" },
        { value: "unassigned", label: "Без исполнителя" },
        { value: "requester_reply", label: "Ответил пользователь" },
      ],
    },
    tickets: [
      {
        ticket_id: "ticket-1",
        ticket_code: "T-0001042",
        title: "Не открывается сайт",
        status: "in_progress",
        status_label: "В работе",
        requester_status: "in_work",
        requester_status_label: "Заявка в работе",
        next_action_owner: "support",
        next_action_due_at: "2026-05-05T10:28:00+05:00",
        status_reason: null,
        priority: "P1",
        priority_class: "P1",
        queue_code: "ServiceDesk L1",
        assignee_id: "op1",
        assignee_display_name: "op1",
        requester_display_name: "Александр Смирнов",
        device_id: "device-1",
        updated_at: "2026-05-05T09:16:00+05:00",
        created_at: "2026-05-05T09:00:00+05:00",
        requires_operator_action: true,
        unread_user_messages: 1,
      },
    ],
  };
}

function detailPayload(status = "in_progress"): SupportTicketDetailPayload {
  return {
    ticket: {
      ticket_id: "ticket-1",
      ticket_code: "T-0001042",
      title: "Не открывается сайт",
      description: "Ошибка 502",
      status,
      status_label: status === "waiting_on_user" ? "Ждём пользователя" : "В работе",
      requester_status: "in_work",
      requester_status_label: "Заявка в работе",
      next_action_owner: null,
      next_action_due_at: "2026-05-05T10:28:00+05:00",
      status_reason: null,
      requester_display_name: "Александр Смирнов",
      device_id: "device-1",
      ticket_type: "incident",
      category_id: null,
      service_id: null,
      subcategory_id: null,
      priority: "high",
      priority_class: "P1",
      impact: 2,
      urgency: 2,
      importance: 2,
      priority_decision: {},
      first_response_due_at: "2026-05-05T10:15:00+05:00",
      resolution_due_at: "2026-05-05T14:00:00+05:00",
      queue: { id: 1, code: "servicedesk_l1", name: "ServiceDesk L1" },
      assignee_id: "op1",
      updated_at: "2026-05-05T09:16:00+05:00",
      created_at: "2026-05-05T09:00:00+05:00",
      resolution_code: null,
      resolution_summary: null,
      requester_resolution_summary: null,
      evidence_required: false,
      evidence_ref: null,
      closure_feedback: {},
      approval_summary: null,
      queue_members: [],
    },
    request_form: {
      request_kind: "incident",
      form_key: "website",
      form_title: "Не открывается сайт",
      rows: [{ key: "site", label: "Сайт", value: "site.ru" }],
    },
    observer: {
      ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
      summary: {
        ticket_id: "ticket-1",
        root_trace_id: "trace-1",
        trace_count: 1,
        active_trace_count: 0,
        error_trace_count: 0,
        signature_count: 0,
        latest_trace_at: "2026-05-05T09:20:00+05:00",
      },
    },
    timeline: [
      {
        message_id: "m1",
        event_id: 1,
        event_type: "chat_message",
        from_role: "user",
        sender_display_name: "Александр Смирнов",
        text: "Не открывается site.ru, ошибка 502.",
        ts: "2026-05-05T09:12:00+05:00",
        visibility: "public",
        direction: "from_agent",
        attachments: [],
        reply_to: null,
      },
      {
        message_id: "m2",
        event_id: 2,
        event_type: "chat_message",
        from_role: "support",
        sender_display_name: "Иван Петров",
        text: "Похоже на проблему DNS или прокси.",
        ts: "2026-05-05T09:16:00+05:00",
        visibility: "internal",
        direction: "to_agent",
        attachments: [],
        reply_to: null,
      },
      {
        message_id: null,
        event_id: 3,
        event_type: "tool_call_result",
        from_role: "system",
        sender_display_name: "Система",
        text: "Диагностика завершена",
        ts: "2026-05-05T09:18:00+05:00",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
        tool_name: "diagnose.website",
        tool_status: "failed",
        result_summary: "HTTP 502 Bad Gateway",
        result_preview: "HTTP: 502",
      },
    ],
    snapshot: {
      last_event_id: 3,
      notification_unread: 0,
      presence: {
        requester_online: false,
        support_online: true,
        agent_online: true,
      },
      device: {
        device_id: "device-1",
        hostname: "PC-SMIRNOV",
        os: "Windows 11 Pro",
        agent_version: "3.1.29",
        last_seen_at: "2026-05-05T09:55:00+05:00",
        online: true,
      },
      registry: {
        person_id: "person-1",
        person_display_name: "Александр Смирнов",
        person_phone: "+7 (495) 123-45-67",
        person_email: "a.smirnov@example.test",
        person_source: "manual",
        department_id: "department-1",
        department_name: "Отдел маркетинга",
        location_id: "location-1",
        location_display_name: "БЦ, 3 этаж, каб. 305",
        building: "БЦ",
        floor: "3",
        room: "305",
        asset_id: "asset-1",
        asset_name: "PC-SMIRNOV",
        asset_type: "pc",
        service_id: "service-1",
        service_name: "Корпоративный сайт",
      },
      latest_operations: [],
    },
    actions: {
      status_options: [{ value: "waiting_on_user", label: "Ждём пользователя" }],
      can_send_internal_note: true,
      closure_requirements: [],
      approval: null,
    },
  };
}

function passportPayload(): SupportTicketPassportPayload {
  return {
    ticket_id: "ticket-1",
    status: "draft",
    passport: null,
    requirements: {
      required_sections: ["problem", "root_cause", "solution", "verification"],
      require_official_passport: true,
      missing_facts: [
        {
          required_fact: "root_cause",
          section_key: "cause",
          source: "passport",
          current_value: null,
          requester_visible_label: "Причина установлена",
          severity: "warning",
        },
      ],
      missing_count: 1,
      blocking_missing_count: 1,
      export_preview: {},
      knowledge_draft_hints: {},
    },
    evidence: [],
    actions: [],
    approvals: [],
    related_objects: [],
  };
}

function slaOlaPayload(): SupportTicketSlaOlaPayload {
  return {
    first_response: {
      due_at: "2026-05-05T10:20:00+05:00",
      remaining_seconds: 1200,
      target_seconds: 1800,
      status: "at_risk",
    },
    resolution: {
      due_at: "2026-05-05T14:00:00+05:00",
      remaining_seconds: 14400,
      target_seconds: 18000,
      status: "ok",
    },
    ola_ack: {
      due_at: "2026-05-05T09:55:00+05:00",
      remaining_seconds: -300,
      target_seconds: 900,
      status: "breached",
    },
    ola_processing: {
      due_at: "2026-05-05T10:45:00+05:00",
      remaining_seconds: 2700,
      target_seconds: 3600,
      status: "ok",
    },
  };
}

function passportReadinessPayload(): SupportTicketPassportReadinessPayload {
  return {
    ticket_id: "ticket-1",
    status: "draft",
    done: 1,
    total: 4,
    items: [
      { key: "problem_identified", label: "Проблема идентифицирована", status: "done" },
      { key: "cause_found", label: "Причина установлена", status: "pending" },
      { key: "solution_applied", label: "Решение применено", status: "pending" },
      { key: "verified_and_closed", label: "Проверка и закрытие", status: "pending" },
    ],
  };
}

function knowledgePayload(): SupportTicketKnowledgeSuggestionsPayload {
  return {
    ticket_id: "ticket-1",
    similar_tickets: [
      {
        id: "ticket-1011",
        number: "T-001011",
        subject: "РћС€РёР±РєР° 502",
        resolution_summary: "РџРµСЂРµР·Р°РїСѓСЃРє upstream.",
      },
    ],
    articles: [{ id: "KB-502", title: "РћС€РёР±РєР° 502 Bad Gateway", url: "/app/knowledge/KB-502" }],
    ai_summary: {
      text: "AI-рекомендация / Бета: проверьте источники перед применением.",
      sources: ["KB-502", "T-001011"],
      confidence: "high",
      source_count: 2,
    },
    diagnostics: {
      provider: "support_knowledge_provider",
      provider_version: "local-v1",
      provider_status: "ok",
      external_provider_status: "not_configured",
      fallback_reason: null,
      catalog_entry_count: 5,
      query_tokens: ["502", "gateway"],
      source_counts: { manual_kb: 1, catalog: 0, similar_ticket: 1 },
      query_signals: ["manual_link", "linked_ticket"],
      article_matches: {
        "KB-502": { source_type: "manual_kb", score: 100, match_reasons: ["manual_link"] },
      },
      similar_ticket_matches: {
        "ticket-1011": { source_type: "similar_ticket", score: 90, match_reasons: ["linked_ticket"] },
      },
    },
  };
}

describe("support workspace mappers", () => {
  it("maps canonical work slices from support queue counts", () => {
    const slices = mapWorkspaceSlices(queuePayload(), "sla_risk");

    expect(slices.map((slice) => [slice.id, slice.label, slice.count, slice.active])).toEqual([
      ["my_action", "Нужен ответ", 12, false],
      ["sla_risk", "SLA риск", 8, true],
      ["unassigned", "Без исполнителя", 7, false],
      ["requester_reply", "Ответил пользователь", 15, false],
    ]);
  });

  it("keeps workspace slices stable for older queue payloads without smart view counts", () => {
    const queue = queuePayload() as unknown as {
      filters?: { smart_view_options?: SupportQueuePayload["filters"]["smart_view_options"] };
      summary?: { smart_view_counts?: SupportQueuePayload["summary"]["smart_view_counts"] };
    };
    delete queue.filters?.smart_view_options;
    delete queue.summary?.smart_view_counts;

    const slices = mapWorkspaceSlices(queue as SupportQueuePayload, "all");

    expect(slices.map((slice) => [slice.id, slice.label, slice.count])).toEqual([
      ["my_action", "Нужен ответ", 0],
      ["sla_risk", "SLA риск", 0],
      ["unassigned", "Без исполнителя", 0],
      ["requester_reply", "Ответил пользователь", 0],
    ]);
  });

  it("derives next action owner and countdown from status and due dates", () => {
    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "my_action",
      detail: detailPayload("waiting_on_user"),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.selectedTicket?.nextAction.owner).toBe("requester");
    expect(viewModel.selectedTicket?.nextAction.ownerLabel).toBe("Пользователь");
    expect(viewModel.selectedTicket?.nextAction.remainingSeconds).toBe(1680);
    expect(viewModel.selectedTicket?.nextAction.remainingLabel).toBe("28 мин");
  });

  it("classifies timeline messages, internal notes and diagnostics", () => {
    const timeline = mapWorkspaceTimeline(detailPayload());

    expect(timeline.map((item) => item.kind)).toEqual(["message", "internal", "diagnostics"]);
    expect(timeline[2].operation).toMatchObject({
      name: "diagnose.website",
      statusLabel: "Ошибка",
      statusTone: "danger",
      summary: "HTTP 502 Bad Gateway",
      preview: "HTTP: 502",
    });
  });

  it("maps normalized backend timeline categories and operation steps", () => {
    const detail = detailPayload();
    detail.timeline = [
      {
        message_id: null,
        event_id: 4,
        event_type: "sla_breached",
        event_category: "sla",
        event_label: "SLA breached",
        event_details: { timer_type: "resolution" },
        from_role: "system",
        sender_display_name: "System",
        text: "SLA breached",
        ts: "2026-05-05T09:20:00+05:00",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
      },
      {
        message_id: null,
        event_id: 5,
        event_type: "tool_call_result",
        event_category: "diagnostics",
        event_label: "Tool result",
        event_details: {},
        from_role: "system",
        sender_display_name: "System",
        text: "Diagnostic result",
        ts: "2026-05-05T09:21:00+05:00",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
        tool_name: "diagnose.website",
        tool_status: "succeeded",
        result_summary: "HTTP 502 Bad Gateway",
        result_preview: null,
        operation_id: "op-timeline-1",
        trace_id: "trace-timeline-1",
        duration_ms: 1253,
        retry_count: 0,
        max_retries: 2,
        retryable: false,
        error_code: null,
        error_category: null,
        details_url: "/api/operations/op-timeline-1",
        operation_steps: [
          { name: "DNS", status: "ok", value: "site.example -> 192.0.2.10" },
          { name: "HTTP", status: "error", value: "502 Bad Gateway", details: "Upstream returned an invalid gateway response." },
        ],
      },
    ];

    const timeline = mapWorkspaceTimeline(detail);

    expect(timeline[0]).toMatchObject({
      kind: "history",
      title: "SLA breached",
      tone: "danger",
    });
    expect(timeline[1].operation?.steps).toEqual([
      { name: "DNS", status: "ok", value: "site.example -> 192.0.2.10" },
      { name: "HTTP", status: "error", value: "502 Bad Gateway", details: "Upstream returned an invalid gateway response." },
    ]);
    expect(timeline[1].operation).toMatchObject({
      statusLabel: "Успешно",
      statusTone: "success",
      metaLabels: expect.arrayContaining(["Длительность: 1 s", "Повторы: 0/2", "Трасса операции: trace-ti...", "Детали API"]),
    });
  });

  it("maps renderable tool result payload and presentation schema for diagnostics timeline", () => {
    const detail = detailPayload();
    const presentationSchema = {
      version: "1.0",
      kind: "tool_result",
      blocks: [{ type: "field_grid", fields: [{ path: "hostname", label: "Host" }] }],
    };
    detail.timeline = [
      {
        message_id: null,
        event_id: 18,
        event_type: "tool_call_result",
        event_category: "diagnostics",
        event_label: "Tool result",
        event_details: {},
        requester_timeline_text: null,
        requester_timeline_kind: null,
        requester_timeline_payload: null,
        requester_timeline_icon: null,
        requester_timeline_style: null,
        from_role: "system",
        sender_display_name: "System",
        text: "Tool finished",
        ts: "2026-05-18T10:00:00Z",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
        tool_name: "system.collect",
        tool_status: "success",
        result_summary: "Collected",
        result_preview: null,
        result_payload: { hostname: "pc-01" },
        result_presentation_schema: presentationSchema,
        result_presentation_schema_source: "server_override",
        operation_id: "op-18",
        trace_id: null,
        duration_ms: 100,
        retry_count: null,
        max_retries: null,
        retryable: false,
        can_retry: false,
        can_cancel: false,
        retry_url: null,
        cancel_url: null,
        retry_disabled_reason: null,
        cancel_disabled_reason: null,
        error_code: null,
        error_category: null,
        details_url: "/api/operations/op-18",
        operation_steps: [],
      },
    ];

    const timeline = mapWorkspaceTimeline(detail);

    expect(timeline[0].operation?.resultPayload).toEqual({ hostname: "pc-01" });
    expect(timeline[0].operation?.presentationSchema).toEqual(presentationSchema);
    expect(timeline[0].operation?.presentationSchemaSource).toBe("server_override");
  });

  it("prefers requester timeline projection over raw backend event text", () => {
    const detail = detailPayload();
    detail.timeline = [
      {
        message_id: null,
        event_id: 6,
        event_type: "status_changed",
        event_category: "history",
        event_label: "Status changed",
        event_details: { status: "unknown" },
        requester_timeline_text: "Статус обращения обновлён.",
        requester_timeline_kind: "system_event",
        requester_timeline_payload: {},
        from_role: "system",
        sender_display_name: "System",
        text: "status_changed unknown",
        ts: "2026-05-05T09:25:00+05:00",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
      },
    ];

    const timeline = mapWorkspaceTimeline(detail);

    expect(timeline[0].body).toBe("Статус обращения обновлён.");
    expect(timeline[0].title).toBe("Системное событие");
    expect(timeline[0].body).not.toContain("status_changed");
    expect(timeline[0].body).not.toContain("unknown");
  });

  it("maps operation summaries and unavailable tool/playbook reasons", () => {
    const detail = detailPayload();
    detail.snapshot.device.online = false;
    detail.snapshot.latest_operations = [
      {
        operation_id: "op-running",
        kind: "tool",
        status: "running",
        display_status: null,
        display_label: null,
        scope: "ticket",
        tool_name: "dns.resolve",
        command_name: null,
        queued_at: "2026-05-05T09:59:00+05:00",
        started_at: "2026-05-05T09:59:01+05:00",
        finished_at: null,
        duration_ms: 1253,
        trace_id: "trace-running-1",
        trace_relation: "operation_child",
        trace_url: "/app/admin/observer?trace_id=trace-running-1",
        root_trace_id: "trace-root-1",
        root_trace_url: "/app/admin/observer?trace_id=trace-root-1",
        retry_of_operation_id: null,
        retry_source_trace_id: null,
        retry_count: 0,
        max_retries: 3,
        retryable: false,
        can_retry: false,
        can_cancel: true,
        retry_url: null,
        cancel_url: "/api/operations/op-running/cancel",
        retry_disabled_reason: "status_not_retryable",
        cancel_disabled_reason: null,
        policy_labels: ["cancel:available"],
        error_code: null,
        error_category: null,
        details_url: "/api/operations/op-running",
        result_summary: null,
        error_message: null,
      },
      {
        operation_id: "op-failed",
        kind: "tool",
        status: "failed",
        display_status: null,
        display_label: "HTTP check",
        scope: "ticket",
        tool_name: "diagnose.website",
        command_name: null,
        queued_at: "2026-05-05T09:40:00+05:00",
        started_at: "2026-05-05T09:40:01+05:00",
        finished_at: "2026-05-05T09:41:00+05:00",
        duration_ms: 59000,
        trace_id: "trace-failed-1",
        trace_relation: "retry_child",
        trace_url: "/app/admin/observer?trace_id=trace-failed-1",
        root_trace_id: "trace-root-1",
        root_trace_url: "/app/admin/observer?trace_id=trace-root-1",
        retry_of_operation_id: "op-source",
        retry_source_trace_id: "trace-source-1",
        retry_count: 1,
        max_retries: 3,
        retryable: true,
        can_retry: true,
        can_cancel: false,
        retry_url: "/api/operations/op-failed/retry",
        cancel_url: null,
        retry_disabled_reason: null,
        cancel_disabled_reason: "already_finished",
        policy_labels: ["cancel:already_finished", "retry:available", "consent:required"],
        error_code: "HTTP_502",
        error_category: "execution",
        details_url: "/api/operations/op-failed",
        result_summary: null,
        error_message: "HTTP 502",
      },
    ];

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      tools: {
        ticket_id: "ticket-1",
        device_id: "device-1",
        tools: [
          {
            tool_name: "dns.resolve",
            module_name: "network",
            description: "Проверка DNS",
            domain: "network",
            tool_kind: "diagnostic",
            risk_level: "low",
            requires_consent: false,
            install_required: false,
            required_permission: "module.tool.run.low_risk",
            allowed_roles: ["support", "admin"],
            policy_labels: ["permission:module.tool.run.low_risk", "roles:support,admin", "consent:not_required"],
            source: "agent",
            params_schema: [],
            presets: [],
          },
        ],
      },
      playbooks: {
        ticket_id: "ticket-1",
        device_id: "device-1",
        playbooks: [
          {
            playbook_version_id: 1,
            key: "diagnose.website",
            name: "Диагностика сайта",
            domain: "network",
            version: "1.0",
            status: "published",
            blocks_count: 3,
            required_tools: ["dns.resolve", "http.check"],
            missing_tools: ["http.check"],
            missing_params: [],
            can_run: false,
            readiness_label: "Нет инструментов",
            updated_at: null,
          },
        ],
      },
      now: NOW,
    });

    expect(viewModel.right.tools[0]).toMatchObject({
      kind: "tool",
      enabled: false,
      disabledReason: "Агент устройства offline",
      metaLabels: expect.arrayContaining([
        "Риск: низкий",
        "Согласие не требуется",
        "Право: запуск безопасных инструментов",
        "Роли: support, admin",
        "Домен: network",
      ]),
    });
    expect(viewModel.right.playbooks[0]).toMatchObject({
      kind: "playbook",
      enabled: false,
      disabledReason: "Нет инструмента: http.check",
    });
    expect(viewModel.right.operations[0]).toMatchObject({
      title: "dns.resolve",
      statusLabel: "Выполняется",
      statusTone: "info",
      active: true,
      canCancel: true,
      cancelUrl: "/api/operations/op-running/cancel",
      traceRelation: "operation_child",
      traceRelationLabel: "Трасса операции",
      traceUrl: "/app/admin/observer?trace_id=trace-running-1",
      rootTraceUrl: "/app/admin/observer?trace_id=trace-root-1",
      metaLabels: expect.arrayContaining(["Длительность: 1 s", "Повторы: 0/3", "Трасса операции: trace-ru...", "Детали API"]),
    });
    expect(viewModel.right.operations[1]).toMatchObject({
      title: "diagnose.website",
      statusLabel: "Ошибка",
      statusTone: "danger",
      active: false,
      canRetry: true,
      requiresConsentForRetry: true,
      retryDisabledReason: null,
      traceRelation: "retry_child",
      traceRelationLabel: "Повтор операции",
      retryOfOperationId: "op-source",
      retrySourceTraceId: "trace-source-1",
      summary: "HTTP 502",
      metaLabels: expect.arrayContaining([
        "Длительность: 59 s",
        "Повтор: 1/3 доступен",
        "Требуется согласие",
        "Код: HTTP_502",
        "Категория: Выполнение",
      ]),
    });
  });

  it("maps compact observer diagnostics for the support workspace", () => {
    const detail = detailPayload();
    detail.observer = {
      ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
      summary: {
        ticket_id: "ticket-1",
        root_trace_id: "trace-root-1",
        root_trace_url: "/app/admin/observer?trace_id=trace-root-1",
        root_trace_status: "running",
        root_kind: "ticket",
        trace_count: 4,
        active_trace_count: 1,
        error_trace_count: 2,
        signature_count: 1,
        latest_trace_at: "2026-05-05T09:25:00+05:00",
        latest_error_at: "2026-05-05T09:24:00+05:00",
        latest_error_label: "HTTP 502 Bad Gateway",
        latest_error_stage: "http.check",
        health_label: "error",
        top_signature: {
          error_signature: "HTTP_502",
          title: "HTTP 502",
          severity: "error",
          ticket_occurrences_count: 2,
          global_occurrences_count: 9,
          last_seen_at: "2026-05-05T09:24:00+05:00",
        },
      },
      root_trace: {
        trace_id: "trace-root-1",
        root_kind: "ticket",
        status: "running",
        title: "Ticket root",
        started_at: "2026-05-05T09:00:00+05:00",
        finished_at: null,
        error_count: 0,
        operation_id: null,
        tool_name: null,
        playbook_id: null,
        trace_url: "/app/admin/observer?trace_id=trace-root-1",
      },
      related_traces: [],
      active_traces: [
        {
          trace_id: "trace-op-running",
          root_kind: "tool_call",
          status: "running",
          title: "dns.resolve",
          started_at: "2026-05-05T09:21:00+05:00",
          finished_at: null,
          error_count: 0,
          operation_id: "op-running",
          tool_name: "dns.resolve",
          playbook_id: null,
          trace_url: "/app/admin/observer?trace_id=trace-op-running",
        },
      ],
      error_traces: [
        {
          trace_id: "trace-op-failed",
          root_kind: "tool_call",
          status: "failed",
          title: "diagnose.website",
          started_at: "2026-05-05T09:20:00+05:00",
          finished_at: "2026-05-05T09:24:00+05:00",
          error_count: 1,
          operation_id: "op-failed",
          tool_name: "diagnose.website",
          playbook_id: null,
          trace_url: "/app/admin/observer?trace_id=trace-op-failed",
        },
      ],
      signatures: [],
      recent_occurrences: [
        {
          error_signature: "HTTP_502",
          message: "HTTP 502 Bad Gateway",
          stage: "http.check",
          severity: "error",
          trace_id: "trace-op-failed",
          created_at: "2026-05-05T09:24:00+05:00",
          trace_url: "/app/admin/observer?trace_id=trace-op-failed",
        },
      ],
    };

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.observer).toMatchObject({
      healthLabel: "Есть ошибки",
      healthTone: "danger",
      rootTraceCompactId: "trace-root-1",
      rootTraceUrl: "/app/admin/observer?trace_id=trace-root-1",
      rootTraceStatusLabel: "В работе",
      latestErrorLabel: "HTTP 502 Bad Gateway",
      latestErrorStage: "http.check",
      traceCount: 4,
      activeTraceCount: 1,
      errorTraceCount: 2,
      signatureCount: 1,
      topSignature: {
        title: "HTTP 502",
        ticketOccurrences: 2,
        globalOccurrences: 9,
      },
      errorTraces: [
        expect.objectContaining({
          compactId: "trace-op...",
          statusLabel: "Ошибка",
          traceUrl: "/app/admin/observer?trace_id=trace-op-failed",
        }),
      ],
    });
  });

  it("maps requester contact fields from registry snapshot", () => {
    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail: detailPayload(),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.context?.requester).toMatchObject({
      name: "Александр Смирнов",
      department: "Отдел маркетинга",
      phone: "+7 (495) 123-45-67",
      email: "a.smirnov@example.test",
      location: "БЦ, 3 этаж, каб. 305",
      sourceLabel: "Профиль: ручной ввод",
    });
    expect(viewModel.right.context?.device).toMatchObject({
      assetId: "asset-1",
      assetTypeLabel: "ПК",
    });
    expect(viewModel.right.context?.classification).toMatchObject({
      category: "Не указана",
      service: "Корпоративный сайт",
      similarTicketsCount: 0,
    });
  });

  it("maps verified other-account warning context", () => {
    const detail = detailPayload();
    detail.ticket.requester_account_warning = "ticket_created_from_other_account_on_registered_device";
    detail.ticket.requester_account_context = {
      warning: "ticket_created_from_other_account_on_registered_device",
      verification_status: "verified",
      verification_method: "admin_approval",
      active_device_person_name: "Registered Owner",
      declared_account: {
        full_name: "Temporary User",
        login: "temp.user",
        email: "temp@example.test",
        phone: "+15551234567",
        reason: "Shift replacement",
      },
    };

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.context?.requester).toMatchObject({
      accountWarning: "ticket_created_from_other_account_on_registered_device",
      accountDeclaredName: "Temporary User",
      accountLogin: "temp.user",
      accountReason: "Shift replacement",
      accountVerification: "admin_approval / verified",
      activeDeviceOwner: "Registered Owner",
    });
  });

  it("builds passport readiness from missing facts", () => {
    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail: detailPayload(),
      passport: passportPayload(),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.passport.done).toBe(3);
    expect(viewModel.right.passport.total).toBe(4);
    expect(viewModel.right.passport.items.find((item) => item.key === "cause_found")?.done).toBe(false);
  });

  it("prefers compact SLA/OLA and passport readiness DTOs when present", () => {
    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail: detailPayload(),
      passport: passportPayload(),
      passportReadiness: passportReadinessPayload(),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      slaOla: slaOlaPayload(),
      now: NOW,
    });

    expect(viewModel.selectedTicket?.timers.map((timer) => [timer.key, timer.status, timer.remainingSeconds])).toEqual([
      ["first_response", "at_risk", 1200],
      ["resolution", "ok", 14400],
      ["ola_ack", "breached", -300],
      ["ola_processing", "ok", 2700],
    ]);
    expect(viewModel.right.passport.done).toBe(1);
    expect(viewModel.right.passport.total).toBe(4);
    expect(viewModel.right.passport.items.map((item) => [item.key, item.done])).toEqual([
      ["problem_identified", true],
      ["cause_found", false],
      ["solution_applied", false],
      ["verified_and_closed", false],
    ]);
  });

  it("maps actionable closure plan from the aggregate workspace payload", () => {
    const detail = detailPayload();
    detail.actions.closure_requirements = [
      {
        key: "resolution_code",
        label: "Код решения",
        met: false,
        detail: "Укажите код решения.",
        candidate_count: 0,
      },
      {
        key: "priority_evidence",
        label: "Доказательство для P0",
        met: false,
        detail: "Нужно приложить evidence.",
        candidate_count: 2,
      },
    ];

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      closurePlan: {
        ticket_id: "ticket-1",
        ready_for_resolution: false,
        missing_count: 2,
        total: 2,
        evidence_candidate_count: 2,
        recommended_next_action: "Добавить evidence",
        blockers: [
          {
            key: "priority_evidence",
            label: "Доказательство для P0",
            met: false,
            detail: "Нужно приложить evidence.",
            source: "closure_requirement",
            action_kind: "attach_evidence",
            action_label: "Добавить evidence",
            severity: "blocking",
            candidate_count: 2,
            fact_key: null,
            blocking_for_closure: true,
          },
        ],
      },
      now: NOW,
    });

    expect(viewModel.selectedTicket?.closurePlan).toMatchObject({
      readyForResolution: false,
      missingCount: 2,
      total: 2,
      evidenceCandidateCount: 2,
      recommendedNextAction: "Добавить evidence",
      blockers: [
        {
          key: "priority_evidence",
          actionKind: "attach_evidence",
          actionLabel: "Добавить evidence",
          candidateCount: 2,
        },
      ],
    });
  });

  it("maps typed knowledge suggestions into the right sidebar model", () => {
    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail: detailPayload(),
      knowledge: knowledgePayload(),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.knowledge.articles).toEqual([
      { id: "KB-502", title: "РћС€РёР±РєР° 502 Bad Gateway", url: "/app/knowledge/KB-502" },
    ]);
    expect(viewModel.right.knowledge.similarTickets[0]).toEqual({
      id: "ticket-1011",
      code: "T-001011",
      subject: "РћС€РёР±РєР° 502",
      summary: "РџРµСЂРµР·Р°РїСѓСЃРє upstream.",
    });
    expect(viewModel.right.knowledge.aiSummary?.sources).toEqual(["KB-502", "T-001011"]);
    expect(viewModel.right.knowledge.aiSummary?.confidence).toBe("high");
    expect(viewModel.right.knowledge.diagnostics.sourceCounts).toEqual({ manual_kb: 1, catalog: 0, similar_ticket: 1 });
    expect(viewModel.right.knowledge.diagnostics.providerStatus).toBe("ok");
    expect(viewModel.right.knowledge.diagnostics.providerStatusLabel).toBe("готов");
    expect(viewModel.right.knowledge.diagnostics.externalProviderStatus).toBe("not_configured");
    expect(viewModel.right.knowledge.diagnostics.externalProviderStatusLabel).toBe("не подключена");
    expect(viewModel.right.knowledge.diagnostics.fallbackReasonLabel).toBeNull();
    expect(viewModel.right.knowledge.diagnostics.catalogEntryCount).toBe(5);
    expect(viewModel.right.knowledge.diagnostics.queryTokens).toEqual(["502", "gateway"]);
    expect(viewModel.right.knowledge.diagnostics.querySignals).toEqual(["manual_link", "linked_ticket"]);
    expect(viewModel.right.knowledge.diagnostics.articleMatches["KB-502"]).toEqual({
      sourceType: "manual_kb",
      score: 100,
      matchReasons: ["manual_link"],
    });
  });

  it("moves next action away from the first response timer after support reply", () => {
    const detail = detailPayload();
    detail.ticket.first_response_at = "2026-05-05T10:05:00+05:00";
    detail.ticket.next_action_due_at = detail.ticket.first_response_due_at;

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      slaOla: slaOlaPayload(),
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.selectedTicket?.nextAction.dueAt).toBe("2026-05-05T14:00:00+05:00");
    expect(viewModel.selectedTicket?.nextAction.timerType).toBe("sla");
    expect(viewModel.selectedTicket?.nextAction.hint).toBe("Продолжить диагностику или подготовить решение");
  });

  it("keeps observer trace links in the support admin observer surface", () => {
    const detail = detailPayload();
    detail.observer.summary = {
      ...detail.observer.summary,
      root_trace_id: "trace-root-1",
      root_trace_url: "/app/tickets/ticket-1",
    };
    detail.observer.related_traces = [
      {
        trace_id: "trace-child-1",
        root_kind: "operation",
        status: "ok",
        title: "Tool trace",
        trace_url: "/app/tickets/ticket-1",
        started_at: "2026-05-05T09:20:00+05:00",
        finished_at: "2026-05-05T09:21:00+05:00",
        error_count: 0,
      },
    ];

    const viewModel = mapSupportWorkspaceViewModel({
      activeQueueId: null,
      activeSmartView: "all",
      detail,
      queue: queuePayload(),
      selectedTicketId: "ticket-1",
      now: NOW,
    });

    expect(viewModel.right.observer.rootTraceUrl).toBe("/app/admin/observer?trace_id=trace-root-1");
    expect(viewModel.right.observer.relatedTraces[0]?.traceUrl).toBe("/app/admin/observer?trace_id=trace-child-1");
  });

  it("formats overdue timers explicitly", () => {
    expect(formatRemainingSeconds(-90)).toBe("Просрочено на 1 мин");
  });
});

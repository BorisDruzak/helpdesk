import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  TicketApprovalsPanel,
  TicketAutomationPanel,
  TicketPassportPanel,
  TicketRequestFormCard,
  TicketStatusActionPanel,
  TicketWorkVisibilityCard,
} from "./detail-page";

describe("TicketRequestFormCard", () => {
  it("renders structured request form data", () => {
    render(
      <TicketRequestFormCard
        requestForm={{
          request_kind: "printer",
          form_key: "printer",
          form_title: "Печать / принтер",
          rows: [
            { key: "room", label: "Кабинет", value: "214" },
            { key: "printer_model", label: "Модель", value: "HP LaserJet Pro M404" },
            { key: "printer_number", label: "Номер принтера", value: "PRN-214-01" },
          ],
        }}
      />,
    );

    expect(screen.getByText("Данные формы")).toBeInTheDocument();
    expect(screen.getByText("Печать / принтер")).toBeInTheDocument();
    expect(screen.getByText("request_kind")).toBeInTheDocument();
    expect(screen.getAllByText("printer").length).toBeGreaterThan(0);
    expect(screen.getByText("HP LaserJet Pro M404")).toBeInTheDocument();
    expect(screen.getByText("PRN-214-01")).toBeInTheDocument();
  });
});

describe("TicketPassportPanel", () => {
  const passportPayload = {
    ticket_id: "ticket-1",
    status: "draft",
    passport: {
      passport_id: 1,
      ticket_id: "ticket-1",
      version: 2,
      status: "draft",
      summary_source: "deterministic",
      generated_at: "2026-04-26T13:00:00Z",
      generated_by: "op1",
      updated_at: "2026-04-26T13:00:00Z",
      updated_by: "op1",
      sections: {
        requester: "Иванов Иван, кабинет 214",
        problem: "Не печатает принтер",
        affected_object: "Принтер HP",
        automated_checks: "system.collect: успешно",
        operator_checks: "Проверена очередь печати",
        changes_made: "Перезапущена служба печати",
        approvals: "Согласования не требовались",
        evidence: "operation-1",
        user_result: "Печать восстановлена",
        internal_result: "Ошибка драйвера",
        repeat_guidance: "При повторе приложить скриншот",
      },
      source_event_ids: [1],
      source_operation_ids: ["operation-1"],
      source_payload: {
        current_source_counts: {
          events: 2,
          operations: 1,
          worklogs: 1,
        },
        stale_reasons: ["events_changed", "worklogs_changed"],
      },
      stale: false,
    },
    evidence: [
      {
        id: 1,
        ticket_id: "ticket-1",
        passport_id: 1,
        evidence_type: "diagnostic_result",
        source_ref: "operation:operation-1",
        source_kind: "operation",
        source_id: "operation-1",
        required_fact: "evidence",
        section_key: "evidence",
        title: "HTTP проверка",
        summary: "HTTP 200 OK",
        visibility: "internal",
        verification_status: "accepted",
        export_visibility: "internal",
        created_by: "op1",
        created_at: "2026-04-26T13:01:00Z",
      },
    ],
    actions: [],
    approvals: [],
    related_objects: [],
  };

  it("renders missing passport action", () => {
    render(
      <TicketPassportPanel
        isGenerating={false}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={{ ticket_id: "ticket-1", status: "missing", passport: null, evidence: [], actions: [], approvals: [], related_objects: [] }}
      />,
    );

    expect(screen.getByText("Собрать паспорт")).toBeInTheDocument();
  });

  it("renders official passport sections and actions", () => {
    render(
      <TicketPassportPanel
        isGenerating={false}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={passportPayload}
      />,
    );

    expect(screen.getByText("Паспорт решения")).toBeInTheDocument();
    expect(screen.getByText("Кто и откуда обратился")).toBeInTheDocument();
    expect(screen.getByText("Что произошло")).toBeInTheDocument();
    expect(screen.getByText("Что проверили автоматически")).toBeInTheDocument();
    expect(screen.getByText("Что изменили")).toBeInTheDocument();
    expect(screen.getByText("Чем подтверждено решение")).toBeInTheDocument();
    expect(screen.getByText("Обновить по последним действиям")).toBeInTheDocument();
    expect(screen.getByText("Печать / PDF")).toBeInTheDocument();
    expect(screen.getByText("Сохранить как черновик знания")).toBeInTheDocument();
  });
  it("renders passport missing facts and export preview", () => {
    render(
      <TicketPassportPanel
        isGenerating={false}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={{
          ...passportPayload,
          requirements: {
            required_sections: ["problem", "evidence", "user_result"],
            require_official_passport: true,
            missing_facts: [
              {
                required_fact: "evidence",
                source: "ticket_evidence_items",
                current_value: null,
                requester_visible_label: "Доказательство решения",
                severity: "blocking",
                candidate_count: 1,
                recommended_actions: ["Привяжите результат диагностики."],
                source_candidates: [
                  {
                    candidate_id: "operation:operation-1",
                    source_kind: "operation",
                    title: "HTTP проверка",
                    summary: "HTTP 200 OK",
                  },
                ],
              },
              {
                required_fact: "user_result",
                source: "ticket.requester_resolution_summary",
                current_value: null,
                requester_visible_label: "Итог для пользователя",
                severity: "blocking",
              },
            ],
            missing_count: 2,
            blocking_missing_count: 2,
            export_preview: {
              visible_sections: ["problem", "evidence", "user_result"],
              hidden_sections: ["internal_result"],
            },
            knowledge_draft_hints: { enabled: true, source: "passport" },
          },
        }}
      />,
    );

    expect(screen.getByText("Требования паспорта")).toBeInTheDocument();
    expect(screen.getByText("2 блокирующих факта")).toBeInTheDocument();
    expect(screen.getByText("Доказательство решения")).toBeInTheDocument();
    expect(screen.getByText("Источник: доказательства тикета")).toBeInTheDocument();
    expect(screen.getByText("Привяжите результат диагностики.")).toBeInTheDocument();
    expect(screen.getByText("Кандидаты: 1")).toBeInTheDocument();
    expect(screen.getAllByText("HTTP проверка").length).toBeGreaterThan(0);
    expect(screen.getByText("Экспорт")).toBeInTheDocument();
    expect(screen.getByText("Скрыто: internal_result")).toBeInTheDocument();
  });

  it("renders stale warning and evidence dossier rows", () => {
    render(
      <TicketPassportPanel
        isGenerating={false}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={{
          ...passportPayload,
          passport: {
            ...passportPayload.passport,
            stale: true,
          },
        }}
      />,
    );

    expect(screen.getByText("Паспорт устарел")).toBeInTheDocument();
    expect(screen.getByText("Новые сообщения или события")).toBeInTheDocument();
    expect(screen.getByText("Новый worklog")).toBeInTheDocument();
    expect(screen.getByText("Доказательства паспорта")).toBeInTheDocument();
    expect(screen.getByText("HTTP проверка")).toBeInTheDocument();
    expect(screen.getByText("diagnostic_result")).toBeInTheDocument();
    expect(screen.getByText("accepted")).toBeInTheDocument();
    expect(screen.getByText("Источник: operation:operation-1")).toBeInTheDocument();
  });

  it("links evidence candidates and submits manual evidence", () => {
    const onCreateEvidence = vi.fn();
    const onLinkCandidate = vi.fn();

    render(
      <TicketPassportPanel
        candidates={{
          ticket_id: "ticket-1",
          candidates: [
            {
              candidate_id: "worklog:7",
              source_kind: "worklog",
              source_id: "7",
              source_ref: "worklog:7",
              source_quality: "strong",
              evidence_type: "worklog",
              required_fact: "operator_checks",
              section_key: "operator_checks",
              title: "Проверка очереди печати",
              summary: "Оператор проверил очередь и службу печати.",
              visibility: "internal",
              existing_evidence_id: null,
            },
          ],
        }}
        isGenerating={false}
        onCreateEvidence={onCreateEvidence}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onLinkCandidate={onLinkCandidate}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={passportPayload}
      />,
    );

    expect(screen.getByText("Кандидаты доказательств")).toBeInTheDocument();
    expect(screen.getByText("Проверка очереди печати")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Привязать" }));
    expect(onLinkCandidate).toHaveBeenCalledWith({
      source_kind: "worklog",
      source_id: "7",
      required_fact: "operator_checks",
      visibility: "internal",
    });

    fireEvent.change(screen.getByLabelText("Название доказательства"), { target: { value: "Ручная проверка" } });
    fireEvent.change(screen.getByLabelText("Краткое описание"), { target: { value: "Проверено вручную." } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить доказательство" }));
    expect(onCreateEvidence).toHaveBeenCalledWith({
      evidence_type: "manual_note",
      required_fact: "evidence",
      section_key: "evidence",
      title: "Ручная проверка",
      summary: "Проверено вручную.",
      visibility: "internal",
      verification_status: "accepted",
      export_visibility: "internal",
    });
  });

  it("saves editable passport sections", () => {
    const onPatchSections = vi.fn();

    render(
      <TicketPassportPanel
        isGenerating={false}
        onGenerate={() => undefined}
        onKnowledgeDraft={() => undefined}
        onPatchSections={onPatchSections}
        onPrint={() => undefined}
        onRefresh={() => undefined}
        payload={passportPayload}
      />,
    );

    fireEvent.change(screen.getByLabelText("Итог для пользователя"), { target: { value: "Печать восстановлена." } });
    fireEvent.change(screen.getByLabelText("Внутренний тех. итог"), { target: { value: "Сброс службы печати." } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить разделы" }));

    expect(onPatchSections).toHaveBeenCalledWith({
      operator_check_summary: passportPayload.passport.sections.operator_checks,
      changes_made_summary: passportPayload.passport.sections.changes_made,
      repeat_guidance: passportPayload.passport.sections.repeat_guidance,
      user_result_summary: "Печать восстановлена.",
      internal_result_summary: "Сброс службы печати.",
    });
  });
});

describe("TicketWorkVisibilityCard", () => {
  it("renders internal status, requester status and next action context", () => {
    render(
      <TicketWorkVisibilityCard
        ticket={{
          status: "waiting_on_vendor",
          status_label: "Ожидает внешнюю сторону",
          requester_status_label: "В работе",
          next_action_owner: "vendor",
          next_action_due_at: "2026-04-26T13:00:00Z",
          status_reason: "Провайдер",
          resolution_code: null,
          resolution_summary: null,
          requester_resolution_summary: null,
          evidence_required: true,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Ход работы")).toBeInTheDocument();
    expect(screen.getByText("Этап")).toBeInTheDocument();
    expect(screen.getAllByText("Ожидание").length).toBeGreaterThan(0);
    expect(screen.getByText("Внутренний статус")).toBeInTheDocument();
    expect(screen.getByText("Ожидает внешнюю сторону")).toBeInTheDocument();
    expect(screen.getByText("Статус для пользователя")).toBeInTheDocument();
    expect(screen.getByText("В работе")).toBeInTheDocument();
    expect(screen.getByText("Чей ход")).toBeInTheDocument();
    expect(screen.getByText("Внешняя сторона")).toBeInTheDocument();
    expect(screen.getByText("Что делать")).toBeInTheDocument();
    expect(screen.getByText("Контролировать внешний ответ")).toBeInTheDocument();
    expect(screen.getByText("Причина ожидания")).toBeInTheDocument();
    expect(screen.getByText("Провайдер")).toBeInTheDocument();
    expect(screen.getByText("Evidence gate")).toBeInTheDocument();
    expect(screen.getAllByText("Нужно доказательство").length).toBeGreaterThan(0);
  });
});

describe("TicketStatusActionPanel", () => {
  it("renders approval policy summary and action guard hints", () => {
    render(
      <TicketApprovalsPanel
        action={{
          approved_transition: "in_progress",
          current_action_owner: "approver",
          pending_count: 1,
          reject_requires_comment: true,
          rejected_transition: "canceled",
          waiting_status: "waiting_on_approval",
        }}
        summary={{
          approval_mode: "sequential",
          approved_count: 0,
          approved_transition: "in_progress",
          approver_source: "service_owner",
          current_action_owner: "approver",
          due_in: "2d",
          escalate_after: "1d",
          items: [
            {
              approval_type: "service_owner",
              approver_id: "owner-1",
              current: true,
              decided_at: null,
              due_at: "2026-01-03T09:00:00+00:00",
              escalated_at: "2026-01-02T09:00:00+00:00",
              escalation_at: "2026-01-02T09:00:00+00:00",
              id: 1,
              reason: "approval_policy_request",
              reminded_at: "2026-01-01T13:00:00+00:00",
              reminder_at: "2026-01-01T13:00:00+00:00",
              requested_at: "2026-01-01T09:00:00+00:00",
              requested_by: "support-test",
              status: "requested",
              timed_out_at: null,
            },
          ],
          pending_count: 1,
          rejected_count: 0,
          rejected_transition: "canceled",
          reminder_after: "4h",
          require_comment_on_reject: true,
          required: true,
          status: "pending",
          timed_out_count: 0,
          waiting_status: "waiting_on_approval",
        }}
      />,
    );

    expect(screen.getByText("Согласования")).toBeInTheDocument();
    expect(screen.getByText("Ожидает согласующего")).toBeInTheDocument();
    expect(screen.getByText("service_owner")).toBeInTheDocument();
    expect(screen.getByText("owner-1")).toBeInTheDocument();
    expect(screen.getByText("При отказе нужен комментарий. Без причины сервер заблокирует reject transition.")).toBeInTheDocument();
    expect(screen.getByText(/Срок:/)).toBeInTheDocument();
    expect(screen.getByText(/Эскалация:/)).toBeInTheDocument();
    expect(screen.getByText(/События:/)).toBeInTheDocument();
  });

  it("previews status transition and applies it only after explicit confirmation", () => {
    const onValueChange = vi.fn();
    const onApply = vi.fn();

    const { rerender } = render(
      <TicketStatusActionPanel
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus=""
        statusOptions={[
          { value: "in_progress", label: "Взять в работу" },
          { value: "resolved", label: "Решено" },
        ]}
        ticket={{
          status: "waiting_on_user",
          status_label: "Ожидает пользователя",
          requester_status_label: "Нужен ваш ответ",
          next_action_owner: "requester",
          evidence_required: true,
          evidence_ref: null,
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Целевой статус"), {
      target: { value: "resolved" },
    });

    expect(onValueChange).toHaveBeenCalledWith("resolved");
    expect(onApply).not.toHaveBeenCalled();

    rerender(
      <TicketStatusActionPanel
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus="resolved"
        statusOptions={[
          { value: "in_progress", label: "Взять в работу" },
          { value: "resolved", label: "Решено" },
        ]}
        ticket={{
          status: "waiting_on_user",
          status_label: "Ожидает пользователя",
          requester_status_label: "Нужен ваш ответ",
          next_action_owner: "requester",
          evidence_required: true,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Предпросмотр перехода")).toBeInTheDocument();
    expect(screen.getAllByText("Решено").length).toBeGreaterThan(0);
    expect(screen.getByText("Перед решением нужен evidence или паспорт решения.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Применить статус" }));
    expect(onApply).toHaveBeenCalledWith("resolved");
  });

  it("shows a permission reason when status changes are disabled by RBAC", () => {
    const onValueChange = vi.fn();
    const onApply = vi.fn();

    render(
      <TicketStatusActionPanel
        disabled={false}
        disabledReason="Недостаточно прав: ticket.status.change"
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus="in_progress"
        statusOptions={[{ value: "in_progress", label: "Взять в работу" }]}
        ticket={{
          status: "assigned",
          status_label: "Назначена",
          requester_status_label: "Заявка принята",
          next_action_owner: "support",
          evidence_required: false,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Недостаточно прав: ticket.status.change")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Применить статус" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Применить статус" }));
    expect(onApply).not.toHaveBeenCalled();
  });

  it("shows missing closure requirements for a resolve transition", () => {
    const onValueChange = vi.fn();
    const onApply = vi.fn();

    render(
      <TicketStatusActionPanel
        closureRequirements={[
          {
            key: "resolution_code",
            label: "Код решения",
            met: false,
            detail: "Укажите код из списка",
          },
          {
            key: "operation_log",
            label: "Журнал операции",
            met: false,
            detail: "Модуль запущен, нужен лог операции",
          },
          {
            key: "requester_confirmation",
            label: "Подтверждение заявителя",
            met: true,
            detail: "Будет запрошено после решения",
          },
        ]}
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus="resolved"
        statusOptions={[{ value: "resolved", label: "Решено" }]}
        ticket={{
          status: "in_progress",
          status_label: "В работе",
          requester_status_label: "Заявка в работе",
          next_action_owner: "support",
          evidence_required: false,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Чек-лист закрытия")).toBeInTheDocument();
    expect(screen.getByText("Код решения")).toBeInTheDocument();
    expect(screen.getByText("Журнал операции")).toBeInTheDocument();
    expect(screen.getByText("Модуль запущен, нужен лог операции")).toBeInTheDocument();
    expect(screen.getByText("Подтверждение заявителя")).toBeInTheDocument();
  });

  it("groups quick transition actions without applying until confirmation", () => {
    const onValueChange = vi.fn();
    const onApply = vi.fn();

    const { rerender } = render(
      <TicketStatusActionPanel
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus=""
        statusOptions={[
          { value: "in_progress", label: "Взять в работу" },
          { value: "waiting_on_vendor", label: "Ждём внешнюю сторону" },
          { value: "resolved", label: "Решено" },
        ]}
        ticket={{
          status: "assigned",
          status_label: "Назначена",
          requester_status_label: "Заявка принята",
          next_action_owner: "support",
          evidence_required: false,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Быстрые переходы")).toBeInTheDocument();
    expect(screen.getByText("В работе")).toBeInTheDocument();
    expect(screen.getAllByText("Ожидание").length).toBeGreaterThan(0);
    expect(screen.getByText("Решение")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Ждём внешнюю сторону/ }));
    expect(onValueChange).toHaveBeenCalledWith("waiting_on_vendor");
    expect(onApply).not.toHaveBeenCalled();

    rerender(
      <TicketStatusActionPanel
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus="waiting_on_vendor"
        statusOptions={[
          { value: "in_progress", label: "Взять в работу" },
          { value: "waiting_on_vendor", label: "Ждём внешнюю сторону" },
          { value: "resolved", label: "Решено" },
        ]}
        ticket={{
          status: "assigned",
          status_label: "Назначена",
          requester_status_label: "Заявка принята",
          next_action_owner: "support",
          evidence_required: false,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Следующий ответственный: Внешняя сторона")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Применить статус" }));
    expect(onApply).toHaveBeenCalledWith("waiting_on_vendor");
  });
});

describe("TicketStatusActionPanel FSM visibility", () => {
  it("separates allowed and blocked transitions and blocks invalid apply", () => {
    const onValueChange = vi.fn();
    const onApply = vi.fn();

    render(
      <TicketStatusActionPanel
        disabled={false}
        onApply={onApply}
        onValueChange={onValueChange}
        pending={false}
        selectedStatus="closed"
        statusOptions={[{ value: "in_progress", label: "Взять в работу" }]}
        ticket={{
          status: "assigned",
          status_label: "Назначена",
          requester_status_label: "Заявка принята",
          next_action_owner: "support",
          evidence_required: false,
          evidence_ref: null,
        }}
      />,
    );

    expect(screen.getByText("Доступно сейчас")).toBeInTheDocument();
    expect(screen.getByText("Недоступно сейчас")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Взять в работу/ })).toBeEnabled();

    const blockedClose = screen.getByRole("button", { name: /Закрыть/ });
    expect(blockedClose).toBeDisabled();
    expect(
      screen.getAllByText(/Сервер не разрешил этот переход/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Этот переход недоступен для текущего статуса.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Применить статус" }));
    expect(onApply).not.toHaveBeenCalled();
  });
});

describe("TicketAutomationPanel", () => {
  it("shows playbook readiness and launches the selected playbook explicitly", () => {
    const onRunPlaybook = vi.fn();

    render(
      <TicketAutomationPanel
        autoPlaybookEvents={[]}
        diagnosticPolicy={{
          suggested_playbooks: ["diagnose.website", "diagnose.dns.basic"],
          auto_run_enabled: true,
          auto_run_priorities: ["P0", "P1"],
          requester_consent_required: true,
          high_risk_consent_required: true,
          attach_to_timeline: true,
          attach_to_passport: true,
          attach_as_evidence: true,
          reroute_by_result: {
            DNS_FAIL: "networks",
            HTTP_500: "information_systems",
          },
        }}
        latestOperations={[
          {
            operation_id: "operation-1",
            kind: "tool_call",
            status: "queued",
            tool_name: "system.collect",
            command_name: null,
            queued_at: "2026-04-28T08:00:00Z",
            finished_at: null,
            result_summary: null,
            error_message: null,
          },
        ]}
        onRunPlaybook={onRunPlaybook}
        playbookErrorMessage={null}
        playbookPending={false}
        playbookResultMessage={null}
        playbooks={[
          {
            playbook_version_id: 7,
            key: "printer.quick_diag",
            name: "Быстрая диагностика принтера",
            domain: "diagnostics",
            version: "1.0.0",
            status: "published",
            blocks_count: 3,
            required_tools: ["system.collect", "printer.queue"],
            can_run: true,
            readiness_label: "Готов к запуску",
            updated_at: "2026-04-28T07:30:00Z",
          },
        ]}
        playbooksErrorMessage={null}
        playbooksLoading={false}
        recentRuns={[]}
        selectedPlaybookVersionId={7}
        setSelectedPlaybookVersionId={() => undefined}
      />,
    );

    expect(screen.getByText("Автоматизация")).toBeInTheDocument();
    expect(screen.getByText("Плейбук")).toBeInTheDocument();
    expect(screen.getAllByText("Быстрая диагностика принтера").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Готов к запуску").length).toBeGreaterThan(0);
    expect(screen.getAllByText("system.collect").length).toBeGreaterThan(0);
    expect(screen.getByText("Операции этого тикета")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Запустить плейбук" }));
    expect(screen.getByText("Политика диагностики")).toBeInTheDocument();
    expect(screen.getByText("diagnose.website, diagnose.dns.basic")).toBeInTheDocument();
    expect(screen.getByText("Автозапуск: P0, P1")).toBeInTheDocument();
    expect(screen.getByText("Нужно согласие пользователя")).toBeInTheDocument();
    expect(screen.getByText("High-risk consent")).toBeInTheDocument();
    expect(screen.getByText("В паспорт")).toBeInTheDocument();
    expect(screen.getByText("Evidence")).toBeInTheDocument();
    expect(screen.getByText("DNS_FAIL -> networks")).toBeInTheDocument();
    expect(onRunPlaybook).toHaveBeenCalledWith(7);
  });

  it("shows form-triggered playbook autostart evidence", () => {
    render(
      <TicketAutomationPanel
        autoPlaybookEvents={[
          {
            message_id: null,
            event_id: 77,
            event_type: "playbook_started",
            from_role: "system",
            sender_display_name: "Автодиагностика",
            text: "Автодиагностика запущена: printer.quick_diag",
            ts: "2026-04-28T08:01:00Z",
            visibility: "system",
            direction: "system",
            attachments: [],
            reply_to: null,
            tool_name: "printer.quick_diag",
            tool_status: "running",
            result_summary: "Run #77 • Событие: ticket_created • Факты формы: Кабинет: 214",
            result_preview: null,
          },
        ]}
        latestOperations={[]}
        onRunPlaybook={() => undefined}
        playbookErrorMessage={null}
        playbookPending={false}
        playbookResultMessage={null}
        playbooks={[]}
        playbooksErrorMessage={null}
        playbooksLoading={false}
        recentRuns={[]}
        selectedPlaybookVersionId={null}
        setSelectedPlaybookVersionId={() => undefined}
      />,
    );

    expect(screen.getByText("Автодиагностика формы")).toBeInTheDocument();
    expect(screen.getByText("Автодиагностика запущена: printer.quick_diag")).toBeInTheDocument();
    expect(screen.getByText(/Run #77/)).toBeInTheDocument();
  });

  it("blocks playbook launch with an RBAC disabled reason", () => {
    const onRunPlaybook = vi.fn();

    render(
      <TicketAutomationPanel
        autoPlaybookEvents={[]}
        disabledReason="Недостаточно прав: ticket.playbook.run"
        latestOperations={[]}
        onRunPlaybook={onRunPlaybook}
        playbookErrorMessage={null}
        playbookPending={false}
        playbookResultMessage={null}
        playbooks={[
          {
            playbook_version_id: 7,
            key: "printer.quick_diag",
            name: "Быстрая диагностика принтера",
            domain: "diagnostics",
            version: "1.0.0",
            status: "published",
            blocks_count: 3,
            required_tools: ["system.collect"],
            can_run: true,
            readiness_label: "Готов к запуску",
            updated_at: "2026-04-28T07:30:00Z",
          },
        ]}
        playbooksErrorMessage={null}
        playbooksLoading={false}
        recentRuns={[]}
        selectedPlaybookVersionId={7}
        setSelectedPlaybookVersionId={() => undefined}
      />,
    );

    expect(screen.getByText("Недостаточно прав: ticket.playbook.run")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Запустить плейбук" }));
    expect(onRunPlaybook).not.toHaveBeenCalled();
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
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
      source_payload: {},
      stale: false,
    },
    evidence: [],
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
    expect(screen.getByText("Ожидание")).toBeInTheDocument();
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
    expect(screen.getByText("Ожидание")).toBeInTheDocument();
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

describe("TicketAutomationPanel", () => {
  it("shows playbook readiness and launches the selected playbook explicitly", () => {
    const onRunPlaybook = vi.fn();

    render(
      <TicketAutomationPanel
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
        selectedPlaybookVersionId={7}
        setSelectedPlaybookVersionId={() => undefined}
      />,
    );

    expect(screen.getByText("Автоматизация")).toBeInTheDocument();
    expect(screen.getByText("Плейбук")).toBeInTheDocument();
    expect(screen.getAllByText("Быстрая диагностика принтера").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Готов к запуску").length).toBeGreaterThan(0);
    expect(screen.getAllByText("system.collect").length).toBeGreaterThan(0);
    expect(screen.getByText("Последние запуски")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Запустить плейбук" }));
    expect(onRunPlaybook).toHaveBeenCalledWith(7);
  });
});

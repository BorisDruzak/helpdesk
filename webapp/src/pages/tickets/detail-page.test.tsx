import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TicketRequestFormCard, TicketWorkVisibilityCard } from "./detail-page";

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
    expect(screen.getByText("Внутренний статус")).toBeInTheDocument();
    expect(screen.getByText("Ожидает внешнюю сторону")).toBeInTheDocument();
    expect(screen.getByText("Статус для пользователя")).toBeInTheDocument();
    expect(screen.getByText("В работе")).toBeInTheDocument();
    expect(screen.getByText("Чей ход")).toBeInTheDocument();
    expect(screen.getByText("Внешняя сторона")).toBeInTheDocument();
    expect(screen.getByText("Причина ожидания")).toBeInTheDocument();
    expect(screen.getByText("Провайдер")).toBeInTheDocument();
    expect(screen.getByText("Требуется")).toBeInTheDocument();
  });
});

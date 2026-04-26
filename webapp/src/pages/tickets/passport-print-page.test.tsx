import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TicketPassportPrintPage } from "./passport-print-page";

function renderPrintPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/app/tickets/ticket-1/passport/print"]}>
        <Routes>
          <Route path="/app/tickets/:ticketId/passport/print" element={<TicketPassportPrintPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TicketPassportPrintPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders official passport print view from typed API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            status: "success",
            data: {
              ticket_id: "ticket-1",
              status: "draft",
              passport: {
                passport_id: 1,
                ticket_id: "ticket-1",
                version: 3,
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
              evidence: [{ id: 1, title: "Скриншот", ticket_id: "ticket-1" }],
              actions: [{ id: 1, title: "Диагностика", ticket_id: "ticket-1" }],
              approvals: [],
              related_objects: [],
            },
          }),
          { headers: { "content-type": "application/json" } },
        ),
      ),
    );

    renderPrintPage();

    expect(await screen.findByText("Версия 3")).toBeInTheDocument();
    expect(screen.getByText("Официальная карточка решения")).toBeInTheDocument();
    expect(screen.getByText("Паспорт решения")).toBeInTheDocument();
    expect(screen.getByText("Кто и откуда обратился")).toBeInTheDocument();
    expect(screen.getByText("Иванов Иван, кабинет 214")).toBeInTheDocument();
    expect(screen.getByText("Что делать при повторе")).toBeInTheDocument();
    expect(screen.getByText("Печать / PDF")).toBeInTheDocument();
  });
});

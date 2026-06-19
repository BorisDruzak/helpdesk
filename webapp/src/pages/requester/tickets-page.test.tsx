import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterTicketsPage } from "./tickets-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderTicketsPage(initialEntry = "/app/requester/tickets") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={queryClient}>
          <Routes>
            <Route path="/app/requester/tickets" element={children} />
            <Route path="/app/requester/tickets/:ticketId" element={children} />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(<RequesterTicketsPage />, { wrapper: Wrapper });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RequesterTicketsPage", () => {
  it("renders requester tickets with filters, search and human request numbers", async () => {
    installTicketsMock();
    renderTicketsPage();

    expect(await screen.findByRole("heading", { name: "Мои обращения" })).toBeInTheDocument();
    expect(await screen.findByText("REQ-1001")).toBeInTheDocument();
    expect(screen.getByText("19.06.2026, 09:30")).toBeInTheDocument();
    expect(screen.queryByText("550e8400-e29b-41d4-a716-446655440000")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Требуют действий" }));
    expect(screen.getByText("Нужен ответ")).toBeInTheDocument();
    expect(screen.getByText("Подтвердите решение")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Поиск по обращениям"), { target: { value: "закрытая" } });
    expect(screen.getByText("Нет обращений по выбранным условиям")).toBeInTheDocument();
  });

  it("preserves reply text when sending a requester message fails", async () => {
    installTicketsMock({ messageFails: true });
    renderTicketsPage("/app/requester/tickets/T-1001");

    expect(await screen.findByRole("heading", { name: "Ноутбук не включается" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Ответ заявителя"), {
      target: { value: "Проблема повторяется после перезагрузки" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Не удалось отправить сообщение")).toBeInTheDocument();
    expect(screen.getByLabelText("Ответ заявителя")).toHaveValue("Проблема повторяется после перезагрузки");
  });

  it("handles attachments, consents, resolution feedback and reopen actions", async () => {
    const fetchMock = installTicketsMock();
    renderTicketsPage("/app/requester/tickets/T-1001");

    expect(await screen.findByRole("heading", { name: "Ноутбук не включается" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Прикрепить файл к ответу"), {
      target: { files: [new File(["log"], "log.txt", { type: "text/plain" })] },
    });
    expect(await screen.findByText("log.txt")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Ответ заявителя"), { target: { value: "Прикладываю лог" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-1001/message",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ text: "Прикладываю лог", attachment_refs: ["artifact-1"] }) }),
      );
    });

    expect(screen.getByRole("heading", { name: "Ожидают вашего решения" })).toBeInTheDocument();
    expect(screen.queryByText("consent-1")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Подтвердить согласие consent-1")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Разрешить запрос согласия" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/consents/consent-1/approve",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить решение" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-1001/close",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByLabelText("Оценка обращения"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("Проблема решена"));
    fireEvent.click(screen.getByRole("button", { name: "Отправить оценку" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-1001/feedback",
        expect.objectContaining({ method: "POST", body: expect.stringContaining('"rating":2') }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Вернуть в работу" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-1001/reopen",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(within(screen.getByRole("list", { name: "История обращения" })).getByText("Оператор запросил диагностику")).toBeInTheDocument();
  });
});

function installTicketsMock(options: { messageFails?: boolean } = {}) {
  let consentStatus = "pending";
  let detailStatus = "resolved";
  let feedbackSubmitted = false;
  let messageSent = false;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/requester/tickets") {
      return jsonResponse({
        status: "success",
        data: {
          tickets: [
            {
              ticket_id: "T-1001",
              ticket_code: "REQ-1001",
              title: "Ноутбук не включается",
              status: detailStatus,
              requester_status_label: detailStatus === "resolved" ? "Решена" : "В работе",
              updated_at: "2026-06-19T04:30:00Z",
              created_at: "2026-06-19T04:00:00Z",
            },
            {
              ticket_id: "550e8400-e29b-41d4-a716-446655440000",
              ticket_code: "REQ-1002",
              title: "Нужен ответ",
              status: "waiting_user",
              requester_status_label: "Ждет вашего ответа",
              updated_at: "2026-06-19T05:00:00Z",
            },
            {
              ticket_id: "T-1003",
              ticket_code: "REQ-1003",
              title: "Закрытая заявка",
              status: "closed",
              requester_status_label: "Закрыта",
              updated_at: "2026-06-18T09:00:00Z",
            },
          ],
        },
      });
    }
    if (url === "/api/web/requester/consents?status=pending") {
      return jsonResponse({
        status: "success",
        data: {
          consents:
            consentStatus === "pending"
              ? [
                  {
                    consent_id: "consent-1",
                    ticket_id: "T-1001",
                    subject_type: "diagnostic",
                    subject_id: "diag-1",
                    title: "Диагностика устройства",
                    description: "Оператор просит выполнить безопасную диагностику.",
                    status: "pending",
                    risk_level: "low",
                    expires_at: "2026-06-20T10:00:00Z",
                  },
                ]
              : [],
        },
      });
    }
    if (url === "/api/web/requester/tickets/T-1001") {
      return jsonResponse({
        status: "success",
        data: {
          ticket: {
            ticket_id: "T-1001",
            ticket_code: "REQ-1001",
            title: "Ноутбук не включается",
            description: "Не включается после обновления",
            status: detailStatus,
            requester_status_label: detailStatus === "resolved" ? "Решена" : "В работе",
            updated_at: "2026-06-19T04:30:00Z",
          },
          messages: messageSent
            ? [
                {
                  message_id: "m-1",
                  from_role: "user",
                  text: "Прикладываю лог",
                  created_at: "2026-06-19T05:10:00Z",
                  attachments: [{ artifact_id: "artifact-1", name: "log.txt", url: "/api/artifacts/artifact-1/download" }],
                },
              ]
            : [{ message_id: "m-support", from_role: "support", text: "Проверьте питание.", created_at: "2026-06-19T04:40:00Z" }],
          events: [{ event_id: "e-1", requester_timeline_text: "Оператор запросил диагностику", created_at: "2026-06-19T04:45:00Z" }],
        },
      });
    }
    if (url === "/api/upload") {
      return jsonResponse({
        status: "success",
        artifact_id: "artifact-1",
        filename: "log.txt",
        url: "/api/artifacts/artifact-1/download",
        kind: "file",
      });
    }
    if (url === "/api/web/requester/tickets/T-1001/message") {
      if (options.messageFails) {
        return jsonResponse({ status: "error", message: "Не удалось отправить сообщение" }, 500);
      }
      messageSent = true;
      return jsonResponse({ status: "success", data: { message_id: "m-1" } });
    }
    if (url === "/api/web/requester/consents/consent-1/approve") {
      consentStatus = "approved";
      return jsonResponse({ status: "success", data: { consent: { consent_id: "consent-1", status: "approved" } } });
    }
    if (url === "/api/web/requester/consents/consent-1/deny") {
      consentStatus = "denied";
      return jsonResponse({ status: "success", data: { consent: { consent_id: "consent-1", status: "denied" } } });
    }
    if (url === "/api/web/requester/tickets/T-1001/close") {
      detailStatus = "closed";
      return jsonResponse({ status: "success", data: { ticket: { ticket_id: "T-1001", status: "closed" } } });
    }
    if (url === "/api/web/requester/tickets/T-1001/feedback") {
      feedbackSubmitted = true;
      return jsonResponse({ status: "success", data: { ok: true, feedback_id: "fb-1", reopen_available: true } });
    }
    if (url === "/api/web/requester/tickets/T-1001/reopen") {
      expect(feedbackSubmitted).toBe(true);
      detailStatus = "in_progress";
      return jsonResponse({ status: "success", data: { ok: true, ticket_id: "T-1001", ticket_status: "in_progress", reopen_id: "re-1" } });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

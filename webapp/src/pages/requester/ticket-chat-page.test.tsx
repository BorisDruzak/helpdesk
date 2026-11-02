import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RequesterTicketChatPage } from "./ticket-chat-page";

vi.mock("./use-ticket-chat", () => ({
  useRequesterTicketChat: () => ({
    selectedTicket: { ticket_id: "one", ticket_code: "T-001", title: "Принтер", description: "Не печатает", status: "closed", requester_resolution_summary: "Заменён картридж" },
    detailQuery: { data: { messages: [] }, isLoading: false, isError: false },
    pendingConsents: [], canClose: false, canRate: false, canReopen: false, canSendMessage: false,
  }),
}));

describe("requester ticket chat result", () => {
  it("shows the public result immediately without requiring confirmation", () => {
    render(<MemoryRouter><RequesterTicketChatPage /></MemoryRouter>);
    expect(screen.getByRole("region", { name: "Результат решения" })).toBeVisible();
    expect(screen.getByText("Заменён картридж")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Подтвердить решение" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить оценку" })).not.toBeInTheDocument();
  });
});

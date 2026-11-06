import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RequesterTicketChatPage } from "./ticket-chat-page";
import { RequesterApiError } from "../../features/requester/api";

const actions = vi.hoisted(() => ({ canClose: false, canRate: false, canReopen: false }));
const failure = vi.hoisted(() => ({ error: null as Error | null }));
beforeEach(() => { actions.canClose = false; actions.canRate = false; actions.canReopen = false; failure.error = null; });

vi.mock("./use-ticket-chat", () => ({
  useRequesterTicketChat: () => ({
    selectedTicket: { ticket_id: "one", ticket_code: "T-001", title: "Принтер", description: "Не печатает", status: "closed", requester_resolution_summary: "Заменён картридж" },
    detailQuery: { data: { messages: [] }, isLoading: false, isError: Boolean(failure.error), error: failure.error },
    pendingConsents: [], ...actions, canSendMessage: false,
  }),
}));

describe("requester ticket chat result", () => {
  it.each([401, 403, 404])("hides cached solution controls when access is rejected with %s", (status) => {
    actions.canClose = true; actions.canReopen = true;
    failure.error = new RequesterApiError("Нет доступа", status);
    render(<MemoryRouter><RequesterTicketChatPage /></MemoryRouter>);
    expect(screen.queryByRole("region", { name: "Действия по решению обращения" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Подтвердить решение" })).not.toBeInTheDocument();
  });
  it("keeps granted resolution actions outside the scrolling history and available in details", () => {
    actions.canClose = true; actions.canReopen = true;
    const view = render(<MemoryRouter><RequesterTicketChatPage /></MemoryRouter>);
    const bar = screen.getByRole("region", { name: "Действия по решению обращения" });
    expect(view.container.querySelector("#requester-chat-content")).not.toContainElement(bar);
    expect(screen.getByRole("button", { name: "Подтвердить решение" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Проблема не решена" })).toBeVisible();
    expect(screen.queryByText(/Переписка доступна для просмотра/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Описание и история" }));
    expect(screen.getByRole("button", { name: "Подтвердить решение" })).toBeVisible();
  });
  it("shows the public result immediately without requiring confirmation", () => {
    render(<MemoryRouter><RequesterTicketChatPage /></MemoryRouter>);
    expect(screen.getByRole("region", { name: "Результат решения" })).toBeVisible();
    expect(screen.getByText("Заменён картридж")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Подтвердить решение" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить оценку" })).not.toBeInTheDocument();
  });
});

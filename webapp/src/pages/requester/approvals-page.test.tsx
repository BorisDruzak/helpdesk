import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RequesterApprovalsPage } from "./approvals-page";

afterEach(() => vi.unstubAllGlobals());

it("requires a rejection comment and sends a decision only for the displayed assignment", async () => {
  let decided = false;
  const decisions: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/decision")) {
      expect(url).toBe("/api/web/support/tickets/ticket-1/approvals/7/decision");
      decisions.push(JSON.parse(init.body)); decided = true;
      return Response.json({ status: "success", data: { approval: { status: "rejected" } } });
    }
    return Response.json({ status: "success", data: { items: decided ? [] : [{ approval_id: 7, ticket_id: "ticket-1", ticket_code: "T-1", title: "Доступ к папке", description: "Нужен доступ к синтетической папке", status: "requested", can_decide: true, reject_requires_comment: true }] } });
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RequesterApprovalsPage /></QueryClientProvider>);
  expect(await screen.findByText("Доступ к папке")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Отклонить" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Комментарий к решению"), { target: { value: "Уточните основание" } });
  fireEvent.click(screen.getByRole("button", { name: "Отклонить" }));
  await waitFor(() => expect(decisions).toEqual([{ decision: "rejected", comment: "Уточните основание" }]));
  expect(await screen.findByText("Нет обращений, ожидающих вашего решения")).toBeInTheDocument();
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationMenu } from "./notification-menu";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("shows chat/status events and marks only the clicked event read", async () => {
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    requests.push(String(input));
    const notifications = [
      { id: 1, title: "Новое сообщение по обращению T-000077", body: "Откройте обращение", url: "/app/requester/tickets/t77", is_read: false },
      { id: 2, title: "Изменён статус обращения T-000077", body: "Обращение в работе", url: "/app/requester/tickets/t77", is_read: true },
    ];
    return new Response(JSON.stringify({ status: "ok", notifications }), { headers: { "Content-Type": "application/json" } });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}><NotificationMenu userLogin="employee" requester onClose={vi.fn()} /></QueryClientProvider></MemoryRouter>);
  await screen.findByText("Новое сообщение по обращению T-000077");
  expect(screen.getByText("Обращение в работе")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: /Новое сообщение/ }));
  await waitFor(() => expect(requests).toContain("/api/web/notifications/1/read"));
  expect(requests).not.toContain("/api/web/notifications/read_all");
  client.clear();
});

it("does not show an empty success state when notification reads fail", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 503 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}><NotificationMenu userLogin="employee" requester onClose={vi.fn()} /></QueryClientProvider></MemoryRouter>);
  await screen.findByText("Не удалось загрузить уведомления.");
  expect(screen.queryByText("Уведомлений пока нет")).not.toBeInTheDocument();
  client.clear();
});

it("requests only unread events and clears the bell after read-all", async () => {
  let read = false;
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    const url = String(input); requests.push(url);
    if (url.endsWith("/read_all")) read = true;
    const row = { id: 3, title: "Новое сообщение", body: "Откройте обращение", url: "/app/requester/tickets/t77", is_read: read };
    return Response.json({ status: "ok", notifications: url.includes("unread_only=true") && read ? [] : [row] });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}><NotificationMenu userLogin="employee" requester onClose={vi.fn()} /></QueryClientProvider></MemoryRouter>);
  await screen.findByText("Новое сообщение");
  fireEvent.click(screen.getByRole("button", { name: "Прочитать все" }));
  await screen.findByText("Уведомлений пока нет");
  expect(screen.queryByText("Новое сообщение")).not.toBeInTheDocument();
  expect(requests).toContain("/api/web/notifications?limit=30&unread_only=true");
  client.clear();
});

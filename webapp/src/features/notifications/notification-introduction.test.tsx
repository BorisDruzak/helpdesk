import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationIntroduction } from "./notification-introduction";

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function setup(login = "intro-user") {
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("PushManager", function () {});
  const permission = vi.fn(async () => "denied");
  vi.stubGlobal("Notification", { requestPermission: permission });
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn(async () => undefined) } });
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(function (this: HTMLDialogElement) { this.open = true; });
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (this: HTMLDialogElement) { this.open = false; });
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ status: "ok", enabled: true, public_key: "BA" })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><NotificationIntroduction key={login} userLogin={login} /></QueryClientProvider>);
  return { ...view, client, permission };
}

it("explains chat/status/closed tab without requesting permission, and remembers close per actor", async () => {
  const view = setup();
  await screen.findByRole("dialog", { name: "Не пропускайте ответы по обращениям" });
  expect(screen.getByText(/сообщениях в чате и смене статуса/)).toBeInTheDocument();
  expect(view.permission).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Закрыть подсказку" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  view.unmount(); view.client.clear();
  const again = setup();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  again.unmount(); again.client.clear();
  const other = setup("other-user");
  await screen.findByRole("dialog");
  other.client.clear();
});

it("asks only after explicit enable and keeps denial visible", async () => {
  const view = setup("intro-denied");
  fireEvent.click(await screen.findByRole("button", { name: "Включить уведомления в браузере" }));
  await screen.findByRole("alert");
  expect(view.permission).toHaveBeenCalledOnce();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  view.client.clear();
});

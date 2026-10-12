import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { OfferingPublication } from "./offering-publication";
afterEach(() => vi.unstubAllGlobals());
function mount() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><OfferingPublication code="it.owned" /></QueryClientProvider>); }
it("requires explicit confirmation and uses only canonical offering publication", async () => {
  const request = vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { headers: { "content-type": "application/json" } })); vi.stubGlobal("fetch", request); mount();
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать услугу" })); expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию услуги" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/api/web/admin/service-catalog/offerings/it.owned/publish", { method: "POST", credentials: "same-origin" }));
});
it("keeps a failed publication visible instead of claiming employee availability", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "not ready" }), { status: 400 }))); mount();
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать услугу" }));
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию услуги" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Услуга не опубликована");
});

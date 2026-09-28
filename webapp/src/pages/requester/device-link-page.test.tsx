import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RequesterDeviceLinkPage } from "./device-link-page";
import { clearPendingDeviceCode, pendingDeviceCode, rememberPendingDeviceCode } from "../../features/requester/device-link-state";

const mocks = vi.hoisted(() => ({ profile: { data: null as unknown, isLoading: false, error: null }, link: vi.fn(), invalidate: vi.fn() }));
vi.mock("../../features/requester/queries", () => ({
  useRequesterProfileQuery: () => mocks.profile,
  requesterInvalidations: { afterDeviceLink: mocks.invalidate },
}));
vi.mock("../../features/requester/api", () => ({ linkRequesterDevice: mocks.link, RequesterApiError: class extends Error {} }));

function show() {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/app/requester/devices/link"]}><Routes>
    <Route path="/app/requester/devices/link" element={<RequesterDeviceLinkPage />} />
    <Route path="/app/requester/devices" element={<p>Device list destination</p>} />
    <Route path="/app/requester/profile/setup" element={<p>Profile destination</p>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); clearPendingDeviceCode(); mocks.profile.data = { profile: { person_id: "person" }, profile_completion: { complete: true } }; });
afterEach(cleanup);

describe("device binding requester wizard", () => {
  it("keeps a fragment code only in memory while profile completion is required", () => {
    rememberPendingDeviceCode("123-456"); mocks.profile.data = { profile: null, profile_completion: { complete: false } };
    show(); fireEvent.click(screen.getByRole("link", { name: "Заполнить профиль" }));
    expect(screen.getByText("Profile destination")).toBeTruthy();
    expect(pendingDeviceCode()).toBe("123456"); expect(mocks.link).not.toHaveBeenCalled();
  });
  it("rejects malformed codes before calling the server", () => {
    show(); fireEvent.change(screen.getByRole("textbox"), { target: { value: "１２３４５６" } });
    fireEvent.click(screen.getByRole("button", { name: "Привязать устройство" }));
    expect(screen.getByRole("alert").textContent).toContain("шестизначный"); expect(mocks.link).not.toHaveBeenCalled();
  });
  it.each(["active", "pending_admin_review"])("clears proof after %s and refreshes device projections", async (binding_status) => {
    mocks.link.mockResolvedValue({ binding_status }); rememberPendingDeviceCode("123-456"); show();
    fireEvent.click(screen.getByRole("button", { name: "Привязать устройство" }));
    await waitFor(() => expect(mocks.invalidate).toHaveBeenCalledOnce());
    expect(mocks.link).toHaveBeenCalledWith("123456"); expect(pendingDeviceCode()).toBe("");
    await waitFor(() => expect(screen.getByText(binding_status === "active" ? "Device list destination" : /Запрос на изменение владельца отправлен/)).toBeTruthy());
  });
});

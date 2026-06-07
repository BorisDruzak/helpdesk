import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DevicePairingPage } from "./index";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderPage(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<DevicePairingPage purpose="login" />} path="/app/device/login" />
        <Route element={<DevicePairingPage purpose="registration" />} path="/app/device/register" />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DevicePairingPage", () => {
  it("confirms login pairing and keeps agent session token out of the browser UI", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-1") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-1",
            purpose: "login",
            status: "pending",
            expires_at: "2026-06-08T12:00:00+05:00",
            device: {
              hostname: "PC-77",
              os: "Windows",
              agent_version: "3.1.62",
            },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-1/login/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-1",
            purpose: "login",
            status: "confirmed",
            binding_id: "binding-1",
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/login?pairing_id=pair-1");

    expect(await screen.findByRole("heading", { name: "Вход на этом устройстве" })).toBeInTheDocument();
    expect(screen.getByText("PC-77")).toBeInTheDocument();
    expect(screen.getByText("Windows")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить вход" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/registry/browser-pairings/pair-1/login/confirm",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(await screen.findByText("Вход подтвержден")).toBeInTheDocument();
    expect(screen.queryByText(/session_token/i)).not.toBeInTheDocument();
  });

  it("confirms registration pairing for the paired device", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-2") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-2",
            purpose: "registration",
            status: "pending",
            device: { hostname: "NEW-PC", os: "Windows", agent_version: "3.1.62" },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-2/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-2",
            purpose: "registration",
            status: "confirmed",
            claim_id: "claim-1",
            registration: { status: "pending_admin_review", device_id: "device-1" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/register?pairing_id=pair-2");

    expect(await screen.findByRole("heading", { name: "Регистрация устройства" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить регистрацию" }));

    expect(await screen.findByText("Регистрация подтверждена")).toBeInTheDocument();
    expect(screen.getByText("pending_admin_review")).toBeInTheDocument();
  });
});

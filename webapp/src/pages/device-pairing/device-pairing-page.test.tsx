import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DevicePairCodePage, DevicePairingPage } from "./index";

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
        <Route element={<DevicePairCodePage />} path="/app/device/pair" />
        <Route element={<DevicePairingPage purpose="login" />} path="/app/device/login" />
        <Route element={<DevicePairingPage purpose="registration" />} path="/app/device/register" />
      </Routes>
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function renderPairCodePage(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          element={
            <>
              <DevicePairCodePage />
              <LocationProbe />
            </>
          }
          path="/app/device/pair"
        />
        <Route element={<LocationProbe />} path="/app/device/login" />
        <Route element={<LocationProbe />} path="/app/device/register" />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DevicePairingPage", () => {
  it("looks up a manual pairing code and redirects to login confirmation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/lookup") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({ pairing_code: "ABCD-1234" });
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-lookup-1",
            purpose: "login",
            next_url: "/app/device/login?pairing_id=pair-lookup-1",
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPairCodePage("/app/device/pair");

    fireEvent.change(screen.getByLabelText("Код подключения"), { target: { value: "ABCD-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/app/device/login?pairing_id=pair-lookup-1");
    });
  });

  it("shows a safe error for rejected manual pairing codes", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          status: "error",
          error: "Код не найден или истек",
          error_code: "PAIRING_CODE_NOT_FOUND",
        },
        404,
      ),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPairCodePage("/app/device/pair");

    fireEvent.change(screen.getByLabelText("Код подключения"), { target: { value: "EXPIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(await screen.findByText("Код не найден или истек")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/app/device/pair");
  });

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
    expect(screen.getByText("NEW-PC")).toBeInTheDocument();
    expect(screen.getByText("Windows")).toBeInTheDocument();
  });
});

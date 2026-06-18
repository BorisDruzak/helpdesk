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

  it("explains when the current web account is not linked to the paired device", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-forbidden") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-forbidden",
            purpose: "login",
            status: "pending",
            device: {
              hostname: "ADMIN-2",
              os: "Windows",
              agent_version: "3.1.67",
            },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-forbidden/login/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse(
          {
            status: "error",
            error: "active binding not found for web user",
            error_code: "PAIRING_FORBIDDEN",
          },
          403,
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/login?pairing_id=pair-forbidden");

    expect(await screen.findByText("ADMIN-2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить вход" }));

    expect(
      await screen.findByText(
        "Текущий веб-аккаунт не привязан к этому компьютеру. Выйдите и войдите под привязанным пользователем или привяжите устройство через регистрацию.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("active binding not found for web user")).not.toBeInTheDocument();
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
      if (url === "/api/registry/options") {
        return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
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
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку" }));

    expect(await screen.findByText("Заявка на привязку отправлена")).toBeInTheDocument();
    expect(screen.getByText("Ожидает проверки администратора")).toBeInTheDocument();
    expect(screen.getByText("Администратор должен одобрить заявку. В локальном агенте нажмите «Обновить», чтобы увидеть статус ожидания.")).toBeInTheDocument();
    expect(screen.queryByText("pending_admin_review")).not.toBeInTheDocument();
    expect(screen.getByText("NEW-PC")).toBeInTheDocument();
    expect(screen.getByText("Windows")).toBeInTheDocument();
  });

  it("keeps registration confirmation on the device page when a stale profile-incomplete error is returned", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-profile") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-profile",
            purpose: "registration",
            status: "pending",
            device: { hostname: "PROFILE-PC", os: "Windows", agent_version: "3.1.62" },
          },
        });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
      }
      if (url === "/api/web/registry/browser-pairings/pair-profile/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse(
          {
            status: "error",
            error_code: "REQUESTER_PROFILE_INCOMPLETE",
            error: "Заполните профиль, чтобы продолжить работу в кабинете пользователя.",
            details: { setup_path: "/app/requester/profile/setup" },
          },
          403,
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/app/device/register?pairing_id=pair-profile"]}>
        <Routes>
          <Route
            element={
              <>
                <DevicePairingPage purpose="registration" />
                <LocationProbe />
              </>
            }
            path="/app/device/register"
          />
          <Route element={<LocationProbe />} path="/app/requester/profile/setup" />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("PROFILE-PC")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/app/device/register?pairing_id=pair-profile");
    });
    expect(screen.getByText("Привязка устройства не должна требовать заполненный профиль. Обновите страницу и повторите привязку.")).toBeInTheDocument();
  });

  it("shows a product-safe Russian error when the device link id is missing", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const { container } = render(
      <MemoryRouter initialEntries={["/app/device/register"]}>
        <Routes>
          <Route element={<DevicePairingPage purpose="registration" />} path="/app/device/register" />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Откройте эту страницу из агента или введите код подключения.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(container.textContent ?? "").not.toMatch(/pairing_id|binding_id|claim_id|session/i);
  });

  it("sends selected registry department and location when confirming registration", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-strict") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-strict",
            purpose: "registration",
            status: "pending",
            device: { hostname: "STRICT-PC", os: "Windows", agent_version: "3.1.62" },
          },
        });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({
          status: "success",
          data: {
            departments: [{ value: "dept-1", label: "ИТ" }],
            locations: [{ value: "loc-1", label: "Офис 7 / 701" }],
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-strict/registration/confirm") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({
          department_id: "dept-1",
          location_id: "loc-1",
        });
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-strict",
            purpose: "registration",
            status: "confirmed",
            claim_id: "claim-strict",
            registration: { status: "pending_admin_review", device_id: "device-strict" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/register?pairing_id=pair-strict");

    expect(await screen.findByText("STRICT-PC")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Подразделение"), { target: { value: "dept-1" } });
    fireEvent.change(screen.getByLabelText("Локация"), { target: { value: "loc-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку" }));

    expect(await screen.findByText("Заявка на привязку отправлена")).toBeInTheDocument();
  });

  it("shows a linked-device result when registration is auto-approved", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-auto") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-auto",
            purpose: "registration",
            status: "pending",
            device: { hostname: "AUTO-PC", os: "Windows", agent_version: "3.1.70" },
          },
        });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
      }
      if (url === "/api/web/registry/browser-pairings/pair-auto/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-auto",
            purpose: "registration",
            status: "confirmed",
            claim_id: "claim-auto",
            registration: { status: "approved", device_id: "device-auto" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/register?pairing_id=pair-auto");

    expect(await screen.findByText("AUTO-PC")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку" }));

    expect((await screen.findAllByText("Устройство привязано")).length).toBeGreaterThan(0);
    expect(screen.getByText("Вернитесь в локальный агент и нажмите «Обновить», чтобы войти под привязанным пользователем.")).toBeInTheDocument();
    expect(screen.queryByText("Ожидает проверки администратора")).not.toBeInTheDocument();
  });

  it("shows a safe Russian error when strict registration ids are rejected", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/registry/browser-pairings/pair-invalid") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-invalid",
            purpose: "registration",
            status: "pending",
            device: { hostname: "STRICT-PC", os: "Windows", agent_version: "3.1.62" },
          },
        });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({
          status: "success",
          data: {
            departments: [{ value: "dept-1", label: "Dept 1" }],
            locations: [{ value: "loc-1", label: "Office 7 / 701" }],
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-invalid/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse(
          {
            status: "error",
            error: "department_id not found",
            error_code: "NOT_FOUND",
          },
          404,
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/device/register?pairing_id=pair-invalid");

    expect(await screen.findByText("STRICT-PC")).toBeInTheDocument();
    const selects = await screen.findAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "dept-1" } });
    fireEvent.change(selects[1], { target: { value: "loc-1" } });
    fireEvent.click(screen.getByRole("button"));

    expect(
      await screen.findByText(
        "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u043e\u0434\u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u0438\u0437 \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("department_id not found")).not.toBeInTheDocument();
  });

});

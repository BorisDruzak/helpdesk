import { fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../features/auth/session-provider";
import { QueryProvider } from "./providers/query-provider";
import { appRoutes } from "./router";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function renderApp(initialEntries: string[], fetchMock: typeof fetch) {
  vi.stubGlobal("fetch", fetchMock);

  const router = createMemoryRouter(appRoutes, {
    initialEntries
  });

  render(
    <QueryProvider>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryProvider>
  );

  return { router };
}

function createSupportSession() {
  return {
    user_login: "support1",
    actor_role: "support",
    auth_type: "ui_token",
    default_workspace: "support",
    available_workspaces: ["support"]
  };
}

function createAdminSession() {
  return {
    user_login: "admin1",
    actor_role: "admin",
    auth_type: "ui_token",
    default_workspace: "admin",
    available_workspaces: ["admin", "support"]
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("appRoutes", () => {
  it("redirects anonymous users to the redesigned login page", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return new Response("", { status: 401 });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/tickets"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Добро пожаловать" })).toBeInTheDocument();
    expect(screen.getByLabelText("Логин")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
  });

  it("opens the new tickets page for support role and hides admin menu", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Тикеты" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Тикеты/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("returns support user from /app/admin to tickets after login", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return new Response("", { status: 401 });
      }

      if (url.endsWith("/api/web/session/login")) {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBe(JSON.stringify({ login: "support", password: "secret" }));

        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    fireEvent.change(await screen.findByLabelText("Логин"), {
      target: { value: "support" }
    });
    fireEvent.change(screen.getByLabelText("Пароль"), {
      target: { value: "secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Тикеты" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("redirects /app/admin to inventory for admin session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Инвентарь устройств" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Инвентарь устройств/ })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Тикеты/ })).toBeInTheDocument();
  });
});

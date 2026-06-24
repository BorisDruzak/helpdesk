import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider, useSession } from "./session-provider";


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}


function SessionProbe() {
  const { session, status } = useSession();

  return (
    <div>
      <span>{status}</span>
      <span>{session?.user_login ?? "anon"}</span>
    </div>
  );
}


function LoginProbe() {
  const { login, session, status } = useSession();

  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{session?.user_login ?? "anon"}</span>
      <button
        type="button"
        onClick={() => {
          void login({ login: "support2", password: "secret" });
        }}
      >
        login support
      </button>
    </div>
  );
}


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("SessionProvider", () => {
  it("hydrates authenticated session data from /api/web/session/me", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: {
            user_login: "admin1",
            actor_role: "admin",
            auth_type: "ui_token",
            default_workspace: "admin",
            available_workspaces: ["admin", "support"]
          }
        })
      )
    );

    render(
      <SessionProvider>
        <SessionProbe />
      </SessionProvider>
    );

    expect(await screen.findByText("authenticated")).toBeInTheDocument();
    expect(screen.getByText("admin1")).toBeInTheDocument();
  });

  it("falls back to anonymous status when the session is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: null
        })
      )
    );

    render(
      <SessionProvider>
        <SessionProbe />
      </SessionProvider>
    );

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(screen.getByText("anon")).toBeInTheDocument();
  });

  it("ignores stale bootstrap responses after a newer login succeeds", async () => {
    let resolveBootstrap!: (response: Response) => void;
    const bootstrapResponse = new Promise<Response>((resolve) => {
      resolveBootstrap = resolve;
    });

    vi.stubGlobal(
      "fetch",
      vi.fn((input: unknown, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/web/session/me") {
          return bootstrapResponse;
        }
        if (url === "/api/web/session/login" && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse({
              status: "success",
              data: {
                user_login: "support2",
                actor_role: "support",
                auth_type: "ui_token",
                default_workspace: "support",
                available_workspaces: ["support"]
              }
            })
          );
        }
        return Promise.resolve(jsonResponse({ status: "error", error: "unexpected fetch" }, 404));
      })
    );

    render(
      <SessionProvider>
        <LoginProbe />
      </SessionProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "login support" }));

    expect(await screen.findByText("support2")).toBeInTheDocument();

    await act(async () => {
      resolveBootstrap(
        jsonResponse({
          status: "success",
          data: {
            user_login: "admin1",
            actor_role: "admin",
            auth_type: "ui_token",
            default_workspace: "admin",
            available_workspaces: ["admin", "support"]
          }
        })
      );
      await bootstrapResponse;
    });

    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("user")).toHaveTextContent("support2");
  });
});

import { render, screen } from "@testing-library/react";
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
            auth_type: "ui_token"
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
});

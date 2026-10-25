import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider, useSession } from "./session-provider";
import type { WebSession } from "./api";

function renderSession(children: ReactNode) {
  return render(<SessionProvider>{children}</SessionProvider>);
}

const requesterA: WebSession = {
  user_login: "requester-a", actor_role: "user", auth_type: "web_session",
  default_workspace: "requester", available_workspaces: ["requester"],
  permissions: ["workspace.requester.view"], permissions_version: "1"
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function CacheProbe({ read, mutate }: { read: (context: { signal: AbortSignal }) => Promise<string>; mutate?: () => Promise<string> }) {
  const { session, status, login, logout, refreshSession } = useSession();
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ["requester", "profile"], queryFn: read, enabled: status === "authenticated", retry: false, staleTime: Infinity });
  const update = useMutation({ mutationFn: mutate, onSuccess: (value) => client.setQueryData(["requester", "profile"], value) });
  return <>
    <span data-testid="actor">{session?.user_login ?? status}</span>
    <span data-testid="profile">{profile.data ?? "no profile"}</span>
    <input aria-label="draft" defaultValue="" />
    <button onClick={() => { void login({ login: "requester-b", password: "fixture" }).catch(() => {}); }}>switch actor</button>
    <button onClick={() => { void logout().catch(() => {}); }}>logout</button>
    <button onClick={() => { void refreshSession().catch(() => {}); }}>refresh</button>
    <button onClick={() => update.mutate()}>update profile</button>
  </>;
}

function mockSessions(nextSession: () => WebSession | null) {
  vi.stubGlobal("fetch", vi.fn(async (input: unknown) => {
    const url = String(input);
    return jsonResponse({ status: "success", data: url.endsWith("/logout") ? null : nextSession() });
  }));
}


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

    renderSession(
        <SessionProbe />
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

    renderSession(
        <SessionProbe />
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

    renderSession(
        <LoginProbe />
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

  it("does not expose the previous actor profile when the next actor read is forbidden", async () => {
    let actor = requesterA;
    mockSessions(() => actor);
    const read = vi.fn(async () => {
      if (actor.user_login !== "requester-a") throw new Error("Forbidden");
      return "Private profile A";
    });
    renderSession(<CacheProbe read={read} />);
    expect(await screen.findByText("Private profile A")).toBeInTheDocument();

    actor = { ...requesterA, user_login: "requester-b" };
    fireEvent.click(screen.getByRole("button", { name: "switch actor" }));
    await waitFor(() => expect(screen.getByTestId("actor")).toHaveTextContent("requester-b"));
    expect(screen.getByTestId("profile")).toHaveTextContent("no profile");
    expect(screen.queryByText("Private profile A")).not.toBeInTheDocument();
  });

  it("isolates late mutation callbacks from the next actor cache", async () => {
    let actor = requesterA;
    mockSessions(() => actor);
    const pending = deferred<string>();
    renderSession(<CacheProbe read={async () => "Initial profile"} mutate={() => pending.promise} />);
    expect(await screen.findByText("Initial profile")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "update profile" }));
    actor = { ...requesterA, user_login: "requester-b" };
    fireEvent.click(screen.getByRole("button", { name: "switch actor" }));
    await waitFor(() => expect(screen.getByTestId("actor")).toHaveTextContent("requester-b"));
    await act(async () => {
      pending.resolve("Private mutation A");
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.queryByText("Private mutation A")).not.toBeInTheDocument();
  });

  it("discards the previous actor's entered draft when the account changes", async () => {
    let actor = requesterA;
    mockSessions(() => actor);
    renderSession(<CacheProbe read={async () => "Profile"} />);
    expect(await screen.findByText("requester-a")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "draft" }), { target: { value: "Private unsaved draft A" } });
    expect(screen.getByRole("textbox", { name: "draft" })).toHaveValue("Private unsaved draft A");
    actor = { ...requesterA, user_login: "requester-b" };
    fireEvent.click(screen.getByRole("button", { name: "switch actor" }));
    await waitFor(() => expect(screen.getByTestId("actor")).toHaveTextContent("requester-b"));
    expect(screen.getByRole("textbox", { name: "draft" })).toHaveValue("");
  });

  it("cancels an old actor read and ignores its late result after switching", async () => {
    let actor = requesterA;
    mockSessions(() => actor);
    const pending = deferred<string>();
    let oldSignal: AbortSignal | undefined;
    renderSession(<CacheProbe read={({ signal }) => {
      if (actor.user_login === "requester-a") {
        oldSignal = signal;
        return pending.promise;
      }
      return Promise.resolve("Profile B");
    }} />);
    await waitFor(() => expect(oldSignal).toBeDefined());
    actor = { ...requesterA, user_login: "requester-b" };
    fireEvent.click(screen.getByRole("button", { name: "switch actor" }));
    expect(await screen.findByText("Profile B")).toBeInTheDocument();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      pending.resolve("Private profile A");
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.getByTestId("profile")).toHaveTextContent("Profile B");
  });

  it.each([
    ["logout", null],
    ["expired session", null],
    ["role change", { ...requesterA, actor_role: "support" }],
    ["authentication change", { ...requesterA, auth_type: "ui_token" }],
    ["permissions change", { ...requesterA, permissions: [] }],
    ["permissions version change", { ...requesterA, permissions_version: "2" }]
  ] satisfies Array<[string, WebSession | null]>)("discards private cached data after %s", async (transition, nextSession) => {
    let actor: WebSession | null = requesterA;
    mockSessions(() => actor);
    let firstRead = true;
    renderSession(<CacheProbe read={async () => {
      if (!firstRead) throw new Error("Forbidden");
      firstRead = false;
      return "Private profile A";
    }} />);
    expect(await screen.findByText("Private profile A")).toBeInTheDocument();
    actor = nextSession;
    fireEvent.click(screen.getByRole("button", { name: transition === "logout" ? "logout" : "refresh" }));
    await waitFor(() => expect(screen.queryByText("Private profile A")).not.toBeInTheDocument());
  });

  it("preserves cached data on a refresh with the same actor and authorization", async () => {
    mockSessions(() => ({ ...requesterA }));
    const read = vi.fn(async () => "Private profile A");
    renderSession(<CacheProbe read={read} />);
    expect(await screen.findByText("Private profile A")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "draft" }), { target: { value: "Unsaved draft A" } });
    fireEvent.click(screen.getByRole("button", { name: "refresh" }));
    await act(async () => {});
    expect(screen.getByText("Private profile A")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "draft" })).toHaveValue("Unsaved draft A");
    expect(read).toHaveBeenCalledTimes(1);
  });

  it.each(["logout", "switch actor", "refresh"])("keeps the current session and cache when %s fails", async (action) => {
    mockSessions(() => requesterA);
    const read = vi.fn(async () => "Private profile A");
    renderSession(<CacheProbe read={read} />);
    expect(await screen.findByText("Private profile A")).toBeInTheDocument();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ status: "error", error: "Unavailable" }, 503)));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: action })); });
    expect(screen.getByTestId("actor")).toHaveTextContent("requester-a");
    expect(screen.getByText("Private profile A")).toBeInTheDocument();
    expect(read).toHaveBeenCalledTimes(1);
  });
});

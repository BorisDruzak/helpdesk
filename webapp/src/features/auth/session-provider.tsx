import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createAppQueryClient, QueryProvider } from "../../app/providers/query-provider";
import { clearPendingDeviceCode } from "../requester/device-link-state";

import {
  fetchCurrentSession,
  loginWebSession,
  logoutWebSession,
  type WebSession
} from "./api";


type SessionStatus = "loading" | "authenticated" | "anonymous";

type SessionContextValue = {
  session: WebSession | null;
  status: SessionStatus;
  refreshSession: () => Promise<void>;
  login: (credentials: { login: string; password: string }) => Promise<WebSession>;
  logout: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);


type SessionProviderProps = {
  children: ReactNode;
};

function sessionCacheIdentity(session: WebSession | null) {
  return session ? JSON.stringify([
    session.user_login,
    session.actor_role,
    session.auth_type,
    session.permissions_version ?? null,
    [...(session.permissions ?? [])].sort(),
    [...session.available_workspaces].sort(),
    session.default_workspace
  ]) : null;
}

export function SessionProvider({ children }: SessionProviderProps) {
  const [session, setSession] = useState<WebSession | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const sessionRequestVersion = useRef(0);
  const [cache, setCache] = useState(() => ({ client: createAppQueryClient(), version: 0 }));
  const currentBoundary = useRef({ identity: sessionCacheIdentity(null), ...cache });

  function applySession(nextSession: WebSession | null) {
    const identity = sessionCacheIdentity(nextSession);
    const previous = currentBoundary.current;
    if (identity !== previous.identity) {
      // clear() cancels old queries, but mutation callbacks can still finish.
      // Give the new actor a separate client and remount observers/drafts so
      // those callbacks retain only the retired actor's cache and closures.
      previous.client.clear();
      const nextCache = { client: createAppQueryClient(), version: previous.version + 1 };
      currentBoundary.current = { identity, ...nextCache };
      setCache(nextCache);
    }
    setSession(nextSession);
    setStatus(nextSession ? "authenticated" : "anonymous");
  }

  async function refreshSession() {
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    const currentSession = await fetchCurrentSession();
    if (requestVersion !== sessionRequestVersion.current) {
      return;
    }

    applySession(currentSession);
  }

  async function login(credentials: { login: string; password: string }) {
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    const nextSession = await loginWebSession(credentials);
    if (requestVersion !== sessionRequestVersion.current) {
      return nextSession;
    }
    applySession(nextSession);
    return nextSession;
  }

  async function logout() {
    clearPendingDeviceCode();
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    await logoutWebSession();
    if (requestVersion !== sessionRequestVersion.current) {
      return;
    }
    applySession(null);
  }

  useEffect(() => {
    let active = true;
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;

    void (async () => {
      try {
        const currentSession = await fetchCurrentSession();
        if (!active || requestVersion !== sessionRequestVersion.current) {
          return;
        }
        applySession(currentSession);
      } catch {
        if (!active || requestVersion !== sessionRequestVersion.current) {
          return;
        }
        applySession(null);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return (
    <SessionContext.Provider
      value={{
        session,
        status,
        refreshSession,
        login,
        logout
      }}
    >
      <QueryProvider client={cache.client} key={cache.version}>
        {children}
      </QueryProvider>
    </SessionContext.Provider>
  );
}


export function useSession() {
  const context = useContext(SessionContext);

  if (!context) {
    throw new Error("useSession must be used inside SessionProvider.");
  }

  return context;
}

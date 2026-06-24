import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

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


export function SessionProvider({ children }: SessionProviderProps) {
  const [session, setSession] = useState<WebSession | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const sessionRequestVersion = useRef(0);

  async function refreshSession() {
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    const currentSession = await fetchCurrentSession();
    if (requestVersion !== sessionRequestVersion.current) {
      return;
    }

    setSession(currentSession);
    setStatus(currentSession ? "authenticated" : "anonymous");
  }

  async function login(credentials: { login: string; password: string }) {
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    const nextSession = await loginWebSession(credentials);
    if (requestVersion !== sessionRequestVersion.current) {
      return nextSession;
    }
    setSession(nextSession);
    setStatus("authenticated");
    return nextSession;
  }

  async function logout() {
    const requestVersion = sessionRequestVersion.current + 1;
    sessionRequestVersion.current = requestVersion;
    await logoutWebSession();
    if (requestVersion !== sessionRequestVersion.current) {
      return;
    }
    setSession(null);
    setStatus("anonymous");
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
        setSession(currentSession);
        setStatus(currentSession ? "authenticated" : "anonymous");
      } catch {
        if (!active || requestVersion !== sessionRequestVersion.current) {
          return;
        }
        setSession(null);
        setStatus("anonymous");
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
      {children}
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

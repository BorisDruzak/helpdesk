import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

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

  async function refreshSession() {
    const currentSession = await fetchCurrentSession();

    setSession(currentSession);
    setStatus(currentSession ? "authenticated" : "anonymous");
  }

  async function login(credentials: { login: string; password: string }) {
    const nextSession = await loginWebSession(credentials);
    setSession(nextSession);
    setStatus("authenticated");
    return nextSession;
  }

  async function logout() {
    await logoutWebSession();
    setSession(null);
    setStatus("anonymous");
  }

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const currentSession = await fetchCurrentSession();
        if (!active) {
          return;
        }
        setSession(currentSession);
        setStatus(currentSession ? "authenticated" : "anonymous");
      } catch {
        if (!active) {
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

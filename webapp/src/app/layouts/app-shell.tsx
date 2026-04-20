import { startTransition, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useSession } from "../../features/auth/session-provider";


type AppShellProps = {
  children: ReactNode;
};


export function AppShell({ children }: AppShellProps) {
  const navigate = useNavigate();
  const { logout, session } = useSession();

  async function handleLogout() {
    await logout();
    startTransition(() => {
      navigate("/app/login", { replace: true });
    });
  }

  return (
    <div className="app-shell">
      <aside className="app-shell__rail">
        <div className="app-shell__brand">
          <span className="app-shell__eyebrow">pc_client</span>
          <strong>Платформа рабочих мест</strong>
        </div>
        <div className="app-shell__session-card">
          <span className="app-shell__session-login">{session?.user_login}</span>
          <span className="app-shell__session-role">{session?.actor_role}</span>
          <button className="app-shell__session-action" onClick={() => void handleLogout()} type="button">
            Выйти
          </button>
        </div>
        <nav className="app-shell__nav" aria-label="Навигация по рабочим местам">
          <NavLink className="app-shell__link" to="/app/support">
            Поддержка
          </NavLink>
          <NavLink className="app-shell__link" to="/app/admin">
            Администрирование
          </NavLink>
        </nav>
      </aside>
      <main className="app-shell__main">{children}</main>
    </div>
  );
}

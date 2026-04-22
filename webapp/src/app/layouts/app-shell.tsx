import { startTransition, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useSession } from "../../features/auth/session-provider";
import { hasWorkspaceAccess } from "../../features/auth/workspace-access";


type AppShellProps = {
  children: ReactNode;
};

type RailIconKind = "support" | "admin";

function RailIcon({ kind }: { kind: RailIconKind }) {
  if (kind === "support") {
    return (
      <svg aria-hidden="true" className="app-shell__link-icon-svg" viewBox="0 0 24 24">
        <path
          d="M5 7.5A2.5 2.5 0 0 1 7.5 5h9A2.5 2.5 0 0 1 19 7.5v6A2.5 2.5 0 0 1 16.5 16h-6.2L6 19.8V16.3A2.5 2.5 0 0 1 5 14.2z"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="app-shell__link-icon-svg" viewBox="0 0 24 24">
      <path
        d="M5 5h6v6H5zm8 0h6v6h-6zM5 13h6v6H5zm8 3h6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M16 11v8m-4-4h8"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function deriveUserInitials(value: string | null | undefined) {
  if (!value) {
    return "PC";
  }

  const parts = value
    .split(/[\s._-]+/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (!parts.length) {
    return value.slice(0, 2).toUpperCase();
  }

  return parts
    .slice(0, 2)
    .map((item) => item[0]?.toUpperCase() ?? "")
    .join("");
}

function deriveRoleLabel(value: string | null | undefined) {
  if (value === "admin") {
    return "Администратор";
  }

  if (value === "support") {
    return "Поддержка";
  }

  return value ?? "Оператор";
}

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
        <div className="app-shell__brand-card">
          <div aria-hidden="true" className="app-shell__logo">
            <span>PC</span>
          </div>
          <div className="app-shell__brand-copy">
            <span className="app-shell__eyebrow">pc_client</span>
            <strong>Единое рабочее пространство</strong>
            <p>Поддержка и администрирование в одном операционном контуре.</p>
          </div>
        </div>

        <nav className="app-shell__nav" aria-label="Навигация по рабочим местам">
          <span className="app-shell__section-label">Рабочие зоны</span>
          {hasWorkspaceAccess(session, "support") ? (
            <NavLink aria-label="Поддержка" className="app-shell__link" to="/app/support">
              <span className="app-shell__link-icon" aria-hidden="true">
                <RailIcon kind="support" />
              </span>
              <span className="app-shell__link-copy">
                <strong>Поддержка</strong>
                <small>Очередь, тикеты, инструменты</small>
              </span>
            </NavLink>
          ) : null}
          {hasWorkspaceAccess(session, "admin") ? (
            <NavLink aria-label="Администрирование" className="app-shell__link" to="/app/admin">
              <span className="app-shell__link-icon" aria-hidden="true">
                <RailIcon kind="admin" />
              </span>
              <span className="app-shell__link-copy">
                <strong>Администрирование</strong>
                <small>Инвентарь, раскатка, реестр</small>
              </span>
            </NavLink>
          ) : null}
        </nav>

        <div className="app-shell__session-card">
          <div className="app-shell__session-user">
            <div aria-hidden="true" className="app-shell__session-avatar">
              {deriveUserInitials(session?.user_login)}
            </div>
            <div className="app-shell__session-copy">
              <span className="app-shell__session-login">{session?.user_login}</span>
              <span className="app-shell__session-role">{deriveRoleLabel(session?.actor_role)}</span>
            </div>
          </div>
          <button className="app-shell__session-action" onClick={() => void handleLogout()} type="button">
            Выйти
          </button>
        </div>
      </aside>

      <main className="app-shell__main">{children}</main>
    </div>
  );
}

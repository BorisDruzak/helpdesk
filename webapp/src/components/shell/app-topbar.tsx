import { Bell, ChevronDown, LogOut, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import type { ChangeEvent } from "react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { SearchField } from "../ui/search-field";
import { Button } from "../ui/button";
import { Select } from "../ui/select";
import { fetchAdminConnectionRequests } from "../../features/admin/api";

type WorkspaceOption = {
  label: string;
  value: string;
};

type AppTopbarProps = {
  onLogout: () => void;
  onWorkspaceChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  searchPlaceholder: string;
  userLogin: string;
  userRoleLabel: string;
  workspaceOptions: WorkspaceOption[];
  workspaceValue: string;
};

async function fetchUnreadNotificationCount(): Promise<number> {
  const response = await fetch("/api/notifications/unread_count", {
    credentials: "same-origin"
  });
  if (!response.ok) {
    return 0;
  }
  const payload = (await response.json()) as { status?: string; unread_count?: number };
  if (payload.status !== "ok") {
    return 0;
  }
  return Number(payload.unread_count ?? 0);
}

export function AppTopbar({
  onLogout,
  onWorkspaceChange,
  searchPlaceholder,
  userLogin,
  userRoleLabel,
  workspaceOptions,
  workspaceValue
}: AppTopbarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const isAdminWorkspace = location.pathname.startsWith("/app/admin");

  const unreadNotificationsQuery = useQuery({
    queryKey: ["shell-notifications-unread"],
    queryFn: fetchUnreadNotificationCount,
    retry: false,
    refetchInterval: 15_000
  });

  const pendingConnectionsQuery = useQuery({
    queryKey: ["shell-pending-connection-requests"],
    queryFn: fetchAdminConnectionRequests,
    enabled: isAdminWorkspace,
    retry: false,
    refetchInterval: 5_000
  });

  const unreadCount = unreadNotificationsQuery.data ?? 0;
  const pendingConnections = pendingConnectionsQuery.data?.connection_requests ?? [];
  const notificationCount = unreadCount + pendingConnections.length;

  function openAgentRequests() {
    setNotificationsOpen(false);
    navigate("/app/admin/inventory?panel=requests");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border/80 bg-white/80 backdrop-blur-xl">
      <div className="flex flex-col gap-4 px-4 py-4 md:px-6 xl:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
                Верхняя шторка
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Рабочая зона, выход и глобальный поиск теперь живут здесь.
              </p>
            </div>

            <div className="relative">
              <Select
                aria-label="Рабочая зона"
                className="min-w-[220px] bg-brand-50 pr-12 text-brand-900"
                onChange={onWorkspaceChange}
                value={workspaceValue}
              >
                {workspaceOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-500" />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="w-full max-w-[420px] flex-1">
              <SearchField placeholder={searchPlaceholder} />
            </div>

            <div className="relative">
              <button
                aria-label="Уведомления"
                className="relative flex h-11 w-11 items-center justify-center rounded-pill border border-border bg-white text-slate-500 transition-colors hover:border-brand-200 hover:text-brand-700"
                onClick={() => setNotificationsOpen((value) => !value)}
                type="button"
              >
                <Bell className="h-4 w-4" />
                {notificationCount > 0 ? (
                  <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">
                    {notificationCount > 99 ? "99+" : notificationCount}
                  </span>
                ) : null}
              </button>

              {notificationsOpen ? (
                <div className="absolute right-0 top-12 z-30 w-[340px] overflow-hidden rounded-2xl border border-border bg-white shadow-soft">
                  <div className="border-b border-border px-4 py-3">
                    <p className="text-sm font-semibold text-slate-950">Уведомления</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {notificationCount > 0 ? `Новых событий: ${notificationCount}` : "Новых событий нет"}
                    </p>
                  </div>

                  {pendingConnections.length > 0 ? (
                    <div className="border-b border-border px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase text-slate-400">Подключения</p>
                        <button
                          className="text-xs font-semibold text-brand-700 hover:text-brand-900"
                          onClick={openAgentRequests}
                          type="button"
                        >
                          Открыть
                        </button>
                      </div>
                      <div className="mt-3 space-y-2">
                        {pendingConnections.slice(0, 3).map((request) => (
                          <button
                            className="w-full rounded-xl bg-amber-50 px-3 py-2 text-left hover:bg-amber-100"
                            key={request.device_id}
                            onClick={openAgentRequests}
                            type="button"
                          >
                            <p className="text-sm font-semibold text-amber-950">
                              {request.hostname || request.device_id.slice(0, 8)}
                            </p>
                            <p className="mt-0.5 text-xs text-amber-800">
                              {request.ip_address || "Новый агент"} ожидает одобрения
                            </p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="px-4 py-3">
                    <button
                      className="w-full rounded-xl border border-border px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
                      onClick={() => {
                        setNotificationsOpen(false);
                        navigate(isAdminWorkspace ? "/app/admin/settings" : "/app/settings");
                      }}
                      type="button"
                    >
                      Тикетные уведомления: {unreadCount}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="hidden items-center gap-3 rounded-pill border border-border bg-white px-4 py-2.5 md:flex">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-brand-800">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="leading-tight">
                <p className="text-sm font-semibold text-slate-900">{userLogin}</p>
                <p className="text-xs text-slate-500">{userRoleLabel}</p>
              </div>
            </div>

            <Button
              className="shrink-0"
              leadingIcon={<LogOut className="h-4 w-4" />}
              onClick={onLogout}
              size="sm"
              variant="outline"
            >
              Выйти
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}

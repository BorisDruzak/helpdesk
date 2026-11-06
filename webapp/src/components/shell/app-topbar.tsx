import { ChevronDown, CircleUserRound, LogOut } from "lucide-react";
import type { ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { NotificationBell } from "../../features/notifications/notification-bell";

import { SearchField } from "../ui/search-field";
import { Button } from "../ui/button";
import { Select } from "../ui/select";

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

export function AppTopbar({
  onLogout,
  onWorkspaceChange,
  searchPlaceholder,
  userLogin,
  userRoleLabel,
  workspaceOptions,
  workspaceValue
}: AppTopbarProps) {
  if (workspaceValue === "requester") return (
    <header className="requester-topbar">
      {workspaceOptions.length > 1 ? <Select aria-label="Рабочая зона" className="h-10 max-w-full bg-transparent text-sm text-slate-600" onChange={onWorkspaceChange} value={workspaceValue}>
        {workspaceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </Select> : <span className="text-sm text-slate-500">Кабинет сотрудника</span>}
      <div className="requester-topbar__account">
        <NotificationBell requester userLogin={userLogin} />
        <details className="relative">
          <summary aria-label="Меню профиля" className="flex cursor-pointer list-none items-center gap-2"><span className="requester-topbar__avatar">{userLogin.slice(0, 2).toUpperCase()}</span><span className="hidden sm:inline">{userLogin}</span></summary>
          <div className="requester-topbar__menu"><Link className="block rounded px-3 py-2 hover:bg-brand-50" to="/app/requester/profile">Мой профиль</Link><button className="w-full rounded px-3 py-2 text-left hover:bg-brand-50" type="button" onClick={onLogout}>Выйти</button></div>
        </details>
      </div>
    </header>
  );

  return (
    <header className="sticky top-0 z-20 border-b border-border/80 bg-white/80 backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 md:px-6 xl:px-8">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            {workspaceOptions.length > 1 ? (
              <div className="relative">
                <Select
                  aria-label="Рабочая зона"
                  className="h-10 min-w-[220px] bg-brand-50 pr-12 text-brand-900"
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
            ) : null}
          </div>

          <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 md:flex md:flex-wrap xl:w-auto">
            <div className="col-span-2 min-w-0 md:w-full md:min-w-[240px] md:max-w-[420px] md:flex-1">
              <SearchField placeholder={searchPlaceholder} />
            </div>

            <NotificationBell requester={false} userLogin={userLogin} />

            <div className="hidden items-center gap-3 rounded-panel border border-border bg-white px-3 py-2 md:flex">
              <div className="flex h-9 w-9 items-center justify-center rounded-panel bg-brand-100 text-brand-800">
                <CircleUserRound className="h-4 w-4" />
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

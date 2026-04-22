import { Bell, ChevronDown, LogOut, Sparkles } from "lucide-react";
import type { ChangeEvent } from "react";

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

            <button
              className="flex h-11 w-11 items-center justify-center rounded-pill border border-border bg-white text-slate-500 transition-colors hover:border-brand-200 hover:text-brand-700"
              type="button"
            >
              <Bell className="h-4 w-4" />
            </button>

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

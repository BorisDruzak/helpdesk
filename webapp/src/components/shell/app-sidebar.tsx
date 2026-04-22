import { NavLink } from "react-router-dom";

import { appNavigation } from "../../app/navigation";
import { cn } from "../../shared/ui/cn";

type AppSidebarProps = {
  hasAdminAccess: boolean;
  hasSupportAccess: boolean;
};

function SidebarGroup({
  items,
  label
}: {
  items: typeof appNavigation;
  label: string;
}) {
  return (
    <div className="space-y-3">
      <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-100/70">
        {label}
      </p>
      <div className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-start gap-3 rounded-panel px-3 py-3 text-sm transition-colors",
                  isActive
                    ? "bg-white text-brand-900 shadow-soft"
                    : "text-brand-50/90 hover:bg-white/10 hover:text-white"
                )
              }
              end
              to={item.to}
            >
              <span className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/14 text-current transition-colors">
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 space-y-1">
                <span className="block font-semibold leading-none">{item.label}</span>
                <span className="block text-xs leading-5 text-current/70">{item.description}</span>
              </span>
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

export function AppSidebar({
  hasAdminAccess,
  hasSupportAccess
}: AppSidebarProps) {
  const supportItems = appNavigation.filter((item) => item.section === "support");
  const adminItems = appNavigation.filter((item) => item.section === "admin");

  return (
    <aside className="hidden w-[248px] shrink-0 border-r border-white/10 bg-brand-700 px-4 py-5 text-white lg:flex lg:flex-col">
      <div className="mb-8 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-4 py-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-700 shadow-soft">
          <span className="text-base font-black tracking-[0.18em]">PC</span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-100/70">
            pc_client
          </p>
          <p className="font-display text-lg font-semibold leading-tight">HelpDesk workspace</p>
          <p className="text-xs leading-5 text-brand-50/70">
            Единый shell для поддержки и администрирования.
          </p>
        </div>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto pr-1">
        {hasSupportAccess ? <SidebarGroup items={supportItems} label="Support" /> : null}
        {hasAdminAccess ? <SidebarGroup items={adminItems} label="Admin" /> : null}
      </div>

      <div className="mt-6 rounded-panel border border-white/10 bg-white/8 px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-100/70">
          Workspace note
        </p>
        <p className="mt-2 text-sm leading-6 text-brand-50/85">
          Светлый canvas, плотная рабочая панель и один визуальный язык для всех зон.
        </p>
      </div>
    </aside>
  );
}

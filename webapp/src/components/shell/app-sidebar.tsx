import { NavLink } from "react-router-dom";

import { appNavigation } from "../../app/navigation";
import { hasPermission } from "../../features/auth/permissions";
import { cn } from "../../shared/ui/cn";

type AppSidebarProps = {
  hasAdminAccess: boolean;
  hasSupportAccess: boolean;
  permissions?: string[];
};

function SidebarGroup({
  items,
  label
}: {
  items: typeof appNavigation;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-100/70">
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
                  "flex items-start gap-3 rounded-panel px-3 py-2.5 text-sm transition-colors",
                  isActive
                    ? "bg-white text-brand-900 shadow-soft"
                    : "text-brand-50/90 hover:bg-white/10 hover:text-white"
                )
              }
              end
              to={item.to}
            >
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-panel bg-white/14 text-current transition-colors">
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 space-y-1">
                <span className="block font-semibold leading-none">{item.label}</span>
                <span className="block text-xs leading-4 text-current/70">{item.description}</span>
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
  hasSupportAccess,
  permissions = []
}: AppSidebarProps) {
  const canShowItem = (item: (typeof appNavigation)[number]) =>
    !item.permission || hasPermission({ permissions }, item.permission);
  const supportItems = appNavigation.filter((item) => item.section === "support" && canShowItem(item));
  const adminItems = appNavigation.filter((item) => item.section === "admin" && canShowItem(item));

  return (
    <aside className="hidden w-[236px] shrink-0 border-r border-white/10 bg-brand-700 px-3 py-4 text-white lg:flex lg:flex-col">
      <div className="mb-5 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-3 py-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-panel bg-white text-brand-700 shadow-soft">
          <span className="text-base font-black tracking-[0.18em]">PC</span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-100/70">
            pc_client
          </p>
          <p className="text-sm font-semibold leading-tight">HelpDesk workspace</p>
        </div>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto pr-1">
        {hasSupportAccess ? <SidebarGroup items={supportItems} label="Support" /> : null}
        {hasAdminAccess ? <SidebarGroup items={adminItems} label="Admin" /> : null}
      </div>
    </aside>
  );
}

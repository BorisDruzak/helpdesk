import { NavLink } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { appNavigation } from "../../app/navigation";
import { hasPermission } from "../../features/auth/permissions";
import { cn } from "../../shared/ui/cn";

type AppSidebarProps = {
  collapsed?: boolean;
  hasAdminAccess: boolean;
  hasSupportAccess: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  permissions?: string[];
  showCollapseToggle?: boolean;
};

function SidebarGroup({
  collapsed = false,
  items,
  label
}: {
  collapsed?: boolean;
  items: typeof appNavigation;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <p
        className={cn(
          "px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-100/70",
          collapsed ? "sr-only" : ""
        )}
      >
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
                  collapsed ? "justify-center px-2" : "",
                  isActive
                    ? "bg-white text-brand-900 shadow-soft"
                    : "text-brand-50/90 hover:bg-white/10 hover:text-white"
                )
              }
              end
              title={collapsed ? `${item.label}: ${item.description}` : undefined}
              to={item.to}
            >
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-panel bg-white/14 text-current transition-colors">
                <Icon className="h-4 w-4" />
              </span>
              <span className={cn("min-w-0 space-y-1", collapsed ? "sr-only" : "")}>
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
  collapsed = false,
  hasAdminAccess,
  hasSupportAccess,
  onCollapsedChange,
  permissions = [],
  showCollapseToggle = false
}: AppSidebarProps) {
  const canShowItem = (item: (typeof appNavigation)[number]) =>
    !item.permission || hasPermission({ permissions }, item.permission);
  const supportItems = appNavigation.filter((item) => item.section === "support" && canShowItem(item));
  const adminItems = appNavigation.filter((item) => item.section === "admin" && canShowItem(item));
  const ToggleIcon = collapsed ? ChevronRight : ChevronLeft;

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r border-white/10 bg-brand-700 px-3 py-4 text-white transition-[width] duration-200 lg:flex lg:flex-col",
        collapsed ? "w-16" : "w-[236px]"
      )}
    >
      <div
        className={cn(
          "mb-5 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-3 py-3",
          collapsed ? "justify-center px-2" : ""
        )}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-panel bg-white text-brand-700 shadow-soft">
          <span className={cn("text-base font-black", collapsed ? "tracking-normal" : "tracking-[0.18em]")}>
            {collapsed ? "PC" : "PC"}
          </span>
        </div>
        <div className={cn("min-w-0", collapsed ? "sr-only" : "")}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-100/70">
            pc_client
          </p>
          <p className="text-sm font-semibold leading-tight">HelpDesk workspace</p>
        </div>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto pr-1">
        {hasSupportAccess ? <SidebarGroup collapsed={collapsed} items={supportItems} label="Support" /> : null}
        {hasAdminAccess ? <SidebarGroup collapsed={collapsed} items={adminItems} label="Admin" /> : null}
      </div>

      {showCollapseToggle ? (
        <button
          aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          className={cn(
            "mt-4 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/14",
            collapsed ? "justify-center px-2" : ""
          )}
          onClick={() => onCollapsedChange?.(!collapsed)}
          title={collapsed ? "Развернуть меню" : "Свернуть меню"}
          type="button"
        >
          <ToggleIcon className="h-4 w-4" />
          <span className={collapsed ? "sr-only" : ""}>
            {collapsed ? "Развернуть меню" : "Свернуть меню"}
          </span>
        </button>
      ) : null}
    </aside>
  );
}

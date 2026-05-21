import { Link, useLocation } from "react-router-dom";

import {
  canUseNavigationItemInContext,
  getActiveNavigationDomain,
  isNavItemActive,
  resolveNavigationItemTarget,
} from "../../app/navigation";
import { cn } from "../../shared/ui/cn";

type DomainTabsProps = {
  permissions: string[];
};

export function DomainTabs({ permissions }: DomainTabsProps) {
  const location = useLocation();
  const activeDomain = getActiveNavigationDomain(location.pathname, permissions);

  if (!activeDomain || activeDomain.items.length < 2) {
    return null;
  }

  const currentPath = `${location.pathname}${location.search}${location.hash}`;

  return (
    <nav
      aria-label={`Раздел: ${activeDomain.label}`}
      className="mb-4 overflow-x-auto border-b border-border/80"
    >
      <div className="flex min-w-max items-center gap-1">
        {activeDomain.items.map((item) => {
          const isAvailable = canUseNavigationItemInContext(item, currentPath);
          const target = resolveNavigationItemTarget(item, currentPath);
          const isActive = isAvailable && isNavItemActive(item, currentPath);

          if (!isAvailable || !target) {
            return (
              <span
                aria-disabled="true"
                className="cursor-not-allowed border-b-2 border-transparent px-3 py-2 text-sm font-semibold text-slate-300"
                key={item.to}
                title="Откройте операции из инвентаря или карточки устройства"
              >
                {item.shortLabel ?? item.label}
              </span>
            );
          }

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "border-b-2 px-3 py-2 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2",
                isActive
                  ? "border-brand-700 text-brand-800"
                  : "border-transparent text-slate-500 hover:border-brand-200 hover:text-brand-700",
              )}
              key={item.to}
              to={target}
            >
              {item.shortLabel ?? item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

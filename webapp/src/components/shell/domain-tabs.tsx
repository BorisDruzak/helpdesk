import { Link, useLocation } from "react-router-dom";

import { getActiveNavigationDomain, isNavItemActive } from "../../app/navigation";
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
          const isActive = isNavItemActive(item, currentPath);

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
              to={item.to}
            >
              {item.shortLabel ?? item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

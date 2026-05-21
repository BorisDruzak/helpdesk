import { Link } from "react-router-dom";

import { appNavigationDomains, findFirstVisibleDomainItem } from "../../app/navigation";
import { useSession } from "../../features/auth/session-provider";
import { AdminWorkspace } from "../../features/admin/admin-workspace";
import { cn } from "../../shared/ui/cn";

const ADMIN_DOMAIN_ORDER = appNavigationDomains
  .filter((domain) => domain.workspace === "admin")
  .sort((left, right) => left.order - right.order);

export function AdminCenterPage() {
  const { session } = useSession();
  const permissions = session?.permissions ?? [];
  const cards = ADMIN_DOMAIN_ORDER.map((domain) => {
    const firstItem = findFirstVisibleDomainItem(domain.id, permissions);
    return firstItem ? { domain, firstItem } : null;
  }).filter(Boolean) as Array<{
    domain: (typeof ADMIN_DOMAIN_ORDER)[number];
    firstItem: NonNullable<ReturnType<typeof findFirstVisibleDomainItem>>;
  }>;

  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-panel border border-border bg-white px-5 py-5 shadow-soft md:px-6">
        <p className="text-xs font-semibold uppercase text-brand-700">Admin</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Центр администрирования</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          Карта доменов service desk: устройства, каталог заявок, знания, автоматизация, управление сервисом и системные настройки.
        </p>
      </div>

      {cards.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map(({ domain, firstItem }) => {
            const Icon = domain.icon;

            return (
              <Link
                className={cn(
                  "group rounded-panel border border-border bg-white p-5 shadow-soft transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-lg focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2",
                )}
                key={domain.id}
                to={firstItem.to}
              >
                <div className="flex items-start gap-4">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-panel bg-brand-50 text-brand-700">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-base font-semibold text-slate-950 group-hover:text-brand-800">
                      {domain.label}
                    </span>
                    <span className="mt-1 block text-sm leading-6 text-slate-600">{domain.description}</span>
                    <span className="mt-3 block text-xs font-semibold uppercase text-brand-700">
                      Открыть: {firstItem.label}
                    </span>
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className="rounded-panel border border-dashed border-border bg-white px-5 py-6 text-sm text-slate-600">
          Для этой роли нет доступных разделов администрирования.
        </div>
      )}
    </section>
  );
}


export function AdminWorkspacePage() {
  return <AdminWorkspace />;
}

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Monitor, Plus, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  ActionCard,
  ContentSection,
  EmptyState,
  ErrorState,
  PageActions,
  PageHeader,
  PageShell,
  PageSkeleton,
  StatCard,
  StatusBadge,
} from "../../components/ui-page";
import { Card } from "../../components/ui/card";
import { cn } from "../../shared/ui/cn";
import { approveRequesterConsent, denyRequesterConsent } from "../../features/requester/api";
import { RequesterConsentList } from "../../features/requester/consent-card";
import {
  requesterDeviceConnectionStatusLabel,
  requesterDeviceLabel,
  requesterDeviceSystemLabel,
  requesterErrorMessage,
  requesterReadinessText,
} from "../../features/requester/labels";
import {
  projectRequesterDashboard,
  requesterInvalidations,
  useRequesterBootstrapQuery,
  useRequesterConsentsQuery,
  useRequesterTicketsQuery,
} from "../../features/requester/queries";
import type { RequesterConsent } from "../../features/requester/types";

const primaryLinkClasses =
  "inline-flex h-11 items-center justify-center gap-2 rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white shadow-soft transition-colors hover:bg-brand-700";
const secondaryLinkClasses =
  "inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-border bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800";

export function RequesterHomePage() {
  const queryClient = useQueryClient();
  const bootstrapQuery = useRequesterBootstrapQuery();
  const ticketsQuery = useRequesterTicketsQuery();
  const consentsQuery = useRequesterConsentsQuery();
  const [consentNotice, setConsentNotice] = useState<string | null>(null);

  const isLoading = bootstrapQuery.isLoading || ticketsQuery.isLoading || consentsQuery.isLoading;
  const blockingError = bootstrapQuery.error ?? ticketsQuery.error;

  if (isLoading) {
    return (
      <PageShell ariaLabelledBy="requester-home-title">
        <PageSkeleton sections={3} title="Загружаем главную страницу кабинета" />
      </PageShell>
    );
  }

  if (blockingError) {
    return (
      <PageShell ariaLabelledBy="requester-home-title">
        <ErrorState
          message={requesterErrorMessage(blockingError, "Не удалось загрузить главную страницу кабинета.")}
          onRetry={() => {
            void bootstrapQuery.refetch();
            void ticketsQuery.refetch();
            void consentsQuery.refetch();
          }}
          title="Не удалось открыть кабинет"
        />
      </PageShell>
    );
  }

  const bootstrap = bootstrapQuery.data ?? null;
  const tickets = ticketsQuery.data ?? [];
  const consents = consentsQuery.data ?? [];
  const pendingConsents = consents.filter((consent) => consent.status === "pending");
  const dashboard = projectRequesterDashboard(bootstrap, tickets, consents);
  const profileName = bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || "пользователь";
  const primaryDevice = bootstrap?.devices[0] ?? null;
  const nextActionTone = dashboard.nextAction.key === "complete_profile" || dashboard.nextAction.key === "review_consents" ? "warning" : "success";

  async function decideConsent(consent: RequesterConsent, decision: "approved" | "denied") {
    setConsentNotice(null);
    try {
      if (decision === "approved") {
        await approveRequesterConsent(consent.consent_id);
      } else {
        await denyRequesterConsent(consent.consent_id, "requester_denied");
      }
      await requesterInvalidations.afterConsentDecision(queryClient, consent.ticket_id);
      await consentsQuery.refetch();
      setConsentNotice(decision === "approved" ? "Согласие подтверждено" : "Согласие отклонено");
    } catch (exc) {
      setConsentNotice(requesterErrorMessage(exc, "Не удалось сохранить решение"));
    }
  }

  return (
    <PageShell ariaLabelledBy="requester-home-title" className="bg-app">
      <PageHeader
        actions={
          <PageActions>
            <Link className={primaryLinkClasses} to="/app/requester/new">
              <Plus className="h-4 w-4" />
              Создать обращение
            </Link>
          </PageActions>
        }
        description={`Здравствуйте, ${profileName}. Здесь собраны ближайшие действия, обращения и состояние рабочего места.`}
        eyebrow="Кабинет пользователя"
        id="requester-home-title"
        title="Главная"
      />

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <ActionCard
          action={
            <Link className={primaryLinkClasses} to={dashboard.nextAction.href}>
              {dashboard.nextAction.label}
              <ArrowRight className="h-4 w-4" />
            </Link>
          }
          description={requesterReadinessText(dashboard.readiness.profileComplete, dashboard.readiness.hasDeviceContext)}
          meta={<StatusBadge label={dashboard.nextAction.label} status={nextActionTone} tone={nextActionTone} />}
          title="Что сделать сейчас"
        />

        <Card className="flex min-h-full flex-col justify-center p-5">
          <div className="flex items-start gap-3">
            <span
              aria-hidden="true"
              className={cn(
                "mt-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-pill",
                dashboard.readiness.profileComplete && dashboard.readiness.hasDeviceContext
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-amber-50 text-amber-700",
              )}
            >
              {dashboard.readiness.profileComplete && dashboard.readiness.hasDeviceContext ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : (
                <TriangleAlert className="h-5 w-5" />
              )}
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-slate-950">Готовность кабинета</h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {requesterReadinessText(dashboard.readiness.profileComplete, dashboard.readiness.hasDeviceContext)}
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section aria-label="Краткие показатели" className="grid gap-4 md:grid-cols-3">
        <StatCard helper="Активные и ожидающие реакции" label="Открытые обращения" value={dashboard.stats.openTickets} />
        <StatCard helper="Ответы, согласия или проверки" label="Требуется действие" value={dashboard.stats.actionsRequired} />
        <StatCard helper="Доступны для работы в кабинете" label="Устройства" value={dashboard.stats.devices} />
      </section>

      {consentNotice ? (
        <div aria-live="polite" className="rounded-panel border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700" role="status">
          {consentNotice}
        </div>
      ) : null}

      <RequesterConsentList consents={pendingConsents} onDecision={decideConsent} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <ContentSection
          actions={
            <Link className={secondaryLinkClasses} to="/app/requester/tickets">
              Все обращения
            </Link>
          }
          description="Последние обращения и статусы без технических идентификаторов."
          title="Мои обращения"
        >
          {dashboard.recentTickets.length ? (
            <div className="grid gap-3">
              {dashboard.recentTickets.slice(0, 4).map((ticket) => (
                <Link
                  className="surface-panel block min-w-0 px-4 py-3 transition-colors hover:border-brand-200 hover:bg-brand-50"
                  key={ticket.ticketId}
                  to={`/app/requester/tickets/${encodeURIComponent(ticket.ticketId)}`}
                >
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-950">{ticket.displayCode}</span>
                    <StatusBadge label={ticket.statusLabel} status={ticket.statusLabel} />
                  </div>
                  <h3 className="mt-2 text-sm font-semibold text-slate-900">{ticket.title}</h3>
                  <p className="mt-1 text-xs text-slate-500">{ticket.createdAtLabel}</p>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              action={
                <Link className={primaryLinkClasses} to="/app/requester/new">
                  Создать обращение
                </Link>
              }
              description="Когда появится первое обращение, оно будет видно здесь."
              title="Обращений пока нет"
            />
          )}
        </ContentSection>

        <ContentSection
          actions={
            <Link className={secondaryLinkClasses} to="/app/requester/devices">
              Устройства
            </Link>
          }
          description="Основной контекст для обращений и диагностики."
          title="Рабочее место"
        >
          <Card className="p-5">
            <div className="flex items-start gap-3">
              <span aria-hidden="true" className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-pill bg-brand-50 text-brand-700">
                <Monitor className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <h3 className="break-words text-base font-semibold text-slate-950">{primaryDevice ? requesterDeviceLabel(primaryDevice, "Основное устройство") : "Устройство не привязано"}</h3>
                <p className="mt-1 text-sm text-slate-600">{primaryDevice ? requesterDeviceSystemLabel(primaryDevice) : "Привяжите компьютер, чтобы видеть его состояние в кабинете."}</p>
                <div className="mt-3">
                  <StatusBadge
                    label={requesterDeviceConnectionStatusLabel(primaryDevice)}
                    status={primaryDevice?.online === true ? "online" : primaryDevice?.online === false ? "offline" : "pending"}
                  />
                </div>
              </div>
            </div>
          </Card>
        </ContentSection>
      </div>
    </PageShell>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, ClipboardList, PlusCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, PageSkeleton, StatusBadge } from "../../components/ui-page";
import { REGISTRATION_LOGIN_KEY } from "../../features/auth/requester-registration";
import { approveRequesterConsent, denyRequesterConsent } from "../../features/requester/api";
import { RequesterConsentList } from "../../features/requester/consent-card";
import { requesterErrorMessage } from "../../features/requester/labels";
import {
  projectRequesterDashboard, requesterInvalidations, useRequesterBootstrapQuery,
  useRequesterConsentsQuery, useRequesterTicketsQuery,
} from "../../features/requester/queries";
import type { RequesterConsent } from "../../features/requester/types";
import { RequesterHomeReadiness } from "./home-readiness";
import "./home.css";

export function RequesterHomePage() {
  const [registeredLogin] = useState(() => {
    try { return sessionStorage.getItem(REGISTRATION_LOGIN_KEY); } catch { return null; }
  });
  const queryClient = useQueryClient();
  const bootstrapQuery = useRequesterBootstrapQuery();
  const ticketsQuery = useRequesterTicketsQuery();
  const consentsQuery = useRequesterConsentsQuery();
  const [consentNotice, setConsentNotice] = useState<string | null>(null);
  const registrationMatches = registeredLogin && registeredLogin === bootstrapQuery.data?.account_summary?.login;
  useEffect(() => {
    if (registrationMatches) {
      try { sessionStorage.removeItem(REGISTRATION_LOGIN_KEY); } catch { /* Optional notice. */ }
    }
  }, [registrationMatches]);

  const isLoading = bootstrapQuery.isLoading || ticketsQuery.isLoading || consentsQuery.isLoading;
  const blockingError = bootstrapQuery.error ?? ticketsQuery.error;
  if (isLoading) return <div className="requester-home"><PageSkeleton sections={3} title="Загружаем главную страницу кабинета" /></div>;
  if (blockingError) return <div className="requester-home"><ErrorState
    message={requesterErrorMessage(blockingError, "Не удалось загрузить главную страницу кабинета.")}
    onRetry={() => { void bootstrapQuery.refetch(); void ticketsQuery.refetch(); void consentsQuery.refetch(); }}
    title="Не удалось открыть кабинет"
  /></div>;

  const bootstrap = bootstrapQuery.data ?? null;
  const consents = consentsQuery.data ?? [];
  const pendingConsents = consents.filter((consent) => consent.status === "pending");
  const dashboard = projectRequesterDashboard(bootstrap, ticketsQuery.data ?? [], consents);
  const ticketStatuses = new Map((ticketsQuery.data?.length ? ticketsQuery.data : bootstrap?.recent_tickets ?? []).map((ticket) => [ticket.ticket_id, ticket.status]));

  async function decideConsent(consent: RequesterConsent, decision: "approved" | "denied") {
    setConsentNotice(null);
    try {
      if (decision === "approved") await approveRequesterConsent(consent.consent_id);
      else await denyRequesterConsent(consent.consent_id, "requester_denied");
      await requesterInvalidations.afterConsentDecision(queryClient, consent.ticket_id);
      await consentsQuery.refetch();
      setConsentNotice(decision === "approved" ? "Согласие подтверждено" : "Согласие отклонено");
    } catch (exc) {
      setConsentNotice(requesterErrorMessage(exc, "Не удалось сохранить решение", { domain: "consent" }));
    }
  }

  return (
    <div aria-labelledby="requester-home-title" className="requester-home">
      {registrationMatches ? <p role="status" className="rounded-panel border border-brand-200 bg-brand-50 p-4 text-sm text-brand-900">Регистрация завершена, профиль заполнен. Ваш логин: <strong>{registeredLogin}</strong>. Создать обращение можно кнопкой в кабинете.</p> : null}
      <header className="requester-home__heading">
        <h1 id="requester-home-title">Чем можем помочь?</h1>
        <p>Создайте обращение или проверьте ответ специалиста.</p>
      </header>

      <section aria-label="Основные действия" className="requester-home__actions">
        <div className="requester-home__create">
          <PlusCircle aria-hidden="true" className="requester-home__action-icon" />
          <div>
            <h2>Создать обращение</h2>
            <p>Сообщите о проблеме с компьютером, программой или оборудованием.</p>
            <Link className="requester-home__primary" to="/app/requester/new">Создать обращение<ArrowRight aria-hidden="true" /></Link>
          </div>
        </div>
        <div className="requester-home__browse">
          <ClipboardList aria-hidden="true" className="requester-home__action-icon" />
          <div>
            <h2>Мои обращения</h2>
            <p>Следите за решением и отвечайте специалистам.</p>
            <Link className="requester-home__secondary" to="/app/requester/tickets">Открыть список<ArrowRight aria-hidden="true" /></Link>
          </div>
        </div>
      </section>

      {consentNotice ? <p aria-live="polite" role="status" className="rounded-panel bg-brand-50 p-3 text-sm">{consentNotice}</p> : null}
      {consentsQuery.error ? <ErrorState title="Не удалось проверить запросы согласия" message="Повторите проверку, чтобы не пропустить запрос специалиста." onRetry={() => void consentsQuery.refetch()} /> : null}
      <RequesterConsentList consents={pendingConsents} onDecision={decideConsent} />

      <section aria-labelledby="requester-recent-title" className="requester-home__recent">
        <div className="requester-home__section-heading">
          <h2 id="requester-recent-title">Последние обращения</h2>
          <Link className="requester-home__text-link" to="/app/requester/tickets">Все обращения<ArrowRight aria-hidden="true" /></Link>
        </div>
        {dashboard.recentTickets.length ? <ul className="requester-home__tickets">
          {dashboard.recentTickets.slice(0, 4).map((ticket) => {
            const body = <>
              <div className="min-w-0"><h3 className="break-words">{ticket.title}</h3><p>{ticket.displayCode}</p></div>
              <StatusBadge className="text-sm" label={ticket.statusLabel} status={ticketStatuses.get(ticket.ticketId)} tone={ticketStatuses.get(ticket.ticketId) === "waiting_on_user" ? "warning" : undefined} />
              <time className="requester-home__date">{ticket.createdAtLabel}</time>
              {ticket.ticketRouteParam ? <ChevronRight aria-hidden="true" className="requester-home__chevron" /> : null}
            </>;
            return <li key={ticket.ticketId}>{ticket.ticketRouteParam ?
              <Link className="requester-home__ticket" to={`/app/requester/tickets/${encodeURIComponent(ticket.ticketRouteParam)}`}>{body}</Link>
              : <div className="requester-home__ticket">{body}</div>}</li>;
          })}
        </ul> : <EmptyState title="Обращений пока нет" description="Если нужна помощь, нажмите «Создать обращение» выше. Здесь появятся ответы и статусы." />}
      </section>

      <RequesterHomeReadiness bootstrap={bootstrap} profileComplete={dashboard.readiness.profileComplete} />
    </div>
  );
}

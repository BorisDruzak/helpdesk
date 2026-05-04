import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { fetchSupportTicketPassport } from "../../features/queues/api";
import { PASSPORT_SECTION_LABELS } from "./detail-page";

function formatPrintDate(value: string | null | undefined) {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function TicketPassportPrintPage() {
  const navigate = useNavigate();
  const { ticketId } = useParams();

  const passportQuery = useQuery({
    queryKey: ["ticket-passport-print", ticketId],
    queryFn: () => fetchSupportTicketPassport(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });

  if (!ticketId) {
    return <Navigate replace to="/app/tickets" />;
  }

  const payload = passportQuery.data;
  const passport = payload?.passport ?? null;

  return (
    <section className="mx-auto max-w-5xl space-y-6 px-2 py-2 print:max-w-none print:px-0 print:py-0">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <Button leadingIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(`/app/tickets/${ticketId}`)} variant="outline">
          Назад к тикету
        </Button>
        <Button leadingIcon={<Printer className="h-4 w-4" />} onClick={() => window.print()}>
          Печать / PDF
        </Button>
      </div>

      <article className="rounded-[1rem] border border-border bg-white px-8 py-8 shadow-soft print:border-0 print:px-0 print:py-0 print:shadow-none">
        <header className="border-b border-slate-200 pb-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-700">
                Официальная карточка решения
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Паспорт решения</h1>
              <p className="mt-2 text-sm text-slate-500">Тикет: {ticketId}</p>
            </div>
            {passport ? <Badge tone="brand">Версия {passport.version}</Badge> : null}
          </div>
          {passport ? (
            <p className="mt-4 text-sm text-slate-500">
              Собран: {formatPrintDate(passport.generated_at)} • источник: {passport.summary_source}
            </p>
          ) : null}
        </header>

        {passportQuery.isLoading ? (
          <div className="py-16 text-center text-sm text-slate-500">Загружаем паспорт решения...</div>
        ) : null}

        {passportQuery.isError ? (
          <div className="mt-6 rounded-[1rem] border border-rose-200 bg-rose-50 px-5 py-5 text-sm text-rose-700">
            {passportQuery.error instanceof Error ? passportQuery.error.message : "Не удалось загрузить паспорт."}
          </div>
        ) : null}

        {!passportQuery.isLoading && !passportQuery.isError && !passport ? (
          <div className="py-16 text-center text-sm text-slate-500">Паспорт решения ещё не собран.</div>
        ) : null}

        {passport ? (
          <div className="mt-8 space-y-6">
            {PASSPORT_SECTION_LABELS.map(([key, label]) => (
              <section key={key} className="break-inside-avoid rounded-[0.75rem] border border-slate-200 px-5 py-5 print:border-slate-300">
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-800">
                  {passport.sections[key] || "Нет данных"}
                </p>
              </section>
            ))}

            <section className="break-inside-avoid rounded-[0.75rem] border border-slate-200 px-5 py-5 print:border-slate-300">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">Приложение доказательств</h2>
              {payload?.evidence.length ? (
                <div className="mt-4 space-y-3">
                  {payload.evidence.map((item) => (
                    <div className="rounded-[0.6rem] border border-slate-200 px-4 py-3" key={item.id}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">{item.title}</p>
                          {item.summary ? <p className="mt-1 text-sm text-slate-700">{item.summary}</p> : null}
                        </div>
                        <Badge tone={item.verification_status === "accepted" ? "success" : "neutral"}>
                          {item.verification_status || "unverified"}
                        </Badge>
                      </div>
                      <dl className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-2">
                        <div>
                          <dt className="font-semibold text-slate-800">Тип</dt>
                          <dd>{item.evidence_type || "Не указан"}</dd>
                        </div>
                        <div>
                          <dt className="font-semibold text-slate-800">Источник</dt>
                          <dd>{item.source_ref || "Не указан"}</dd>
                        </div>
                        <div>
                          <dt className="font-semibold text-slate-800">Факт</dt>
                          <dd>{item.required_fact || "Не привязан"}</dd>
                        </div>
                        <div>
                          <dt className="font-semibold text-slate-800">Экспорт</dt>
                          <dd>{item.export_visibility || item.visibility || "Не указан"}</dd>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-600">Доказательства не приложены к паспорту.</p>
              )}
            </section>

            <footer className="grid gap-4 border-t border-slate-200 pt-6 text-sm text-slate-600 md:grid-cols-3">
              <div>
                <p className="font-semibold text-slate-950">Доказательства</p>
                <p className="mt-1">{payload?.evidence.length ?? 0}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-950">Действия</p>
                <p className="mt-1">{payload?.actions.length ?? 0}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-950">Согласования</p>
                <p className="mt-1">{payload?.approvals.length ?? 0}</p>
              </div>
            </footer>
          </div>
        ) : null}
      </article>
    </section>
  );
}

import { useId, useState } from "react";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";

export function TicketRequestContext({ detail, serviceContext }: { detail: SupportTicketDetailPayload; serviceContext?: SupportWorkspaceContext["classification"] }) {
  const raw = detail.ticket;
  const resultId = useId();
  const [expandedResultTicket, setExpandedResultTicket] = useState<string | null>(null);
  const resultExpanded = expandedResultTicket === raw.ticket_id;
  const rows = detail.request_form?.rows ?? [];
  const comparable = (value: string) => value.replace(/[\s?:]+/g, "").trim();
  const descriptionIsAnswers = rows.length > 0 && comparable(raw.description ?? "") === comparable(rows.map((row) => `${row.label}: ${row.value}`).join(" "));
  return <section className="simple-panel simple-ticket-context" aria-label="Контекст обращения">
        <h3>Контекст</h3>
        {serviceContext ? <div className="simple-ticket-context__service"><p className="simple-eyebrow">Услуга обращения</p><h4>{serviceContext.service}</h4>
          <dl className="simple-facts">{[
            ["Тип обращения", serviceContext.ticketType], ["Категория", serviceContext.category], ["Владелец услуги", serviceContext.serviceOwner],
            ["Источник услуги", serviceContext.serviceSourceLabel], ["Группа обработки", raw.queue.name ?? raw.queue.code], ["Похожие тикеты", String(serviceContext.similarTicketsCount)],
          ].filter(([, value]) => value && !/^не указан[ао]?$/i.test(value)).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        </div> : null}
        {!descriptionIsAnswers ? <div className="simple-ticket-context__description"><h4>Описание проблемы</h4><p>{raw.description || "Описание не указано"}</p></div> : null}
        {rows.length ? <dl className="simple-facts">{rows.map((row) => <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl> : null}
        {raw.requester_resolution_summary ? <div className="simple-ticket-context__result"><h4>Результат решения</h4><p id={resultId} data-expanded={resultExpanded} tabIndex={resultExpanded ? 0 : undefined}>{raw.requester_resolution_summary}</p>
          <button className="simple-link simple-result-toggle" type="button" aria-controls={resultId} aria-expanded={resultExpanded} onClick={() => setExpandedResultTicket(resultExpanded ? null : raw.ticket_id)}>{resultExpanded ? "Свернуть результат" : "Показать результат полностью"}</button>
        </div> : null}
      </section>;
}

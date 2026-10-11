import { useMemo, useState } from "react";
import { InlineAlert } from "../../features/requester/ui/form-controls";
import { useRequesterTicketsQuery } from "../../features/requester/queries";
import { requesterErrorMessage } from "../../features/requester/labels";
import { TicketsListPanel } from "./tickets-panels";
import { ticketMatchesFilter, ticketMatchesSearch, type TicketFilter } from "./tickets-workflow";

export function RequesterTicketsPage() {
  const ticketsQuery = useRequesterTicketsQuery();
  const [filter, setFilter] = useState<TicketFilter>("open");
  const [search, setSearch] = useState("");
  const filteredTickets = useMemo(() => (ticketsQuery.data ?? [])
    .filter(ticket => ticketMatchesFilter(ticket, filter) && ticketMatchesSearch(ticket, search)),
    [ticketsQuery.data, filter, search]);
  return (
    <div className="mx-auto max-w-6xl px-2 py-4">
      {ticketsQuery.isError ? <InlineAlert role="alert">{requesterErrorMessage(ticketsQuery.error, "Не удалось загрузить обращения")}</InlineAlert> : null}
      <TicketsListPanel filter={filter} filteredTickets={filteredTickets} isLoading={ticketsQuery.isLoading}
        search={search} selectedTicketId={undefined} setFilter={setFilter} setSearch={setSearch} />
    </div>
  );
}

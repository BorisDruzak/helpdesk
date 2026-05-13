import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { SearchField } from "../../components/ui/search-field";
import { listTicketCapabilityReadiness } from "./api";
import type { CapabilityDescriptor } from "./types";
import { label, readinessTone, targetTone } from "./labels";

type ReadinessLabPanelProps = {
  globalCapabilities: CapabilityDescriptor[];
  onOpenCapability: (capability: CapabilityDescriptor) => void;
};

export function ReadinessLabPanel({ globalCapabilities, onOpenCapability }: ReadinessLabPanelProps) {
  const [ticketId, setTicketId] = useState("");
  const [query, setQuery] = useState("");
  const [submittedTicketId, setSubmittedTicketId] = useState("");

  const readinessQuery = useQuery({
    enabled: Boolean(submittedTicketId.trim()),
    queryKey: ["admin-capability-readiness", submittedTicketId],
    queryFn: () => listTicketCapabilityReadiness(submittedTicketId.trim()),
    retry: false,
  });

  const capabilities = readinessQuery.data ?? globalCapabilities;
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return capabilities;
    }
    return capabilities.filter((capability) =>
      [
        capability.id,
        capability.title,
        capability.provider_id ?? "",
        capability.execution_target,
        capability.readiness ?? "",
        capability.reason_code ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [capabilities, query]);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Readiness Lab</CardTitle>
          <CardDescription>
            Выберите ticket id, чтобы увидеть ticket-scoped готовность. Для agent capabilities нужен тикет или устройство.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-[minmax(14rem,0.7fr)_minmax(14rem,1fr)_auto]">
          <Input
            onChange={(event) => setTicketId(event.target.value)}
            placeholder="ticket id"
            value={ticketId}
          />
          <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Фильтр capability/readiness" value={query} />
          <Button
            disabled={!ticketId.trim() || readinessQuery.isFetching}
            leadingIcon={<RefreshCw className="h-4 w-4" />}
            onClick={() => setSubmittedTicketId(ticketId)}
          >
            {readinessQuery.isFetching ? "Проверяем..." : "Проверить"}
          </Button>
        </CardContent>
      </Card>

      {!submittedTicketId ? (
        <p className="rounded-[0.9rem] border border-dashed border-border bg-white px-4 py-3 text-sm text-slate-500">
          Сейчас показана generic readiness из global catalog. Для ticket-scoped readiness укажите ticket id.
        </p>
      ) : null}
      {readinessQuery.isError ? (
        <p className="rounded-[0.9rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {readinessQuery.error instanceof Error ? readinessQuery.error.message : "Не удалось загрузить readiness."}
        </p>
      ) : null}

      <Card>
        <CardContent className="overflow-x-auto px-0 pb-0">
          <table className="min-w-full divide-y divide-border text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
              <tr>
                <th className="px-5 py-3">Capability</th>
                <th className="px-5 py-3">Readiness</th>
                <th className="px-5 py-3">Reason</th>
                <th className="px-5 py-3">Actions</th>
                <th className="px-5 py-3">Execution target</th>
                <th className="px-5 py-3">Provider</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-white">
              {filtered.map((capability) => (
                <tr key={capability.id} className="hover:bg-brand-50/30">
                  <td className="px-5 py-4">
                    <button className="text-left" onClick={() => onOpenCapability(capability)} type="button">
                      <span className="block font-semibold text-slate-950">{capability.title}</span>
                      <span className="mt-1 block break-all text-xs text-slate-500">{capability.id}</span>
                    </button>
                  </td>
                  <td className="px-5 py-4">
                    <Badge tone={readinessTone(capability.readiness)}>{capability.readiness ?? "unknown"}</Badge>
                  </td>
                  <td className="max-w-md px-5 py-4 text-slate-600">
                    {capability.reason ?? capability.reason_code ?? "Нет блокирующей причины."}
                  </td>
                  <td className="px-5 py-4 text-slate-600">{capability.actions?.join(", ") || "run"}</td>
                  <td className="px-5 py-4">
                    <Badge tone={targetTone(capability.execution_target)}>{label(capability.execution_target)}</Badge>
                  </td>
                  <td className="px-5 py-4 text-slate-600">{capability.provider_id ?? "unknown"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length ? (
            <div className="px-6 py-10 text-center text-sm text-slate-500">Под выбранный фильтр readiness строк нет.</div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

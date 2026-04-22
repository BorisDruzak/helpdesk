import { AlertTriangle, TimerReset } from "lucide-react";
import { useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { observerTraces } from "../../mocks/helpdesk-data";

export function AdminObserverPage() {
  const [selectedTraceId, setSelectedTraceId] = useState(observerTraces[0].id);
  const selectedTrace = observerTraces.find((trace) => trace.id === selectedTraceId) ?? observerTraces[0];

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<TimerReset className="h-4 w-4" />} size="sm" variant="outline">
              24 часа
            </Button>
            <Button size="sm">Открыть полный срез</Button>
          </>
        }
        description="Observer переведен в тот же SaaS-формат: чистые KPI, компактный список трасс и удобный detail panel справа."
        eyebrow="Observability"
        title="Observer"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        {[
          { label: "Recent traces", value: "34" },
          { label: "Hot traces", value: "6" },
          { label: "Error signatures", value: "3" },
          { label: "Dangerous flows", value: "1" }
        ].map((item) => (
          <Card key={item.label}>
            <CardContent className="pt-6">
              <p className="text-sm text-slate-500">{item.label}</p>
              <p className="mt-2 text-3xl font-semibold text-slate-950">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Горячие трассы</CardTitle>
            <CardDescription>Плотный список для быстрого выбора без перегруза деталями.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {observerTraces.map((trace) => (
              <button
                key={trace.id}
                className={`w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors ${
                  trace.id === selectedTraceId
                    ? "border-brand-200 bg-brand-50"
                    : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                }`}
                onClick={() => setSelectedTraceId(trace.id)}
                type="button"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-slate-950">{trace.title}</p>
                  <Badge tone={trace.statusTone}>{trace.status}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-500">{trace.summary}</p>
                <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-400">
                  <span>{trace.device}</span>
                  <span>{trace.duration}</span>
                  <span>{trace.timestamp}</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Детальный разбор</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{selectedTrace.id}</p>
                <p className="mt-2 text-xl font-semibold text-slate-950">{selectedTrace.title}</p>
                <p className="mt-2 text-sm text-slate-500">{selectedTrace.summary}</p>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Устройство</span>
                  <span className="font-medium text-slate-900">{selectedTrace.device}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Длительность</span>
                  <span className="font-medium text-slate-900">{selectedTrace.duration}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Последнее событие</span>
                  <span className="font-medium text-slate-900">{selectedTrace.timestamp}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Горячие сигнатуры</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "Launcher signature mismatch",
                "Rollback policy skipped",
                "Observer backlog increased"
              ].map((item) => (
                <div key={item} className="flex items-start gap-3 rounded-[1.1rem] bg-rose-50 px-4 py-4 text-sm text-rose-700">
                  <AlertTriangle className="mt-0.5 h-4 w-4" />
                  <span>{item}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}

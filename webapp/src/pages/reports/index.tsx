import { Filter, TrendingUp } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { reportChannels, reportMetrics, reportTrend } from "../../mocks/helpdesk-data";

export function ReportsPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button size="sm" variant="outline">
              12 мая - 18 мая 2024
            </Button>
            <Button leadingIcon={<Filter className="h-4 w-4" />} size="sm" variant="outline">
              Фильтры
            </Button>
          </>
        }
        description="Операционный отчет в том же светлом SaaS-языке: метрики, динамика тикетов, SLA и нагрузка по каналам."
        eyebrow="Analytics"
        title="Отчеты"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        {reportMetrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="pt-6">
              <p className="text-sm text-slate-500">{metric.label}</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{metric.value}</p>
              <Badge className="mt-4" tone={metric.tone}>
                {metric.delta}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Динамика тикетов</CardTitle>
            <CardDescription>Легкая визуализация без тяжелой графической библиотеки.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid min-h-[280px] grid-cols-6 items-end gap-4">
              {reportTrend.map((point) => (
                <div key={point.day} className="flex h-full flex-col items-center justify-end gap-3">
                  <div className="flex h-full w-full items-end justify-center gap-2 rounded-[1.1rem] bg-surface-subtle px-3 py-4">
                    <div className="w-3 rounded-full bg-blue-500" style={{ height: `${point.requests * 7}px` }} />
                    <div className="w-3 rounded-full bg-emerald-500" style={{ height: `${point.waiting * 7}px` }} />
                    <div className="w-3 rounded-full bg-amber-400" style={{ height: `${point.resolved * 7}px` }} />
                  </div>
                  <p className="text-xs font-medium text-slate-500">{point.day}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Тикеты по каналам</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="mx-auto h-44 w-44 rounded-full bg-[conic-gradient(#2563eb_0deg_223deg,#16a34a_223deg_309deg,#f59e0b_309deg_345deg,#0ea5e9_345deg_360deg)] p-5">
                <div className="flex h-full items-center justify-center rounded-full bg-white text-center">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">SLA</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-950">92%</p>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {reportChannels.map((channel) => (
                  <div key={channel.label} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-2.5 w-2.5 rounded-full ${
                          channel.tone === "brand"
                            ? "bg-blue-500"
                            : channel.tone === "success"
                              ? "bg-emerald-500"
                              : channel.tone === "warning"
                                ? "bg-amber-400"
                                : "bg-sky-500"
                        }`}
                      />
                      <span className="text-slate-600">{channel.label}</span>
                    </div>
                    <span className="font-semibold text-slate-950">{channel.value}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Top категории</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { label: "Техническая поддержка", value: "64 (50%)" },
                { label: "Доступ и аккаунты", value: "32 (25%)" },
                { label: "Интеграции", value: "18 (14%)" }
              ].map((item, index) => (
                <div key={item.label}>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="text-slate-600">{item.label}</span>
                    <span className="font-medium text-slate-900">{item.value}</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-subtle">
                    <div
                      className={`h-2 rounded-full ${index === 0 ? "bg-brand-500" : index === 1 ? "bg-blue-500" : "bg-emerald-500"}`}
                      style={{ width: `${[64, 32, 18][index]}%` }}
                    />
                  </div>
                </div>
              ))}
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <div className="flex items-center gap-2 text-brand-700">
                  <TrendingUp className="h-4 w-4" />
                  <span className="text-sm font-semibold">SLA за период</span>
                </div>
                <div className="mt-4 h-2 rounded-full bg-white">
                  <div className="h-2 w-[92%] rounded-full bg-brand-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}

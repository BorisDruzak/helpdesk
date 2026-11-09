import {SettingsLink} from "./settings-link";


import {Badge} from "../../components/ui/badge";

import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import type {ServiceSettingsModel} from './use-service-settings';
export function OverviewSettingsSection({model}:{model:ServiceSettingsModel}){const {payload}=model; if(!payload)return null;
return (
            <div className="space-y-6"><div className="rounded-panel border border-border bg-white p-5 space-y-3"><h2 className="font-semibold text-lg">Режим работы службы</h2><p>{payload.ticket_settings.operational_flags.queue_mode === "unified" ? "Единая очередь: все активные операторы работают с общим списком." : "Разделённые очереди: работа распределяется по группам поддержки."}</p><p className="text-sm text-slate-600">Правила конкретной услуги задаются в Студии обращений. Здесь находятся общие политики службы.</p><div className="flex flex-wrap gap-4"><SettingsLink className="underline text-brand-800" href="/app/admin/request-template-studio">Студия обращений</SettingsLink><SettingsLink className="underline text-brand-800" href="/app/admin/users">Пользователи и доступ</SettingsLink></div></div>
              <div className="grid gap-4 xl:grid-cols-4">
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Очереди</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.queues_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Активных: {payload.overview.active_queues_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Маршрутизация</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.routing_rules_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Активных правил: {payload.overview.active_routing_rules_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Сроки и календари</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.sla_policies_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Календарей: {payload.overview.calendars_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Коды и аудит</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.resolution_codes_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Последних записей аудита: {payload.overview.audit_records_count}</p>
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
                <Card>
                  <CardHeader>
                    <CardTitle>Рабочие очереди</CardTitle>
                    <CardDescription>Текущий состав очередей и число открытых обращений.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-2">
                    {payload.queues.slice(0, 4).map((queue) => (
                      <div key={queue.id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{queue.name}</p>
                          <Badge tone={queue.is_active ? "success" : "neutral"}>{queue.code}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">
                          Открыто тикетов: {queue.open_tickets_count} • участников: {queue.members.length}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Права на запись</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="text-sm text-slate-500">Роль текущего сеанса</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-950">{payload.capabilities.actor_role}</p>
                    </div>
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="text-sm text-slate-500">Доступ на изменение</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-950">
                        {payload.capabilities.can_write ? "Разрешён" : "Только чтение"}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          );
}

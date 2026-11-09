
import {Badge} from "../../components/ui/badge";

import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import type {ServiceSettingsModel} from './use-service-settings';
export function ProcessReference({model}:{model:ServiceSettingsModel}){const {payload}=model;if(!model.payload)return null;if(!payload)return null;
return (<details className="rounded-panel border border-border bg-white p-4"><summary className="cursor-pointer font-medium">Справка о процессе и приоритетах</summary><Card>
                <CardHeader>
                  <CardTitle>Схема service desk</CardTitle>
                  <CardDescription>
                    Шаблон обращения → форма → процесс → приоритет → сроки → очередь → паспорт
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {payload.ticket_settings.process_schema.map((item) => (
                      <div key={item.key} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-950">{item.label}</p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{item.meaning}</p>
                          </div>
                          <Badge tone={item.status === "active" ? "success" : "warning"}>{item.status}</Badge>
                        </div>
                        <p className="mt-3 text-xs text-slate-500">{item.source}</p>
                        <code className="mt-2 block text-xs text-slate-400">{item.ui_surface}</code>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)]">
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">Модель приоритета</p>
                          <p className="mt-1 text-sm text-slate-500">
                            Пользователь не выбирает P0/P1/P2/P3 напрямую
                          </p>
                        </div>
                        <Badge tone={payload.ticket_settings.priority_model.direct_user_priority_choice ? "warning" : "success"}>
                          {payload.ticket_settings.priority_model.direct_user_priority_choice ? "Ручной выбор" : "Факты → приоритет"}
                        </Badge>
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-3">
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Влияние</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.impact_levels.join(", ")}</p>
                        </div>
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Срочность</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.urgency_levels.join(", ")}</p>
                        </div>
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Важность</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.importance_sources.join(", ")}</p>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {payload.ticket_settings.priority_model.modifiers.map((modifier) => (
                          <Badge key={modifier} tone="info">{modifier}</Badge>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="font-semibold text-slate-950">Линии поддержки</p>
                      <div className="mt-3 space-y-3">
                        {payload.ticket_settings.support_lines.map((line) => (
                          <div key={line.code} className="rounded-[0.9rem] bg-white px-3 py-3">
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-semibold text-slate-900">{line.label}</p>
                              <Badge tone={line.status === "active" ? "success" : "warning"}>{line.status}</Badge>
                            </div>
                            <p className="mt-2 text-sm text-slate-600">{line.competence_depth}</p>
                            <code className="mt-2 block text-xs text-slate-400">{line.routing_role}</code>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card></details>);}

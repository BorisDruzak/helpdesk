
import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import type {ServiceSettingsModel} from './use-service-settings';
export function ProcessLinks({model}:{model:ServiceSettingsModel}){const {setActiveTab,payload}=model;if(!model.payload)return null;if(!payload)return null;
return (<details className="rounded-panel border border-border bg-white p-4"><summary className="cursor-pointer font-medium">Связанные настройки</summary><div className="grid gap-6 xl:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle>Пользовательские статусы</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {payload.ticket_settings.requester_statuses.map((item) => (
                      <div key={item.value} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{item.label}</p>
                          <Badge tone="neutral">{item.internal_statuses.length}</Badge>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{item.internal_statuses.join(", ") || "Нет статусов"}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Следующий ответственный</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {payload.ticket_settings.next_action_owners.map((item) => (
                      <div key={item.value} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{item.label}</p>
                          <code className="text-xs text-slate-400">{item.value}</code>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{item.internal_statuses.join(", ") || "Нет статусов"}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Детальные настройки</CardTitle>
                    <CardDescription>Редактируемые части тикетной системы уже вынесены в соседние вкладки.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3">
                    <Button onClick={() => setActiveTab("queues")} variant="outline">Очереди и внутренние сроки</Button>
                    <Button onClick={() => setActiveTab("routing")} variant="outline">Маршрутизация</Button>
                    <Button onClick={() => setActiveTab("sla")} variant="outline">Сроки и матрица приоритетов</Button>
                    <Button onClick={() => setActiveTab("resolution")} variant="outline">Коды решения</Button>
                  </CardContent>
                </Card>
              </div></details>);}

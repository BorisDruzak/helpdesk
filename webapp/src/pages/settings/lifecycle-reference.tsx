
import {Badge} from "../../components/ui/badge";

import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import {getTicketStageLabel, getTicketStageTone} from "../../features/tickets/status-presentation";

import {formatBooleanFlag} from './settings-workflow-model';

import type {ServiceSettingsModel} from './use-service-settings';
export function LifecycleReference({model}:{model:ServiceSettingsModel}){const {payload}=model;if(!model.payload)return null;if(!payload)return null;
return (<details className="rounded-panel border border-border bg-white p-4"><summary className="cursor-pointer font-medium">Статусы и технические параметры</summary><div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
                <Card>
                  <CardHeader>
                    <CardTitle>Жизненный цикл тикета</CardTitle>
                    <CardDescription>
                      Канонические внутренние статусы, пользовательское отображение и ответственный за следующий шаг.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[760px] text-left text-sm">
                        <thead className="text-xs uppercase tracking-[0.18em] text-slate-400">
                          <tr>
                            <th className="px-3 py-3">Внутренний статус</th>
                            <th className="px-3 py-3">Для пользователя</th>
                            <th className="px-3 py-3">Чей ход</th>
                            <th className="px-3 py-3">Этап</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {payload.ticket_settings.internal_statuses.map((status) => (
                            <tr key={status.value}>
                              <td className="px-3 py-4">
                                <div className="font-semibold text-slate-950">{status.label}</div>
                                <code className="mt-1 block text-xs text-slate-400">{status.value}</code>
                              </td>
                              <td className="px-3 py-4">
                                <div className="font-medium text-slate-800">{status.requester_label}</div>
                                <code className="mt-1 block text-xs text-slate-400">{status.requester_status}</code>
                              </td>
                              <td className="px-3 py-4">
                                <code className="text-xs text-slate-600">{status.next_action_owner}</code>
                              </td>
                              <td className="px-3 py-4">
                                <div className="flex flex-wrap gap-2">
                                  <Badge tone={getTicketStageTone(status.stage)}>{getTicketStageLabel(status.stage)}</Badge>
                                  {status.waits ? <Badge tone="warning">Wait ledger</Badge> : null}
                                  {status.terminal ? <Badge tone="neutral">Terminal</Badge> : null}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Правила закрытия</CardTitle>
                      <CardDescription>То, что влияет на подтверждаемость решения.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Подтверждение пользователя</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {formatBooleanFlag(payload.ticket_settings.governance.requester_confirmation_required)}
                        </p>
                      </div>
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Автозакрытие после решения</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {payload.ticket_settings.governance.auto_close_hours} ч
                        </p>
                      </div>
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Root cause обязателен для</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {payload.ticket_settings.governance.require_root_cause_priorities.map((priority) => (
                            <Badge key={priority} tone="warning">{priority}</Badge>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Operational flags</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {[
                        ["Admin config API", payload.ticket_settings.operational_flags.admin_config_api_enabled],
                        ["Admin config write", payload.ticket_settings.operational_flags.admin_config_write_enabled],
                        ["Auditor role", payload.ticket_settings.operational_flags.auditor_role_enabled],
                        ["Retention", payload.ticket_settings.operational_flags.retention_enabled],
                        ["Retention dry-run", payload.ticket_settings.operational_flags.retention_dry_run],
                      ].map(([label, value]) => (
                        <div key={String(label)} className="flex items-center justify-between rounded-[1rem] bg-surface-subtle px-4 py-3">
                          <span className="text-slate-500">{label}</span>
                          <Badge tone={value ? "success" : "neutral"}>{formatBooleanFlag(Boolean(value))}</Badge>
                        </div>
                      ))}
                      <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                        <p className="text-slate-500">Take-self queue mode</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {payload.ticket_settings.operational_flags.take_queue_mode}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          common: {payload.ticket_settings.operational_flags.take_queue_common_code} • test:{" "}
                          {payload.ticket_settings.operational_flags.take_queue_test_code}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div></details>);}

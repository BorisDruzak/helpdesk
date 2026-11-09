import {CheckCircle2, GitBranch, ShieldCheck, Workflow} from "lucide-react";

import {Card, CardContent} from "../../components/ui/card";

import {formatBooleanFlag} from './settings-workflow-model';

import type {ServiceSettingsModel} from './use-service-settings';
export function ProcessSummary({model}:{model:ServiceSettingsModel}){const {payload}=model;if(!model.payload)return null;if(!payload)return null;
return (<div className="grid gap-4 xl:grid-cols-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <Workflow className="h-4 w-4 text-brand-700" />
                      Статусы
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {payload.ticket_settings.internal_statuses.length}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Пользовательских: {payload.ticket_settings.requester_statuses.length}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <ShieldCheck className="h-4 w-4 text-brand-700" />
                      Governance
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {payload.ticket_settings.governance.resolution_validation_mode}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      FSM: {payload.ticket_settings.governance.fsm_mode}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <CheckCircle2 className="h-4 w-4 text-brand-700" />
                      Паспорт решения
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {formatBooleanFlag(payload.ticket_settings.governance.passport_enabled)}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Evidence gate: {formatBooleanFlag(payload.ticket_settings.governance.evidence_gate_enabled)}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <GitBranch className="h-4 w-4 text-brand-700" />
                      Сроки ответа и очередей
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {formatBooleanFlag(payload.ticket_settings.operational_flags.ola_enabled)}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Рабочий календарь для сроков: {formatBooleanFlag(payload.ticket_settings.operational_flags.sla_calendar_enabled)}
                    </p>
                  </CardContent>
                </Card>
              </div>);}

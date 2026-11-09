import {DurationTargetsEditor} from "./duration-targets-editor";
import {PriorityMatrixEditor} from "./priority-matrix-editor";
import {Plus} from "lucide-react";

import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardHeader, CardTitle} from "../../components/ui/card";
import {Input} from "../../components/ui/input";

import {Select} from "../../components/ui/select";

import {type PolicyDraft} from './settings-types';
import {buildPolicyDraft, buildSlaTargetsDraft, buildPriorityMatrixDraft} from './settings-form-model';

import {SettingsField, PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function SlaSettingsSection({model}:{model:ServiceSettingsModel}){const {requestChange,setDirty,payload,canManageRouting,routingDeniedReason,setSelectedPolicyId,selectedPolicy,policyDraft,setPolicyDraft,slaTargetsDraft,setSlaTargetsDraft,priorityMatrixDraft,setPriorityMatrixDraft,policyMutation,slaTargetsMutation,priorityMatrixMutation}=model; if(!payload)return null;
return (
            <div className="settings-object-editor">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Политики сроков</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PermissionNotice text={routingDeniedReason} />
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => requestChange(() => {
                      setSelectedPolicyId(-1);
                      setDirty(true);
                      setPolicyDraft(buildPolicyDraft(null));
                      setSlaTargetsDraft(buildSlaTargetsDraft(null));
                      setPriorityMatrixDraft(buildPriorityMatrixDraft(null));
                    })}
                    variant="secondary"
                  >
                    Новая политика
                  </Button>
                  {payload.sla_policies.map((policy) => (
                    <button
                      key={policy.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedPolicy?.id === policy.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => requestChange(() => setSelectedPolicyId(policy.id))}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{policy.name}</p>
                        {policy.is_default ? <Badge tone="success">Default</Badge> : null}
                      </div>
                      <p className="mt-2 text-xs text-current/70">
                        {policy.timezone} • открытых тикетов: {policy.open_tickets_count}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <PermissionNotice text={routingDeniedReason} />
                <Card>
                  <CardHeader>
                    <CardTitle>{selectedPolicy ? selectedPolicy.name : "Новая политика сроков"}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <SettingsField label="Название">
                        <Input data-settings-draft="policy"
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, name: event.target.value }))}
                          value={policyDraft.name}
                        />
                      </SettingsField>
                      <SettingsField label="Часовой пояс">
                        <Input data-settings-draft="policy"
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, timezone: event.target.value }))}
                          value={policyDraft.timezone}
                        />
                      </SettingsField>
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                      <SettingsField label="Календарь">
                        <Select data-settings-draft="policy"
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, calendar_id: event.target.value }))}
                          value={policyDraft.calendar_id}
                        >
                          <option value="">Без календаря</option>
                          {payload.calendars.map((calendar) => (
                            <option key={calendar.id} value={calendar.id}>
                              {calendar.name}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input data-settings-draft="policy"
                          checked={policyDraft.is_default}
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, is_default: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Политика по умолчанию</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input data-settings-draft="policy"
                          checked={policyDraft.is_active}
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, is_active: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Политика активна</span>
                      </label>
                    </div>
                    <SettingsField label="Режим рабочих часов">
                      <Select data-settings-draft="policy"
                        onChange={(event) =>
                          setPolicyDraft((current) => ({
                            ...current,
                            business_hours_mode: event.target.value as PolicyDraft["business_hours_mode"],
                          }))
                        }
                        value={policyDraft.business_hours_mode}
                      >
                        <option value="calendar">По выбранному календарю</option>
                        <option value="always_on">24×7 без календаря</option>
                      </Select>
                    </SettingsField>
                    <Button disabled={!canManageRouting || policyMutation.isPending} onClick={() => policyMutation.mutate()} className="w-full">
                      Сохранить политику сроков
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-6 2xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Сроки ответа и решения</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <DurationTargetsEditor kind="sla" disabled={!canManageRouting} rows={slaTargetsDraft.map(row=>({priority:row.priority,first:row.first_response_min,second:row.resolution_min}))} onFirst={(priority,value)=>setSlaTargetsDraft(rows=>rows.map(row=>row.priority===priority?{...row,first_response_min:value}:row))} onSecond={(priority,value)=>setSlaTargetsDraft(rows=>rows.map(row=>row.priority===priority?{...row,resolution_min:value}:row))}/>
                      <Button disabled={!canManageRouting || slaTargetsMutation.isPending || !selectedPolicy} onClick={() => slaTargetsMutation.mutate()} className="w-full">
                        Сохранить сроки
                      </Button>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Матрица влияния и срочности</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <PriorityMatrixEditor rows={priorityMatrixDraft} disabled={!canManageRouting} onChange={(impact,urgency,priority)=>setPriorityMatrixDraft(rows=>rows.map(row=>row.impact===impact&&row.urgency===urgency?{...row,priority}:row))}/>
                      <Button disabled={!canManageRouting || priorityMatrixMutation.isPending || !selectedPolicy} onClick={() => priorityMatrixMutation.mutate()} className="w-full">
                        Сохранить матрицу
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          );
}

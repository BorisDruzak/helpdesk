import {Plus} from "lucide-react";

import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";
import {Input} from "../../components/ui/input";

import {Select} from "../../components/ui/select";

import {prettyJson, buildRoutingDraft, buildRoutingConditionBuilder, buildRoutingConditionJson} from './settings-form-model';

import {SettingsField, PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function RoutingSettingsSection({model}:{model:ServiceSettingsModel}){const {requestChange,payload,canManageRouting,routingDeniedReason,setSelectedRuleId,selectedRule,routingDraft,setRoutingDraft,routingConditionBuilder,setRoutingConditionBuilder,routingMutation}=model; if(!payload)return null;
return (
            <div className="settings-object-editor">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Правила маршрутизации</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Button
                      disabled={!canManageRouting}
                      leadingIcon={<Plus className="h-4 w-4" />}
                      onClick={() => requestChange(() => {
                        model.markDirty("routing");
                        setSelectedRuleId(-1);
                        setRoutingDraft(buildRoutingDraft(null, payload.queues[0]?.id ?? null));
                        setRoutingConditionBuilder(
                          buildRoutingConditionBuilder(
                            { field: payload.routing_builder.fields[0]?.field ?? "request_kind", op: "eq", value: "" },
                            payload.routing_builder.fields[0]?.field ?? "request_kind"
                          )
                        );
                      })}
                      variant="secondary"
                    >
                    Новое правило
                  </Button>
                  {payload.routing_rules.map((rule) => (
                    <button
                      key={rule.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedRule?.id === rule.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => requestChange(() => setSelectedRuleId(rule.id))}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">Rule #{rule.id}</p>
                        <Badge tone={rule.enabled ? "success" : "neutral"}>{rule.target_queue_name ?? rule.target_queue_id}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Priority: {rule.priority_order}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedRule ? `Rule #${selectedRule.id}` : "Новое правило"}</CardTitle>
                  <CardDescription>
                    Общие правила выбирают очередь по данным обращения. Правила конкретной услуги настраиваются в Студии обращений. Проверьте совместимость правил перед включением.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-3">
                    <SettingsField label="Порядок проверки">
                      <Input data-settings-draft="routing"
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, priority_order: Number(event.target.value) }))}
                        type="number"
                        value={String(routingDraft.priority_order)}
                      />
                    </SettingsField>
                    <SettingsField label="Целевая очередь">
                      <Select data-settings-draft="routing"
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, target_queue_id: Number(event.target.value) }))}
                        value={String(routingDraft.target_queue_id)}
                      >
                        {payload.queues.map((queue) => (
                          <option key={queue.id} value={queue.id}>
                            {queue.name}
                          </option>
                        ))}
                      </Select>
                    </SettingsField>
                    <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                      <input data-settings-draft="routing"
                        checked={routingDraft.enabled}
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, enabled: event.target.checked }))}
                        type="checkbox"
                      />
                      <span>Правило активно</span>
                    </label>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Условие правила</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Выберите поле и условие. Технический каталог форм доступен ниже для справки.
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      <SettingsField label="Поле">
                        <Select data-settings-draft="routing"
                          onChange={(event) =>
                            setRoutingConditionBuilder((current) => ({ ...current, field: event.target.value }))
                          }
                          value={routingConditionBuilder.field}
                        >
                          {payload.routing_builder.fields.map((item) => (
                            <option key={`${item.field}-${item.form_key ?? "base"}`} value={item.field}>
                              {item.label}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      <SettingsField label="Оператор">
                        <Select data-settings-draft="routing"
                          onChange={(event) =>
                            setRoutingConditionBuilder((current) => ({
                              ...current,
                              op: event.target.value,
                            }))
                          }
                          value={routingConditionBuilder.op}
                        >
                          {payload.routing_builder.operators.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      {routingConditionBuilder.op === "is_null" ? (
                        <SettingsField label="Значение">
                          <Select data-settings-draft="routing"
                            onChange={(event) =>
                              setRoutingConditionBuilder((current) => ({
                                ...current,
                                null_state: event.target.value as "true" | "false",
                              }))
                            }
                            value={routingConditionBuilder.null_state}
                          >
                            <option value="true">Пусто</option>
                            <option value="false">Не пусто</option>
                          </Select>
                        </SettingsField>
                      ) : (
                        <SettingsField
                          label={routingConditionBuilder.op === "in" || routingConditionBuilder.op === "nin" ? "Значение (через запятую)" : "Значение"}
                        >
                          <Input data-settings-draft="routing"
                            onChange={(event) =>
                              setRoutingConditionBuilder((current) => ({
                                ...current,
                                value_text: event.target.value,
                              }))
                            }
                            placeholder={
                              routingConditionBuilder.op === "in" || routingConditionBuilder.op === "nin"
                                ? "214, 215"
                                : "access"
                            }
                            value={routingConditionBuilder.value_text}
                          />
                        </SettingsField>
                      )}
                    </div>

                    <div className="mt-4 space-y-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Текущие формы каталога</p>
                      {payload.routing_builder.forms.length === 0 ? (
                        <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-4 text-sm text-slate-500">
                          Формы пока не опубликованы.
                        </div>
                      ) : (
                        payload.routing_builder.forms.map((form) => (
                          <div key={form.key} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <p className="font-medium text-slate-900">{form.title}</p>
                                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{form.request_kind}</p>
                              </div>
                              <Badge tone="neutral">{form.fields.length} полей</Badge>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                              {form.fields.map((field) => (
                                <code key={field.field} className="rounded-pill bg-surface-subtle px-3 py-1 text-[11px]">
                                  {field.field}
                                </code>
                              ))}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Собранное условие</p>
                    <code className="mt-3 block whitespace-pre-wrap rounded-[0.8rem] bg-surface-subtle px-4 py-3 text-xs text-slate-700">
                      {prettyJson(buildRoutingConditionJson(routingConditionBuilder))}
                    </code>
                  </div>

                  <Button disabled={!canManageRouting || routingMutation.isPending} onClick={() => routingMutation.mutate()} className="w-full">
                    {routingMutation.isPending ? "Сохраняем…" : "Сохранить правило"}
                  </Button>
                </CardContent>
              </Card>
            </div>
          );
}

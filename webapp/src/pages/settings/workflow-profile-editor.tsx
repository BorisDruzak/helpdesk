import {WorkflowTransitionEditor} from './workflow-transition-editor';
import {Trash2} from "lucide-react";

import {Button} from "../../components/ui/button";

import {Input} from "../../components/ui/input";

import {type WorkflowProfileDraft} from './settings-types';

import {SettingsField} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function WorkflowProfileEditor({model,profile,index}:{model:ServiceSettingsModel;profile:WorkflowProfileDraft;index:number}){const {canManageWorkflow:canManageRouting,workflowProfileDrafts,setWorkflowProfileDrafts}=model;return (<div key={`${profile.ticket_type}-${index}`} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-950">{profile.label || profile.ticket_type || `Профиль ${index + 1}`}</p>
                            <p className="mt-1 text-xs text-slate-500">{profile.purpose || "назначение не указано"}</p>
                          </div>
                          <Button
                            disabled={!canManageRouting || workflowProfileDrafts.length <= 1}
                            onClick={() => {model.markDirty("workflow");setWorkflowProfileDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));}}
                            variant="ghost"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-3">
                          <SettingsField label="Код типа">
                            <Input data-settings-draft="workflow"
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                {const nextFieldValue = event.currentTarget.value;setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, ticket_type: nextFieldValue } : item
                                  )
                                );}
                              }
                              value={profile.ticket_type}
                            />
                          </SettingsField>
                          <SettingsField label="Название">
                            <Input data-settings-draft="workflow"
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                {const nextFieldValue = event.currentTarget.value;setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, label: nextFieldValue } : item
                                  )
                                );}
                              }
                              value={profile.label}
                            />
                          </SettingsField>
                          <SettingsField label="Назначение">
                            <Input data-settings-draft="workflow"
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                {const nextFieldValue = event.currentTarget.value;setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, purpose: nextFieldValue } : item
                                  )
                                );}
                              }
                              value={profile.purpose}
                            />
                          </SettingsField>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-2">
                          {[
                            ["suggested_path_text", "Рекомендуемый путь"],
                            ["allowed_statuses_text", "Разрешённые статусы"],
                            ["required_create_fields_text", "Поля при создании"],
                            ["required_resolve_fields_text", "Поля при решении"],
                            ["evidence_required_for_priorities_text", "Приоритеты с доказательствами"],
                          ].map(([key, label]) => (
                            <SettingsField key={key} label={label}>
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) =>
                                  {const nextFieldValue = event.currentTarget.value;setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, [key]: nextFieldValue } : item
                                    )
                                  );}
                                }
                                value={String(profile[key as keyof WorkflowProfileDraft] ?? "")}
                              />
                            </SettingsField>
                          ))}
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-3">
                          {[
                            ["requires_approval", "Требует согласование"],
                            ["requires_change_plan", "Требует план изменений"],
                            ["requires_action_log", "Требует журнал действий"],
                          ].map(([key, label]) => (
                            <label key={key} className="flex items-center gap-3 rounded-[1rem] bg-surface-subtle px-4 py-3 text-sm font-medium text-slate-800">
                              <input data-settings-draft="workflow"
                                checked={Boolean(profile[key as keyof WorkflowProfileDraft])}
                                disabled={!canManageRouting}
                                onChange={(event) =>
                                  {const nextFieldChecked = event.currentTarget.checked;setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, [key]: nextFieldChecked } : item
                                    )
                                  );}
                                }
                                type="checkbox"
                              />
                              {label}
                            </label>
                          ))}
                        </div>

                        <WorkflowTransitionEditor model={model} profile={profile} index={index}/>

                        <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer font-medium">Дополнительно: импорт переходов JSON</summary><SettingsField label="Переходы статусов JSON">
                          <textarea data-settings-draft="workflow"
                            className="field-base mt-4 min-h-[220px] w-full px-4 py-3 font-mono text-xs"
                            disabled={!canManageRouting}
                            onChange={(event) =>
                              {const nextFieldValue = event.currentTarget.value;setWorkflowProfileDrafts((current) =>
                                current.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, transitions_json: nextFieldValue } : item
                                )
                              );}
                            }
                            value={profile.transitions_json}
                          />
                        </SettingsField></details>
                      </div>);}

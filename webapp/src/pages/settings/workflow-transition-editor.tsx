import {Workflow} from "lucide-react";

import {Button} from "../../components/ui/button";

import {Input} from "../../components/ui/input";

import {type WorkflowProfileDraft} from './settings-types';
import {applyWorkflowTransitionRule} from './settings-workflow-model';
import {SettingsField} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function WorkflowTransitionEditor({model,profile,index}:{model:ServiceSettingsModel;profile:WorkflowProfileDraft;index:number}){const {canManageWorkflow:canManageRouting,setWorkflowProfileDrafts}=model;return (<div className="mt-4 rounded-[1rem] border border-border bg-surface-subtle px-4 py-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="font-semibold text-slate-950">Правило перехода</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Настройте, кто может перевести тикет, что должно быть заполнено и какие действия выполнить.
                              </p>
                            </div>
                            <Button
                              disabled={!canManageRouting}
                              onClick={() =>
                                {model.markDirty("workflow");setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? applyWorkflowTransitionRule(item) : item
                                  )
                                );}
                              }
                              variant="secondary"
                            >
                              <Workflow className="h-4 w-4" />
                              Применить правило перехода
                            </Button>
                          </div>

                          <div className="mt-4 grid gap-4 lg:grid-cols-3 xl:grid-cols-5">
                            <SettingsField label="Откуда">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_from: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_from}
                              />
                            </SettingsField>
                            <SettingsField label="Куда">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_to: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_to}
                              />
                            </SettingsField>
                            <SettingsField label="Какой комментарий нужен">
                              <select data-settings-draft="workflow"
                                className="field-base w-full px-3 py-2 text-sm"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_required_comment: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_required_comment}
                              >
                                <option value="">Не обязателен</option>
                                <option value="public">Публичный комментарий</option>
                                <option value="internal">Внутренний комментарий</option>
                                <option value="any">Любой комментарий</option>
                              </select>
                            </SettingsField>
                            <SettingsField label="Что сделать со сроками ответа">
                              <select data-settings-draft="workflow"
                                className="field-base w-full px-3 py-2 text-sm"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_sla_action: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_sla_action}
                              >
                                <option value="">Не менять</option>
                                <option value="pause">Поставить на паузу</option>
                                <option value="resume">Продолжить отсчёт</option>
                                <option value="stop">Зафиксировать действие</option>
                              </select>
                            </SettingsField>
                            <SettingsField label="Действие согласования">
                              <select data-settings-draft="workflow"
                                className="field-base w-full px-3 py-2 text-sm"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_approval_action: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_approval_action}
                              >
                                <option value="">None</option>
                                <option value="create_request">Create approval request</option>
                                <option value="require_existing">Require existing approval</option>
                              </select>
                            </SettingsField>
                          </div>

                          <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
                            <SettingsField label="Роли, которые могут перевести">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, transition_builder_allowed_roles_text: value }
                                        : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_allowed_roles_text}
                              />
                            </SettingsField>
                            <SettingsField label="Поля, обязательные перед переходом">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, transition_builder_required_fields_text: value }
                                        : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_required_fields_text}
                              />
                            </SettingsField>
                            <SettingsField label="Кого уведомить">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_notify_text: value } : item
                                    )
                                  );
                                }}
                                value={profile.transition_builder_notify_text}
                              />
                            </SettingsField>
                            <SettingsField label="Поля журнала">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, transition_builder_log_fields_text: value }
                                        : item
                                    )
                                  );
                                }}
                                placeholder="resolution_code, custom_fields.routing_decision.queue"
                                value={profile.transition_builder_log_fields_text}
                              />
                            </SettingsField>
                          </div>

                          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(12rem,16rem)]">
                            <SettingsField label="Событие запуска">
                              <Input data-settings-draft="workflow"
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldValue = event.currentTarget.value;
                                  const value = nextFieldValue;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_trigger: value } : item
                                    )
                                  );
                                }}
                                placeholder="requester_replied"
                                value={profile.transition_builder_trigger}
                              />
                            </SettingsField>
                            <label className="flex items-center gap-3 rounded-[0.9rem] bg-white px-4 py-3 text-sm font-medium text-slate-800">
                              <input data-settings-draft="workflow"
                                checked={profile.transition_builder_auto}
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldChecked = event.currentTarget.checked;
                                  const checked = nextFieldChecked;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, transition_builder_auto: checked } : item
                                    )
                                  );
                                }}
                                type="checkbox"
                              />
                              Автоматический переход
                            </label>
                          </div>

                          <div className="mt-4 grid gap-3 md:grid-cols-2">
                            <label className="flex items-center gap-3 rounded-[0.9rem] bg-white px-4 py-3 text-sm font-medium text-slate-800">
                              <input data-settings-draft="workflow"
                                checked={profile.transition_builder_require_approval}
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldChecked = event.currentTarget.checked;
                                  const checked = nextFieldChecked;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, transition_builder_require_approval: checked }
                                        : item
                                    )
                                  );
                                }}
                                type="checkbox"
                              />
                              Нужно согласование
                            </label>
                            <label className="flex items-center gap-3 rounded-[0.9rem] bg-white px-4 py-3 text-sm font-medium text-slate-800">
                              <input data-settings-draft="workflow"
                                checked={profile.transition_builder_require_evidence}
                                disabled={!canManageRouting}
                                onChange={(event) => {const nextFieldChecked = event.currentTarget.checked;
                                  const checked = nextFieldChecked;
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, transition_builder_require_evidence: checked }
                                        : item
                                    )
                                  );
                                }}
                                type="checkbox"
                              />
                              Нужно доказательство
                            </label>
                          </div>
                        </div>);}

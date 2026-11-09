import {useState} from 'react';
import {WorkflowProfileEditor} from './workflow-profile-editor';
import {Plus, Workflow} from "lucide-react";
import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import {createWorkflowProfileDraft} from './settings-workflow-model';
import {PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function WorkflowProfiles({model}:{model:ServiceSettingsModel}){const [selectedIndex,setSelectedIndex]=useState(0);const {canManageWorkflow:canManageRouting,workflowDeniedReason:routingDeniedReason,workflowProfileDrafts,setWorkflowProfileDrafts,workflowProfilesMutation}=model;if(!model.payload)return null;
return (<Card>
                <CardHeader>
                  <CardTitle>Профили процесса</CardTitle>
                  <CardDescription>Тип процесса выбирает жизненный цикл и разрешённые переходы статусов.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="info">{workflowProfileDrafts.length} профилей</Badge>
                      <Badge tone="neutral">переходы редактируются визуально и совместимы с JSON</Badge>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        disabled={!canManageRouting}
                        onClick={() =>
                          {model.markDirty("workflow");setWorkflowProfileDrafts((current) => [
                            ...current,
                            createWorkflowProfileDraft(current.length + 1),
                          ]);}
                        }
                        variant="secondary"
                      >
                        <Plus className="h-4 w-4" />
                        Новый тип
                      </Button>
                      <Button
                        disabled={!canManageRouting || workflowProfilesMutation.isPending}
                        onClick={() => workflowProfilesMutation.mutate()}
                      >
                        <Workflow className="h-4 w-4" />
                        Сохранить профили процесса
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <label className="block font-medium">Профиль процесса<select data-settings-draft="view" aria-label="Профиль процесса" className="ml-3 rounded border p-2" value={Math.min(selectedIndex,workflowProfileDrafts.length-1)} onChange={event=>setSelectedIndex(Number(event.target.value))}>{workflowProfileDrafts.map((profile,index)=><option key={index} value={index}>{profile.label||`Профиль ${index+1}`}</option>)}</select></label>{workflowProfileDrafts.map((profile, index) => index===Math.min(selectedIndex,workflowProfileDrafts.length-1) && (<WorkflowProfileEditor key={index} model={model} profile={profile} index={index}/>))}
                  </div>
                </CardContent>
              </Card>);}

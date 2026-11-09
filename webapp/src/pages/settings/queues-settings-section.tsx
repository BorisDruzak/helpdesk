import {QueueMemberPicker} from "./queue-member-picker";
import {DurationTargetsEditor} from "./duration-targets-editor";
import {Plus} from "lucide-react";

import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";
import {Input} from "../../components/ui/input";

import {buildQueueDraft, buildOlaDraft} from './settings-form-model';

import {SettingsField, PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function QueuesSettingsSection({model}:{model:ServiceSettingsModel}){const {requestChange,setDirty,payload,canManageQueues,queueDeniedReason,setSelectedQueueId,selectedQueue,queueDraft,setQueueDraft,olaDraft,setOlaDraft,newMemberActorId,setNewMemberActorId,newMemberRole,setNewMemberRole,queueMutation,memberMutation,removeMemberMutation,olaMutation}=model; if(!payload)return null;
return (
            <div className="settings-object-editor">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Очереди</CardTitle>
                  <CardDescription>{payload.ticket_settings.operational_flags.queue_mode === "unified" ? "Включена единая очередь: все активные операторы работают с общим списком. Настройки очередей сохранены для возврата к разделению. Режим задаётся администратором сервера. Настройки разделённых очередей не меняют видимость общего списка." : "Выбор очереди, участники и внутренние сроки принятия и обработки."}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    disabled={!canManageQueues}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => requestChange(() => {
                      setSelectedQueueId(-1);
                      setDirty(true);
                      setQueueDraft(buildQueueDraft(null));
                      setOlaDraft(buildOlaDraft(null));
                    })}
                    variant="secondary"
                  >
                    Новая очередь
                  </Button>
                  {payload.queues.map((queue) => (
                    <button
                      key={queue.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedQueue?.id === queue.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => requestChange(() => setSelectedQueueId(queue.id))}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{queue.name}</p>
                        <Badge tone={queue.is_active ? "success" : "neutral"}>{queue.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">
                        Открыто: {queue.open_tickets_count} • участников: {queue.members.length}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <PermissionNotice text={queueDeniedReason} />
                <Card>
                  <CardHeader>
                    <CardTitle>{selectedQueue ? "Настройки очереди" : "Новая очередь"}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <SettingsField label="Код">
                        <Input data-settings-draft="queue"
                          onChange={(event) => setQueueDraft((current) => ({ ...current, code: event.target.value }))}
                          value={queueDraft.code}
                        />
                      </SettingsField>
                      <SettingsField label="Название">
                        <Input data-settings-draft="queue"
                          onChange={(event) => setQueueDraft((current) => ({ ...current, name: event.target.value }))}
                          value={queueDraft.name}
                        />
                      </SettingsField>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input data-settings-draft="queue"
                          checked={queueDraft.is_triage}
                          onChange={(event) => setQueueDraft((current) => ({ ...current, is_triage: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Первичная обработка</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input data-settings-draft="queue"
                          checked={queueDraft.is_active}
                          onChange={(event) => setQueueDraft((current) => ({ ...current, is_active: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Активна</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input data-settings-draft="queue"
                          checked={queueDraft.auto_assign_enabled}
                          onChange={(event) =>
                            setQueueDraft((current) => ({ ...current, auto_assign_enabled: event.target.checked }))
                          }
                          type="checkbox"
                        />
                        <span>Автоназначение</span>
                      </label>
                    </div>
                    <Button disabled={!canManageQueues || queueMutation.isPending} onClick={() => queueMutation.mutate()} className="w-full">
                      {queueMutation.isPending ? "Сохраняем…" : "Сохранить очередь"}
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-6 2xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Участники очереди</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {selectedQueue?.members.length ? (
                        selectedQueue.members.map((member) => (
                          <div key={member.actor_id} className="flex items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                            <div>
                              <p className="font-medium text-slate-900">{member.actor_id}</p>
                              <p className="text-slate-500">{member.role_in_queue ?? "role_in_queue не задан"}</p>
                            </div>
                            <Button
                              disabled={!canManageQueues || removeMemberMutation.isPending}
                              onClick={() => removeMemberMutation.mutate(member.actor_id)}
                              size="sm"
                              variant="ghost"
                            >
                              Удалить
                            </Button>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-slate-500">У выбранной очереди участников пока нет.</p>
                      )}

                      <QueueMemberPicker model={model}/>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Внутренние сроки очереди</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <DurationTargetsEditor kind="ola" disabled={!canManageQueues} rows={olaDraft.map(row=>({priority:row.priority,first:row.ack_min,second:row.processing_min}))} onFirst={(priority,value)=>setOlaDraft(rows=>rows.map(row=>row.priority===priority?{...row,ack_min:value}:row))} onSecond={(priority,value)=>setOlaDraft(rows=>rows.map(row=>row.priority===priority?{...row,processing_min:value}:row))}/>
                      <Button disabled={!canManageQueues || olaMutation.isPending || !selectedQueue} onClick={() => olaMutation.mutate()} className="w-full">
                        Сохранить внутренние сроки
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          );
}

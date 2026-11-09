

import {Badge} from "../../components/ui/badge";

import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "../../components/ui/card";

import {formatDateTime} from './settings-form-model';

import type {ServiceSettingsModel} from './use-service-settings';
export function AuditSettingsSection({model}:{model:ServiceSettingsModel}){const {payload}=model; if(!payload)return null;
return (
            <Card>
              <CardHeader>
                <CardTitle>Журнал аудита</CardTitle>
                <CardDescription>Последние real-data изменения admin-config в новом интерфейсе.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.audit.length ? (
                  payload.audit.map((item) => (
                    <div key={item.id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">
                            {item.entity_type} / {item.entity_id}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {item.action} • {item.actor_id} ({item.actor_role})
                          </p>
                        </div>
                        <Badge tone="info">{formatDateTime(item.created_at)}</Badge>
                      </div>
                      <p className="mt-3 text-xs text-slate-400">{item.trace_id ?? "trace_id не передан"}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Записей аудита пока нет.</p>
                )}
              </CardContent>
            </Card>
          );
}

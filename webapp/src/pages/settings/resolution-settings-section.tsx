import {Plus, Trash2} from "lucide-react";

import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardHeader, CardTitle} from "../../components/ui/card";
import {Input} from "../../components/ui/input";

import {buildResolutionDraft} from './settings-form-model';

import {SettingsField, PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function ResolutionSettingsSection({model}:{model:ServiceSettingsModel}){const {requestChange,setDirty,payload,canManageRouting,routingDeniedReason,setSelectedResolutionCode,selectedResolution,resolutionDraft,setResolutionDraft,resolutionMutation,deleteResolutionMutation}=model; if(!payload)return null;
return (
            <div className="settings-object-editor">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Коды решения</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PermissionNotice text={routingDeniedReason} />
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => requestChange(() => {
                      setSelectedResolutionCode("__new__");
                      setDirty(true);
                      setResolutionDraft(buildResolutionDraft(null));
                    })}
                    variant="secondary"
                  >
                    Новый код
                  </Button>
                  {payload.resolution_codes.map((item) => (
                    <button
                      key={item.code}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedResolution?.code === item.code ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => requestChange(() => setSelectedResolutionCode(item.code))}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{item.name}</p>
                        <Badge tone={item.is_active ? "success" : "neutral"}>{item.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Использований: {item.usage_count}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedResolution ? selectedResolution.name : "Новый код решения"}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Код">
                      <Input data-settings-draft="resolution"
                        disabled={Boolean(selectedResolution)}
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, code: event.target.value }))}
                        value={resolutionDraft.code}
                      />
                    </SettingsField>
                    <SettingsField label="Название">
                      <Input data-settings-draft="resolution"
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, name: event.target.value }))}
                        value={resolutionDraft.name}
                      />
                    </SettingsField>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Порядок">
                      <Input data-settings-draft="resolution"
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, sort_order: Number(event.target.value) }))}
                        type="number"
                        value={String(resolutionDraft.sort_order)}
                      />
                    </SettingsField>
                    <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                      <input data-settings-draft="resolution"
                        checked={resolutionDraft.is_active}
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, is_active: event.target.checked }))}
                        type="checkbox"
                      />
                      <span>Код активен</span>
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button disabled={!canManageRouting || resolutionMutation.isPending} onClick={() => resolutionMutation.mutate()}>
                      Сохранить код
                    </Button>
                    <Button
                      disabled={!canManageRouting || deleteResolutionMutation.isPending || !selectedResolution || selectedResolution.usage_count > 0}
                      leadingIcon={<Trash2 className="h-4 w-4" />}
                      onClick={() => deleteResolutionMutation.mutate()}
                      variant="outline"
                    >
                      Удалить код
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          );
}

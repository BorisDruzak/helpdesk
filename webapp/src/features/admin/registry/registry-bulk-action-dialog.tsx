import { useEffect, useMemo, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryBulkResponse, AdminRegistryOperationPreview, AdminRegistryPayload } from "../api";
import { RegistryOperationPreview } from "./registry-operation-preview";

export type RegistryBulkOperation =
  | "devices.assign_location"
  | "devices.assign_department"
  | "devices.revoke_account_sessions"
  | "people.assign_department"
  | "account_sessions.revoke";

export type RegistryBulkDialogState = {
  operation: RegistryBulkOperation;
  ids: string[];
} | null;

type Props = {
  busy?: boolean;
  registry: AdminRegistryPayload | null;
  state: RegistryBulkDialogState;
  onApply: (state: Exclude<RegistryBulkDialogState, null>, payload: { target_id?: string; reason: string }) => Promise<AdminRegistryBulkResponse> | void;
  onClose: () => void;
  onPreview: (payload: { operation: RegistryBulkOperation; ids: string[]; payload?: Record<string, unknown> }) => Promise<AdminRegistryOperationPreview>;
};

const operationLabels: Record<RegistryBulkOperation, string> = {
  "devices.assign_location": "Назначить локацию устройствам",
  "devices.assign_department": "Назначить подразделение устройствам",
  "devices.revoke_account_sessions": "Отозвать сессии устройств",
  "people.assign_department": "Назначить подразделение пользователям",
  "account_sessions.revoke": "Отозвать аккаунт-сессии",
};

function requiresDepartment(operation: RegistryBulkOperation): boolean {
  return operation === "devices.assign_department" || operation === "people.assign_department";
}

function requiresLocation(operation: RegistryBulkOperation): boolean {
  return operation === "devices.assign_location";
}

function previewPayload(operation: RegistryBulkOperation, targetId: string): Record<string, unknown> | undefined {
  if (requiresDepartment(operation)) {
    return { department_id: targetId };
  }
  if (requiresLocation(operation)) {
    return { location_id: targetId };
  }
  return undefined;
}

export function RegistryBulkActionDialog({ busy, onApply, onClose, onPreview, registry, state }: Props) {
  const [targetId, setTargetId] = useState("");
  const [targetQuery, setTargetQuery] = useState("");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<AdminRegistryOperationPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const departmentOptions = useMemo(() => {
    const normalized = targetQuery.trim().toLowerCase();
    return (registry?.departments ?? [])
      .filter((department) => department.status === "active")
      .filter((department) => !normalized || `${department.code ?? ""} ${department.name}`.toLowerCase().includes(normalized))
      .map((department) => ({
        id: department.department_id ?? department.id,
        label: `${department.code ? `${department.code} · ` : ""}${department.name}`,
      }));
  }, [registry?.departments, targetQuery]);

  const locationOptions = useMemo(() => {
    const normalized = targetQuery.trim().toLowerCase();
    return (registry?.locations ?? [])
      .filter((location) => location.status === "active")
      .filter((location) => !normalized || `${location.display_name} ${location.building ?? ""} ${location.room ?? ""}`.toLowerCase().includes(normalized))
      .map((location) => ({
        id: location.location_id ?? location.id,
        label: location.display_name,
      }));
  }, [registry?.locations, targetQuery]);

  const targetOptions = state && requiresDepartment(state.operation) ? departmentOptions : locationOptions;
  const needsTarget = Boolean(state && (requiresDepartment(state.operation) || requiresLocation(state.operation)));

  useEffect(() => {
    setTargetId("");
    setTargetQuery("");
    setReason("");
    setPreview(null);
    setError(null);
  }, [state]);

  if (!state) {
    return null;
  }

  const targetLabel = requiresDepartment(state.operation) ? "Подразделение" : "Локация";

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Массовая операция</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-slate-50 px-3 py-3 text-sm">
            <p className="font-semibold text-slate-950">{operationLabels[state.operation]}</p>
            <p className="mt-1 text-slate-600">Выбрано объектов: {state.ids.length}</p>
          </div>
          {needsTarget ? (
            <div className="space-y-3">
              <label className="block text-sm font-medium text-slate-700">
                Поиск
                <Input
                  className="mt-2"
                  onChange={(event) => {
                    setTargetQuery(event.target.value);
                    setPreview(null);
                  }}
                  placeholder={requiresDepartment(state.operation) ? "код или название подразделения" : "здание, кабинет или название"}
                  value={targetQuery}
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                {targetLabel}
                <select
                  aria-label={targetLabel}
                  className="field-base mt-2 h-11 w-full px-3 text-sm"
                  onChange={(event) => {
                    setTargetId(event.target.value);
                    setPreview(null);
                  }}
                  value={targetId}
                >
                  <option value="">Выберите {targetLabel.toLowerCase()}</option>
                  {targetOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </label>
            </div>
          ) : null}
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input
              aria-label="Причина"
              className="mt-2"
              onChange={(event) => {
                setReason(event.target.value);
                setPreview(null);
              }}
              value={reason}
            />
          </label>
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <RegistryOperationPreview preview={preview} />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={previewBusy || (needsTarget && !targetId)}
              onClick={async () => {
                setPreviewBusy(true);
                setError(null);
                try {
                  setPreview(await onPreview({
                    operation: state.operation,
                    ids: state.ids,
                    payload: previewPayload(state.operation, targetId),
                  }));
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Не удалось построить предпросмотр");
                } finally {
                  setPreviewBusy(false);
                }
              }}
              variant="outline"
            >
              {previewBusy ? "Строим..." : "Предпросмотр"}
            </Button>
            <Button
              disabled={busy || !reason.trim() || !preview || (needsTarget && !targetId)}
              onClick={() => void onApply(state, { target_id: targetId || undefined, reason: reason.trim() })}
            >
              Применить
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

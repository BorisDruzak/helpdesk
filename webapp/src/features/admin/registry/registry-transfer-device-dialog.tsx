import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryOperationPreview, AdminRegistryPayload } from "../api";
import { RegistryOperationPreview } from "./registry-operation-preview";

export type TransferDeviceDialogState = {
  deviceId: string;
  hostname?: string | null;
} | null;

type Props = {
  state: TransferDeviceDialogState;
  people: AdminRegistryPayload["people"];
  onClose: () => void;
  onPreview: (payload: { device_id: string; new_person_id: string; old_binding_action: "transferred" | "revoked" | "keep_as_shared" }) => Promise<AdminRegistryOperationPreview>;
  onSubmit: (payload: { device_id: string; new_person_id: string; old_binding_action: "transferred" | "revoked" | "keep_as_shared"; reason: string }) => void;
  busy?: boolean;
};

export function RegistryTransferDeviceDialog({ busy, onClose, onPreview, onSubmit, people, state }: Props) {
  const [personId, setPersonId] = useState("");
  const [oldBindingAction, setOldBindingAction] = useState<"transferred" | "revoked" | "keep_as_shared">("transferred");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<AdminRegistryOperationPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    setPersonId("");
    setOldBindingAction("transferred");
    setReason("");
    setPreview(null);
    setPreviewError(null);
  }, [state]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Передать устройство {state.hostname ?? state.deviceId}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Новый владелец
            <select className="field-base mt-2 h-11 w-full px-3 text-sm" onChange={(event) => { setPersonId(event.target.value); setPreview(null); }} value={personId}>
              <option value="">Выберите пользователя</option>
              {people.map((person) => (
                <option key={person.person_id} value={person.person_id}>{person.display_name}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Что сделать со старой primary-привязкой
            <select className="field-base mt-2 h-11 w-full px-3 text-sm" onChange={(event) => { setOldBindingAction(event.target.value as typeof oldBindingAction); setPreview(null); }} value={oldBindingAction}>
              <option value="transferred">Пометить как transferred</option>
              <option value="revoked">Отозвать</option>
              <option value="keep_as_shared">Оставить как shared</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input className="mt-2" onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          {previewError ? <p className="text-sm text-rose-600">{previewError}</p> : null}
          <RegistryOperationPreview preview={preview} />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={previewBusy || !personId}
              onClick={async () => {
                setPreviewBusy(true);
                setPreviewError(null);
                try {
                  setPreview(await onPreview({ device_id: state.deviceId, new_person_id: personId, old_binding_action: oldBindingAction }));
                } catch (error) {
                  setPreviewError(error instanceof Error ? error.message : "Не удалось построить предпросмотр");
                } finally {
                  setPreviewBusy(false);
                }
              }}
              variant="outline"
            >
              {previewBusy ? "Строим..." : "Предпросмотр"}
            </Button>
            <Button
              disabled={busy || !personId || !reason.trim() || !preview}
              onClick={() => onSubmit({
                device_id: state.deviceId,
                new_person_id: personId,
                old_binding_action: oldBindingAction,
                reason: reason.trim(),
              })}
            >
              Передать
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

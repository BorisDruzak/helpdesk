import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryPayload } from "../api";

type BindMode = "primary_user" | "shared_user" | "responsible" | "temporary_user";

export type BindPersonDialogState = {
  deviceId: string;
  mode: BindMode;
  personId?: string;
  title: string;
  replaceExisting?: boolean;
} | null;

type Props = {
  state: BindPersonDialogState;
  people: AdminRegistryPayload["people"];
  onClose: () => void;
  onSubmit: (payload: { device_id: string; person_id: string; relationship_type: BindMode; replace_existing: boolean; reason: string }) => void;
  busy?: boolean;
};

export function RegistryBindPersonDialog({ busy, onClose, onSubmit, people, state }: Props) {
  const [personId, setPersonId] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [reason, setReason] = useState("");
  const [replaceExisting, setReplaceExisting] = useState(false);

  useEffect(() => {
    setPersonId(state?.personId ?? "");
    setDeviceId(state?.deviceId ?? "");
    setReason("");
    setReplaceExisting(Boolean(state?.replaceExisting));
  }, [state]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{state.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Device ID
            <Input className="mt-2" disabled={Boolean(state.deviceId)} onChange={(event) => setDeviceId(event.target.value)} value={deviceId} />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Пользователь
            <select
              className="field-base mt-2 h-11 w-full px-3 text-sm"
              onChange={(event) => setPersonId(event.target.value)}
              value={personId}
            >
              <option value="">Выберите пользователя</option>
              {people.map((person) => (
                <option key={person.person_id} value={person.person_id}>
                  {person.display_name} {person.login ? `(${person.login})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input className="mt-2" onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          {state.mode === "primary_user" || state.mode === "responsible" ? (
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input checked={replaceExisting} onChange={(event) => setReplaceExisting(event.target.checked)} type="checkbox" />
              Заменить текущую активную привязку этого типа
            </label>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={busy || !deviceId.trim() || !personId || !reason.trim()}
              onClick={() => onSubmit({
                device_id: deviceId.trim(),
                person_id: personId,
                relationship_type: state.mode,
                replace_existing: replaceExisting,
                reason: reason.trim(),
              })}
            >
              Применить
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";

export type RegistryReasonDialogState = {
  title: string;
  defaultReason: string;
  confirmLabel?: string;
  tone?: "default" | "danger";
  onConfirm: (reason: string) => void;
} | null;

type Props = {
  busy?: boolean;
  state: RegistryReasonDialogState;
  onClose: () => void;
};

export function RegistryReasonDialog({ busy, onClose, state }: Props) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    setReason(state?.defaultReason ?? "");
  }, [state]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{state.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input
              aria-label="Причина"
              className="mt-2"
              onChange={(event) => setReason(event.target.value)}
              value={reason}
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              className={state.tone === "danger" ? "bg-rose-600 hover:bg-rose-700 active:bg-rose-800" : undefined}
              disabled={busy || !reason.trim()}
              onClick={() => state.onConfirm(reason.trim())}
            >
              {state.confirmLabel ?? "Применить"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

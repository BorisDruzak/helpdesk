import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";

export type IdentityDialogState = {
  personId: string;
  personName: string;
} | null;

type Props = {
  state: IdentityDialogState;
  onClose: () => void;
  onSubmit: (personId: string, payload: { provider: string; identifier: string; verified: boolean; reason: string }) => void;
  busy?: boolean;
};

const providers = ["windows_login", "ui_login", "ad", "email", "phone", "manual"];
const providerLabels: Record<string, string> = {
  windows_login: "Windows-логин",
  ui_login: "UI-аккаунт",
  ad: "Active Directory",
  email: "Почта",
  phone: "Телефон",
  manual: "Вручную",
};

export function RegistryIdentityDialog({ busy, onClose, onSubmit, state }: Props) {
  const [provider, setProvider] = useState("windows_login");
  const [identifier, setIdentifier] = useState("");
  const [verified, setVerified] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    setProvider("windows_login");
    setIdentifier("");
    setVerified(false);
    setReason("");
  }, [state]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Добавить идентичность: {state.personName}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Источник
            <select className="field-base mt-2 h-11 w-full px-3 text-sm" onChange={(event) => setProvider(event.target.value)} value={provider}>
              {providers.map((item) => <option key={item} value={item}>{providerLabels[item] ?? item}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Идентификатор
            <Input className="mt-2" onChange={(event) => setIdentifier(event.target.value)} value={identifier} />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input checked={verified} onChange={(event) => setVerified(event.target.checked)} type="checkbox" />
            Подтверждено администратором
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input className="mt-2" onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={busy || !identifier.trim() || !reason.trim()}
              onClick={() => onSubmit(state.personId, { provider, identifier: identifier.trim(), verified, reason: reason.trim() })}
            >
              Добавить
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

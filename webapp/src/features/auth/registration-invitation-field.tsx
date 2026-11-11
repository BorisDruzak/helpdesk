import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { previewRegistrationInvitation, type RegistrationInvitation } from "./requester-registration";

type Props = {
  code: string;
  onCodeChange: (value: string) => void;
  selected: RegistrationInvitation | null;
  onSelect: (value: RegistrationInvitation) => void;
  retry?: boolean;
};

export function RegistrationInvitationField({ code, onCodeChange, selected, onSelect, retry }: Props) {
  const [preview, setPreview] = useState<RegistrationInvitation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function check() {
    if (loading) return;
    setLoading(true);
    setError("");
    setPreview(null);
    try {
      setPreview(await previewRegistrationInvitation(code.trim()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось проверить приглашение.");
    } finally {
      setLoading(false);
    }
  }

  const employee = selected ?? preview;
  const field = (
    <div className="space-y-3 pt-2">
      <label className="block space-y-1 text-sm font-medium">
        Код приглашения
        <Input type="password" autoComplete="off" spellCheck={false} maxLength={60}
          disabled={loading} value={code}
          onChange={(event) => { onCodeChange(event.target.value); setPreview(null); setError(""); }} />
      </label>
      {!retry && !selected ? <Button type="button" variant="outline" disabled={loading || !code.trim()} onClick={() => void check()}>
        {loading ? "Проверяем…" : "Проверить код"}
      </Button> : null}
      {error ? <p className="text-sm text-rose-700" role="alert">{error}</p> : null}
      {employee ? (
        <div className="space-y-2 rounded-xl bg-slate-50 p-3 text-sm">
          <p className="font-semibold">{employee.full_name}</p>
          <p>{employee.department}</p>
          {selected ? <p role="status">Запись выбрана.</p> :
            <Button type="button" variant="outline" onClick={() => onSelect(employee)}>Это моя запись</Button>}
        </div>
      ) : null}
      {retry ? <p className="text-sm text-slate-600">Для повтора введите тот же код приглашения.</p> : null}
    </div>
  );
  return retry ? field : <details className="rounded-xl border p-3">
    <summary className="cursor-pointer text-sm font-semibold">У меня есть приглашение</summary>
    {field}
  </details>;
}

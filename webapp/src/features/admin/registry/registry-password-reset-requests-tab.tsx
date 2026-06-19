import { KeyRound } from "lucide-react";
import { useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminPasswordResetRequest } from "../api";
import { formatDateTime, registryStatusLabel, statusTone } from "./registry-utils";

type Props = {
  busy?: boolean;
  requests: AdminPasswordResetRequest[];
  onComplete: (request: AdminPasswordResetRequest, payload: { password: string; reason: string }) => void;
};

export function RegistryPasswordResetRequestsTab({ busy = false, requests, onComplete }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(requests[0]?.request_id ?? null);
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const selected = requests.find((item) => item.request_id === selectedId) ?? requests[0] ?? null;
  const canSubmit = Boolean(selected && selected.status === "pending" && password.trim() && reason.trim());

  const submit = () => {
    if (!selected || !canSubmit) {
      return;
    }
    onComplete(selected, { password, reason });
    setPassword("");
    setReason("");
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[820px] grid-cols-[260px_140px_190px_170px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>Логин</span><span>Статус</span><span>Подана</span><span>Исполнитель</span>
        </div>
        {requests.length ? requests.map((request) => (
          <button
            className={`grid min-w-[820px] grid-cols-[260px_140px_190px_170px] gap-3 border-t border-border px-4 py-3 text-left text-sm ${selected?.request_id === request.request_id ? "bg-brand-50" : "bg-white hover:bg-slate-50"}`}
            key={request.request_id}
            onClick={() => setSelectedId(request.request_id)}
            type="button"
          >
            <span className="font-semibold text-slate-950">{request.login}</span>
            <Badge tone={statusTone(request.status)}>{registryStatusLabel(request.status)}</Badge>
            <span>{formatDateTime(request.requested_at)}</span>
            <span>{request.completed_by ?? "Не назначен"}</span>
          </button>
        )) : (
          <div className="border-t border-border p-4">
            <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Заявок на смену пароля нет.</p>
          </div>
        )}
      </section>

      <aside className="rounded-lg border border-border bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-950">Смена пароля</h3>
        {selected ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg bg-surface-subtle px-3 py-2 text-sm text-slate-600">
              <p className="font-semibold text-slate-900">{selected.login}</p>
              <p>Заявка: {formatDateTime(selected.requested_at)}</p>
            </div>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-800">Новый пароль</span>
              <input
                autoComplete="new-password"
                className="field-base h-11 px-3 text-sm"
                disabled={busy || selected.status !== "pending"}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                value={password}
              />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-800">Причина</span>
              <textarea
                className="field-base min-h-24 px-3 py-2 text-sm"
                disabled={busy || selected.status !== "pending"}
                onChange={(event) => setReason(event.target.value)}
                value={reason}
              />
            </label>
            <Button disabled={!canSubmit || busy} leadingIcon={<KeyRound className="h-4 w-4" />} onClick={submit} size="sm">
              {busy ? "Сохраняем..." : "Сохранить пароль"}
            </Button>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500">Выберите заявку из списка.</p>
        )}
      </aside>
    </div>
  );
}

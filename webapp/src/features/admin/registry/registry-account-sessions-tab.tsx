import { ArrowUpRight, LogOut } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminDeviceAccountSession } from "../api";
import { accountModeLabel, formatDateTime, registryStatusLabel, statusTone, verificationMethodLabel, type RegistrySelection } from "./registry-utils";

type Props = {
  sessions: AdminDeviceAccountSession[];
  onRevoke: (session: AdminDeviceAccountSession) => void;
  onSelect: (selection: RegistrySelection) => void;
  onToggleSelection: (id: string) => void;
  onToggleVisibleSelection: (ids: string[]) => void;
  selectedIds: string[];
};

export function RegistryAccountSessionsTab({ onRevoke, onSelect, onToggleSelection, onToggleVisibleSelection, selectedIds, sessions }: Props) {
  const visibleIds = sessions.map((session) => session.session_id).filter(Boolean);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className="grid min-w-[1310px] grid-cols-[48px_220px_190px_180px_160px_150px_160px_190px_150px_150px_120px_180px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
        <input aria-label="Выбрать все видимые аккаунт-сессии" checked={allVisibleSelected} disabled={!visibleIds.length} onChange={() => onToggleVisibleSelection(visibleIds)} title="Выбрать или снять выбор со всех сессий в текущем фильтре" type="checkbox" />
        <span>ID сессии</span><span>Устройство</span><span>Аккаунт</span><span>Режим</span><span>Статус</span><span>Проверка</span><span>Базовый владелец</span><span>Создана</span><span>Истекает</span><span>Отозвана</span><span>Действия</span>
      </div>
      {sessions.length ? sessions.map((session) => (
        <div className="grid min-w-[1310px] grid-cols-[48px_220px_190px_180px_160px_150px_160px_190px_150px_150px_120px_180px] gap-3 border-t border-border px-4 py-3 text-sm" key={session.session_id}>
          <input
            aria-label={`Выбрать аккаунт-сессию ${session.session_id}`}
            checked={selectedIds.includes(session.session_id)}
            onChange={() => onToggleSelection(session.session_id)}
            type="checkbox"
          />
          <button className="break-all text-left text-brand-700" onClick={() => onSelect({ kind: "session", id: session.session_id })} type="button">{session.session_id}</button>
          <span className="break-all">{session.device_id}</span>
          <span>{session.display_name ?? session.login ?? session.person_id ?? "Нет данных"}</span>
          <span title={session.account_mode}>{accountModeLabel(session.account_mode)}</span>
          <Badge tone={statusTone(session.verification_status)}>{registryStatusLabel(session.verification_status)}</Badge>
          <span title={session.verification_method ?? undefined}>{verificationMethodLabel(session.verification_method)}</span>
          <span>{session.base_person_id ?? session.binding_id ?? "Нет данных"}</span>
          <span>{formatDateTime(session.created_at)}</span>
          <span>{formatDateTime(session.expires_at)}</span>
          <span>{formatDateTime(session.revoked_at)}</span>
          <div className="flex flex-wrap gap-2">
            <Button leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={() => onSelect({ kind: "session", id: session.session_id })} size="sm" title="Открыть историю сессии и связанные события" variant="outline">История</Button>
            <Button disabled={session.verification_status === "revoked"} leadingIcon={<LogOut className="h-4 w-4" />} onClick={() => onRevoke(session)} size="sm" title="Отозвать аккаунт-сессию пользователя на устройстве" variant="ghost">Отозвать</Button>
          </div>
        </div>
      )) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Аккаунт-сессии не найдены.</p></div>}
    </div>
  );
}

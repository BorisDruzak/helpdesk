import { ArrowUpRight, LogOut } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminDeviceAccountSession } from "../api";
import { formatDateTime, statusTone, type RegistrySelection } from "./registry-utils";

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
        <input aria-label="Select visible account sessions" checked={allVisibleSelected} disabled={!visibleIds.length} onChange={() => onToggleVisibleSelection(visibleIds)} type="checkbox" />
        <span>Session ID</span><span>Device</span><span>Account</span><span>Mode</span><span>Status</span><span>Method</span><span>Base owner</span><span>Created</span><span>Expires</span><span>Revoked</span><span>Actions</span>
      </div>
      {sessions.length ? sessions.map((session) => (
        <div className="grid min-w-[1310px] grid-cols-[48px_220px_190px_180px_160px_150px_160px_190px_150px_150px_120px_180px] gap-3 border-t border-border px-4 py-3 text-sm" key={session.session_id}>
          <input
            aria-label={`Select account session ${session.session_id}`}
            checked={selectedIds.includes(session.session_id)}
            onChange={() => onToggleSelection(session.session_id)}
            type="checkbox"
          />
          <button className="break-all text-left text-brand-700" onClick={() => onSelect({ kind: "session", id: session.session_id })} type="button">{session.session_id}</button>
          <span className="break-all">{session.device_id}</span>
          <span>{session.display_name ?? session.login ?? session.person_id ?? "Нет данных"}</span>
          <span>{session.account_mode}</span>
          <Badge tone={statusTone(session.verification_status)}>{session.verification_status}</Badge>
          <span>{session.verification_method ?? "Нет данных"}</span>
          <span>{session.base_person_id ?? session.binding_id ?? "Нет данных"}</span>
          <span>{formatDateTime(session.created_at)}</span>
          <span>{formatDateTime(session.expires_at)}</span>
          <span>{formatDateTime(session.revoked_at)}</span>
          <div className="flex flex-wrap gap-2">
            <Button leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={() => onSelect({ kind: "session", id: session.session_id })} size="sm" variant="outline">Timeline</Button>
            <Button disabled={session.verification_status === "revoked"} leadingIcon={<LogOut className="h-4 w-4" />} onClick={() => onRevoke(session)} size="sm" variant="ghost">Revoke</Button>
          </div>
        </div>
      )) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Account sessions не найдены.</p></div>}
    </div>
  );
}

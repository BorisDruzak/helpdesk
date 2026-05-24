import { ArrowUpRight, Link2, LogOut, UserCheck, UserPlus, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { formatDateTime, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  devices: AdminRegistryPayload["assets"];
  onBind: (deviceId: string) => void;
  onShared: (deviceId: string) => void;
  onResponsible: (deviceId: string) => void;
  onTransfer: (device: AdminRegistryPayload["assets"][number]) => void;
  onRevokeSessions: (device: AdminRegistryPayload["assets"][number]) => void;
  onSelect: (selection: RegistrySelection) => void;
};

export function RegistryDevicesTab({ devices, onBind, onResponsible, onRevokeSessions, onSelect, onShared, onTransfer }: Props) {
  const navigate = useNavigate();
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className="grid min-w-[1500px] grid-cols-[220px_220px_120px_120px_160px_180px_150px_150px_150px_100px_120px_360px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
        <span>Device / hostname</span>
        <span>Device ID</span>
        <span>OS</span>
        <span>Agent</span>
        <span>Online / last</span>
        <span>Registered user</span>
        <span>Binding</span>
        <span>Registration</span>
        <span>Location</span>
        <span>Tickets</span>
        <span>Sessions</span>
        <span>Actions</span>
      </div>
      {devices.length ? devices.map((device) => (
        <div className="grid min-w-[1500px] grid-cols-[220px_220px_120px_120px_160px_180px_150px_150px_150px_100px_120px_360px] gap-3 border-t border-border px-4 py-3 text-sm" key={device.id}>
          <button className="text-left" onClick={() => device.device_id && onSelect({ kind: "device", id: device.device_id })} type="button">
            <p className="font-semibold text-slate-950">{device.hostname ?? device.name ?? "ПК"}</p>
            <p className="mt-1 text-xs text-slate-500">{device.asset_type}</p>
          </button>
          <span className="break-all text-slate-700">{device.device_id ?? "Нет device_id"}</span>
          <span className="text-slate-700">{device.os ?? "Нет данных"}</span>
          <span className="text-slate-700">{device.agent_version ?? "Нет данных"}</span>
          <span className="text-slate-700">{formatDateTime(device.last_seen_at)}</span>
          <span className="text-slate-700">{device.active_person_name ?? device.owner_name ?? "Не зарегистрирован"}</span>
          <span className="text-slate-700">{device.binding_type ?? "Нет"}</span>
          <Badge tone={statusTone(device.registration_status)}>{device.registration_status ?? "unregistered"}</Badge>
          <span className="text-slate-700">{device.location_name ?? "Не указана"}</span>
          <span className="text-slate-700">{device.active_tickets_count ?? device.ticket_count}</span>
          <span className="text-slate-700">{device.active_sessions_count ?? 0}</span>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!device.device_id} leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={() => device.device_id && navigate(`/app/admin/device?device=${encodeURIComponent(device.device_id)}`)} size="sm" variant="outline">ПК</Button>
            <Button disabled={!device.device_id} leadingIcon={<Link2 className="h-4 w-4" />} onClick={() => device.device_id && onBind(device.device_id)} size="sm" variant="outline">Привязать</Button>
            <Button disabled={!device.active_binding_id} leadingIcon={<UserCheck className="h-4 w-4" />} onClick={() => onTransfer(device)} size="sm" variant="outline">Передать</Button>
            <Button disabled={!device.device_id} leadingIcon={<Users className="h-4 w-4" />} onClick={() => device.device_id && onShared(device.device_id)} size="sm" variant="ghost">Shared</Button>
            <Button disabled={!device.device_id} leadingIcon={<UserPlus className="h-4 w-4" />} onClick={() => device.device_id && onResponsible(device.device_id)} size="sm" variant="ghost">Responsible</Button>
            <Button disabled={!device.device_id || !(device.active_sessions_count ?? 0)} leadingIcon={<LogOut className="h-4 w-4" />} onClick={() => onRevokeSessions(device)} size="sm" variant="ghost">Sessions</Button>
          </div>
        </div>
      )) : (
        <div className="border-t border-border p-4">
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Устройства не найдены.</p>
        </div>
      )}
    </div>
  );
}

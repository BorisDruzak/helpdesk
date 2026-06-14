import { ArrowUpRight, Link2, LogOut, UserCheck, UserPlus, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { formatDateTime, registryStatusLabel, relationshipTypeLabel, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  devices: AdminRegistryPayload["assets"];
  onBind: (deviceId: string) => void;
  onShared: (deviceId: string) => void;
  onResponsible: (deviceId: string) => void;
  onTransfer: (device: AdminRegistryPayload["assets"][number]) => void;
  onRevokeSessions: (device: AdminRegistryPayload["assets"][number]) => void;
  onSelect: (selection: RegistrySelection) => void;
  onToggleSelection: (id: string) => void;
  onToggleVisibleSelection: (ids: string[]) => void;
  selectedIds: string[];
};

export function RegistryDevicesTab({ devices, onBind, onResponsible, onRevokeSessions, onSelect, onShared, onToggleSelection, onToggleVisibleSelection, onTransfer, selectedIds }: Props) {
  const navigate = useNavigate();
  const selectableIds = devices.map((device) => device.device_id).filter(Boolean) as string[];
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className="grid min-w-[1560px] grid-cols-[48px_220px_220px_120px_120px_160px_180px_150px_150px_150px_100px_120px_360px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
        <input aria-label="Выбрать все видимые устройства" checked={allVisibleSelected} disabled={!selectableIds.length} onChange={() => onToggleVisibleSelection(selectableIds)} title="Выбрать или снять выбор со всех устройств в текущем фильтре" type="checkbox" />
        <span>Устройство / имя ПК</span>
        <span>ID устройства</span>
        <span>OS</span>
        <span>Агент</span>
        <span>Последняя активность</span>
        <span>Зарегистрированный пользователь</span>
        <span>Привязка</span>
        <span>Регистрация</span>
        <span>Локация</span>
        <span>Тикеты</span>
        <span>Сессии</span>
        <span>Действия</span>
      </div>
      {devices.length ? devices.map((device) => (
        <div className="grid min-w-[1560px] grid-cols-[48px_220px_220px_120px_120px_160px_180px_150px_150px_150px_100px_120px_360px] gap-3 border-t border-border px-4 py-3 text-sm" key={device.id}>
          <input
            aria-label={`Выбрать устройство ${device.hostname ?? device.device_id ?? device.id}`}
            checked={Boolean(device.device_id && selectedIds.includes(device.device_id))}
            disabled={!device.device_id}
            onChange={() => device.device_id && onToggleSelection(device.device_id)}
            type="checkbox"
          />
          <button className="text-left" onClick={() => device.device_id && onSelect({ kind: "device", id: device.device_id })} type="button">
            <p className="font-semibold text-slate-950">{device.hostname ?? device.name ?? "ПК"}</p>
            <p className="mt-1 text-xs text-slate-500">{device.asset_type}</p>
          </button>
          <span className="break-all text-slate-700">{device.device_id ?? "Нет ID устройства"}</span>
          <span className="text-slate-700">{device.os ?? "Нет данных"}</span>
          <span className="text-slate-700">{device.agent_version ?? "Нет данных"}</span>
          <span className="text-slate-700">{formatDateTime(device.last_seen_at)}</span>
          <span className="text-slate-700">{device.active_person_name ?? device.owner_name ?? "Не зарегистрирован"}</span>
          <span className="text-slate-700">{relationshipTypeLabel(device.binding_type)}</span>
          <Badge tone={statusTone(device.registration_status)}>{registryStatusLabel(device.registration_status ?? "unregistered")}</Badge>
          <span className="text-slate-700">{device.location_name ?? "Не указана"}</span>
          <span className="text-slate-700">{device.active_tickets_count ?? device.ticket_count}</span>
          <span className="text-slate-700">{device.active_sessions_count ?? 0}</span>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!device.device_id} leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={() => device.device_id && navigate(`/app/admin/device?device=${encodeURIComponent(device.device_id)}`)} size="sm" title="Открыть карточку устройства с инвентарем и операциями" variant="outline">ПК</Button>
            <Button disabled={!device.device_id} leadingIcon={<Link2 className="h-4 w-4" />} onClick={() => device.device_id && onBind(device.device_id)} size="sm" title="Назначить основного пользователя устройства" variant="outline">Привязать</Button>
            <Button disabled={!device.active_binding_id} leadingIcon={<UserCheck className="h-4 w-4" />} onClick={() => onTransfer(device)} size="sm" title="Передать устройство другому основному пользователю через предпросмотр" variant="outline">Передать</Button>
            <Button disabled={!device.device_id} leadingIcon={<Users className="h-4 w-4" />} onClick={() => device.device_id && onShared(device.device_id)} size="sm" title="Добавить совместного пользователя без смены основного владельца" variant="ghost">Совместный</Button>
            <Button disabled={!device.device_id} leadingIcon={<UserPlus className="h-4 w-4" />} onClick={() => device.device_id && onResponsible(device.device_id)} size="sm" title="Назначить ответственного за устройство" variant="ghost">Ответственный</Button>
            <Button disabled={!device.device_id || !(device.active_sessions_count ?? 0)} leadingIcon={<LogOut className="h-4 w-4" />} onClick={() => onRevokeSessions(device)} size="sm" title="Отозвать все активные аккаунт-сессии этого устройства" variant="ghost">Сессии</Button>
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

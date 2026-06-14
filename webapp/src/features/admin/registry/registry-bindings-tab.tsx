import { ArrowUpRight, RotateCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminDeviceUserBinding } from "../api";
import { formatDateTime, registrySourceLabel, registryStatusLabel, relationshipTypeLabel, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  bindings: AdminDeviceUserBinding[];
  onRevoke: (binding: AdminDeviceUserBinding) => void;
  onSelect: (selection: RegistrySelection) => void;
  onTransferDevice: (deviceId: string) => void;
};

export function RegistryBindingsTab({ bindings, onRevoke, onSelect, onTransferDevice }: Props) {
  const [filter, setFilter] = useState("active");
  const visible = bindings.filter((binding) => filter === "all" || binding.status === filter || binding.relationship_type === filter);
  const filterLabels: Record<string, string> = {
    active: "Активные",
    primary_user: "Основные",
    shared_user: "Совместные",
    responsible: "Ответственные",
    revoked: "Отозванные",
    transferred: "Переданные",
    stale: "Устаревшие",
    all: "Все",
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {["active", "primary_user", "shared_user", "responsible", "revoked", "transferred", "stale", "all"].map((item) => (
          <button className={`rounded-pill px-3 py-2 text-sm font-semibold ${filter === item ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`} key={item} onClick={() => setFilter(item)} title={`Показать: ${filterLabels[item] ?? item}`} type="button">{filterLabels[item] ?? item}</button>
        ))}
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[1260px] grid-cols-[220px_190px_190px_150px_120px_140px_150px_150px_150px_150px_260px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>ID привязки</span><span>Устройство</span><span>Пользователь</span><span>Тип</span><span>Статус</span><span>Источник</span><span>Подтвердил</span><span>Подтверждена</span><span>Действует с</span><span>Действует до</span><span>Действия</span>
        </div>
        {visible.length ? visible.map((binding) => (
          <div className="grid min-w-[1260px] grid-cols-[220px_190px_190px_150px_120px_140px_150px_150px_150px_150px_260px] gap-3 border-t border-border px-4 py-3 text-sm" key={binding.binding_id}>
            <button className="break-all text-left text-brand-700" onClick={() => onSelect({ kind: "binding", id: binding.binding_id })} type="button">{binding.binding_id}</button>
            <span>{binding.hostname ?? binding.device_id}</span>
            <span>{binding.person_name ?? binding.person_id}</span>
            <span title={binding.relationship_type}>{relationshipTypeLabel(binding.relationship_type)}</span>
            <Badge tone={statusTone(binding.status)}>{registryStatusLabel(binding.status)}</Badge>
            <span title={binding.source ?? "registration_claim"}>{registrySourceLabel(binding.source ?? "registration_claim")}</span>
            <span>{binding.confirmed_by_admin ?? "Нет данных"}</span>
            <span>{formatDateTime(binding.confirmed_at)}</span>
            <span>{formatDateTime(binding.valid_from)}</span>
            <span>{formatDateTime(binding.valid_to)}</span>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={() => onSelect({ kind: "binding", id: binding.binding_id })} size="sm" title="Открыть карточку привязки и историю" variant="outline">Открыть</Button>
              <Button disabled={binding.status !== "active"} leadingIcon={<RotateCw className="h-4 w-4" />} onClick={() => onTransferDevice(binding.device_id)} size="sm" title="Передать устройство другому основному пользователю" variant="ghost">Передать</Button>
              <Button disabled={binding.status !== "active"} leadingIcon={<Trash2 className="h-4 w-4" />} onClick={() => onRevoke(binding)} size="sm" title="Отозвать активную привязку с обязательной причиной" variant="ghost">Отозвать</Button>
            </div>
          </div>
        )) : (
          <div className="border-t border-border p-4">
            <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Привязки не найдены.</p>
          </div>
        )}
      </div>
    </div>
  );
}
